"""
scriptwriter.py - 播报稿生成模块
调用 LLM API 将论文列表转化为有深度的中文学术播报稿
"""

import os
import json
import requests
from datetime import date
from src.fetcher import Paper

# 每分钟中文播报约 280 字
CHARS_PER_MINUTE = 280


def _build_prompt(papers: list[Paper], config: dict) -> str:
    """构造 LLM prompt"""
    content_config = config["content"]
    target_chars = content_config["duration_minutes"] * CHARS_PER_MINUTE
    today = date.today().strftime("%Y年%m月%d日")
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][date.today().weekday()]

    papers_text = ""
    for i, p in enumerate(papers, 1):
        authors_str = ", ".join(p.authors[:3])
        if len(p.authors) > 3:
            authors_str += " 等"
        papers_text += f"""
===== 论文{i} =====
标题: {p.title}
作者: {authors_str}
摘要: {p.abstract[:800]}
链接: {p.url}
来源热度: {"HuggingFace Trending, " + str(p.upvotes) + " upvotes" if p.source == "huggingface" else "arXiv最新"}
"""

    prompt = f"""你是「Paper Morning 学术晨间播报」的主播，一位在AI for Science领域有深厚积累的资深研究者。
你的听众画像是：AI4S方向的青年科研工作者，对neural operator、PDE求解基础模型、科学计算有深入了解，
同时关注整个AI领域的方法论突破和范式变迁。

你的播报风格：
- 像一位你尊敬的学术前辈在早餐时跟你聊天，不是念稿，而是分享见解
- 每篇论文不只是"做了什么"，而是"为什么这件事现在出现了"、"这改变了什么"、"和我们在意的事情有什么关系"
- 敢于给出判断：这篇工作是真正的突破还是增量改进？方法上有什么巧妙或值得商榷之处？
- 善于发现跨领域的联系：比如NLP的scaling law思想如何启发科学计算，RL的训练范式如何影响物理模拟
- 偶尔用类比让抽象概念变得直觉化
- 结尾有对当天论文整体趋势的洞察，不是简单罗列而是提炼出一个统一的观察

你特别关注以下方向的进展和联系（按相关性排序）：
1. 核心方向：neural operator, PDE foundation model, operator learning, physics-informed learning
2. 方法论迁移：foundation model的预训练范式、scaling law、test-time compute如何迁移到科学计算
3. 基础设施：AI4S平台、科学数据、benchmark、开源工具链
4. 前沿范式：diffusion model在科学问题中的应用、几何深度学习、世界模型与物理模拟的交叉
5. 大方向：AI agent在科研中的应用、LLM辅助科学发现

结构要求：
1. 开场：简短亲切的问候，自然引出今天的主题（不要机械地说"今天是某年某月某日"，要自然，比如"各位早上好，今天{weekday}，Paper Morning开播"）
2. 正文：每篇论文用2-4段介绍，第一段一句话讲清核心贡献，后面展开分析。论文之间用自然的过渡语连接，不要"接下来介绍第二篇"这种机械转场
3. 结尾：用2-3句话提炼今天的整体观察。不需要说"感谢收听"之类的套话，用一句有思考余味的话收尾就好

格式规范：
- 总字数约{target_chars}字，对应约{content_config['duration_minutes']}分钟口播
- 输出纯文本，无markdown、无emoji、无括号注释（文本直接送TTS合成）
- 英文论文名和术语首次出现时用中文翻译，可保留关键英文缩写（如PDE, GNN, RL）
- 需要停顿的地方用逗号或句号自然断开，不要出现过长的连续句子

以下是今天要播报的论文：
{papers_text}

请直接输出播报稿全文。"""

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
            "temperature": 0.75,
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
            "temperature": 0.75,
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
            "temperature": 0.75,
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return "".join(
        block["text"] for block in data["content"] if block["type"] == "text"
    )


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

    # 清理LLM可能输出的格式标记
    script = script.strip()
    for prefix in ["```", "---"]:
        if script.startswith(prefix):
            script = script.split("\n", 1)[-1]
    script = script.replace("**", "").replace("##", "").replace("*", "")

    print(f"[scriptwriter] Generated script: {len(script)} chars")
    print(f"[scriptwriter] Estimated duration: {len(script) / CHARS_PER_MINUTE:.1f} min")

    return script
