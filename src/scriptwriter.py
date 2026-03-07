"""
scriptwriter.py - 播报稿生成模块
调用 LLM API 将论文列表转化为中文新闻播报稿
"""

import os
import json
import requests
from src.fetcher import Paper

# 每分钟中文播报约 280 字
CHARS_PER_MINUTE = 280


def _build_prompt(papers: list[Paper], config: dict) -> str:
    """构造 LLM prompt"""
    content_config = config["content"]
    target_chars = content_config["duration_minutes"] * CHARS_PER_MINUTE
    today = __import__("datetime").date.today().strftime("%Y年%m月%d日")

    papers_text = ""
    for i, p in enumerate(papers, 1):
        authors_str = ", ".join(p.authors[:3])
        if len(p.authors) > 3:
            authors_str += " 等"
        papers_text += f"""
论文{i}:
  标题: {p.title}
  作者: {authors_str}
  摘要: {p.abstract[:500]}
  链接: {p.url}
"""

    prompt = f"""你是一位专业的学术新闻主播，请将以下{len(papers)}篇最新学术论文编写成一期中文播报稿。

日期: {today}

要求:
1. 总字数约{target_chars}字 (对应约{content_config['duration_minutes']}分钟口播)
2. 以"各位听众早上好，这里是Paper Morning学术晨间播报，今天是{today}"开头
3. 逐一介绍每篇论文，每篇包含: 一句话概括核心贡献 → 用通俗语言解释为什么重要 → 关键技术亮点
4. 最后以简短总结收尾，可以点评今天论文的整体趋势
5. 语言风格: 专业但不晦涩，像央视科技频道的主持人，成熟知性，偶尔加入自己的见解
6. 不要使用markdown格式、emoji、括号注释等，输出纯文本，因为这段文字将直接用于语音合成
7. 论文标题用中文翻译，但首次提到时附上英文原名
8. 不需要每篇论文都念作者名字，挑重要的提一下即可

{content_config.get('host_context', '')}

以下是今天要播报的论文:
{papers_text}

请直接输出播报稿全文，不要有任何前缀说明。"""

    return prompt


def _call_deepseek(prompt: str, config: dict) -> str:
    """调用 DeepSeek API"""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY not set")

    ds_config = config["llm"]["deepseek"]
    resp = requests.post(
        f"{ds_config['base_url']}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": ds_config["model"],
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "temperature": 0.7,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_minimax(prompt: str, config: dict) -> str:
    """调用 MiniMax API"""
    api_key = os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        raise ValueError("MINIMAX_API_KEY not set")

    mm_config = config["llm"]["minimax"]
    resp = requests.post(
        f"{mm_config['base_url']}/text/chatcompletion_v2",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": mm_config["model"],
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "temperature": 0.7,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_claude(prompt: str, config: dict) -> str:
    """调用 Claude API"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    cl_config = config["llm"]["claude"]
    resp = requests.post(
        f"{cl_config['base_url']}/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": cl_config["model"],
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return "".join(
        block["text"] for block in data["content"] if block["type"] == "text"
    )


# 提供者映射
_LLM_PROVIDERS = {
    "deepseek": _call_deepseek,
    "minimax": _call_minimax,
    "claude": _call_claude,
}


def generate_script(papers: list[Paper], config: dict) -> str:
    """生成播报稿"""
    provider = config["llm"]["provider"]
    if provider not in _LLM_PROVIDERS:
        raise ValueError(f"Unknown LLM provider: {provider}")

    prompt = _build_prompt(papers, config)
    print(f"[scriptwriter] Generating script via {provider}...")
    print(f"[scriptwriter] Prompt length: {len(prompt)} chars")

    script = _LLM_PROVIDERS[provider](prompt, config)

    print(f"[scriptwriter] Generated script: {len(script)} chars")
    print(f"[scriptwriter] Estimated duration: {len(script) / CHARS_PER_MINUTE:.1f} min")

    return script
