"""
fetcher.py - 论文数据抓取模块
支持 HuggingFace Daily Papers API 和 arXiv API
"""

import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from dataclasses import dataclass, field


@dataclass
class Paper:
    """论文数据结构"""
    title: str
    authors: list[str]
    abstract: str
    arxiv_id: str
    url: str
    published: str
    source: str  # "huggingface" or "arxiv"
    score: float = 0.0  # 综合相关性得分
    upvotes: int = 0     # HF社区点赞数


def fetch_huggingface_papers(config: dict) -> list[Paper]:
    """从 HuggingFace Daily Papers API 抓取trending论文"""
    hf_config = config["sources"]["huggingface"]
    if not hf_config["enabled"]:
        return []

    try:
        resp = requests.get(
            hf_config["api_url"],
            params={"limit": hf_config["max_papers"]},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[fetcher] HuggingFace API error: {e}")
        return []

    papers = []
    for item in data:
        paper_info = item.get("paper", {})
        arxiv_id = paper_info.get("id", "")
        papers.append(Paper(
            title=paper_info.get("title", ""),
            authors=[a.get("name", "") for a in paper_info.get("authors", [])[:5]],
            abstract=paper_info.get("summary", ""),
            arxiv_id=arxiv_id,
            url=f"https://arxiv.org/abs/{arxiv_id}",
            published=paper_info.get("publishedAt", ""),
            source="huggingface",
            upvotes=item.get("paper", {}).get("upvotes", 0),
        ))

    print(f"[fetcher] Got {len(papers)} papers from HuggingFace")
    return papers


def fetch_arxiv_papers(config: dict) -> list[Paper]:
    """从 arXiv API 抓取指定领域的最新论文"""
    arxiv_config = config["sources"]["arxiv"]
    if not arxiv_config["enabled"]:
        return []

    # 构造查询: 按分类 OR 关键词
    cat_query = " OR ".join(f"cat:{c}" for c in arxiv_config["categories"])
    query = f"({cat_query})"

    try:
        resp = requests.get(
            "http://export.arxiv.org/api/query",
            params={
                "search_query": query,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
                "max_results": arxiv_config["max_results"],
            },
            timeout=30,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"[fetcher] arXiv API error: {e}")
        return []

    # 解析 Atom XML
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }
    root = ET.fromstring(resp.text)
    papers = []

    for entry in root.findall("atom:entry", ns):
        title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
        abstract = entry.find("atom:summary", ns).text.strip().replace("\n", " ")
        authors = [
            a.find("atom:name", ns).text
            for a in entry.findall("atom:author", ns)
        ][:5]
        arxiv_id_full = entry.find("atom:id", ns).text  # http://arxiv.org/abs/xxxx.xxxxx
        arxiv_id = arxiv_id_full.split("/abs/")[-1]
        published = entry.find("atom:published", ns).text

        papers.append(Paper(
            title=title,
            authors=authors,
            abstract=abstract,
            arxiv_id=arxiv_id,
            url=f"https://arxiv.org/abs/{arxiv_id}",
            published=published,
            source="arxiv",
        ))

    print(f"[fetcher] Got {len(papers)} papers from arXiv")
    return papers


def score_relevance(paper: Paper, keywords: list[str]) -> float:
    """计算论文与用户关键词的相关性得分"""
    text = (paper.title + " " + paper.abstract).lower()
    keyword_score = sum(
        2.0 if kw.lower() in paper.title.lower() else
        1.0 if kw.lower() in text else 0.0
        for kw in keywords
    )
    # HF upvotes 作为社区热度信号
    popularity_score = min(paper.upvotes / 10.0, 5.0) if paper.upvotes else 0.0
    return keyword_score + popularity_score


def fetch_and_rank(config: dict) -> list[Paper]:
    """抓取所有源的论文, 去重, 打分, 排序"""
    all_papers = []
    all_papers.extend(fetch_huggingface_papers(config))
    all_papers.extend(fetch_arxiv_papers(config))

    # 按 arxiv_id 去重 (优先保留HF源, 因为有upvotes信息)
    seen = {}
    for p in all_papers:
        clean_id = re.sub(r"v\d+$", "", p.arxiv_id)  # 去掉版本号
        if clean_id not in seen or p.source == "huggingface":
            seen[clean_id] = p
    unique_papers = list(seen.values())

    # 打分排序
    keywords = config["sources"]["arxiv"].get("keywords", [])
    for p in unique_papers:
        p.score = score_relevance(p, keywords)

    # 按得分降序, 取 top N
    unique_papers.sort(key=lambda p: p.score, reverse=True)
    n = config["content"]["num_papers"]

    print(f"[fetcher] {len(unique_papers)} unique papers, returning top {n}")
    for p in unique_papers[:n]:
        print(f"  [{p.score:.1f}] {p.title[:80]}")

    return unique_papers[:n]
