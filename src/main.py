"""
main.py - Paper Morning 主流程
抓取 → 生成播报稿 → 语音合成 → 发布
"""

import os
import sys
import yaml
from datetime import date

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fetcher import fetch_and_rank
from src.scriptwriter import generate_script
from src.synthesizer import synthesize_audio
from src.feed_generator import (
    add_episode,
    generate_rss_feed,
    generate_episode_page,
    generate_index_page,
)


def load_config(path: str = "config.yaml") -> dict:
    """加载配置文件"""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    print("=" * 60)
    print("  Paper Morning - 学术晨间播报")
    print("=" * 60)

    # 1. 加载配置
    config = load_config()
    today = date.today().strftime("%Y-%m-%d")
    print(f"\n[main] Date: {today}")
    print(f"[main] LLM provider: {config['llm']['provider']}")
    print(f"[main] TTS voice: {config['tts']['voice']}")

    # 2. 抓取论文
    print("\n--- Step 1: Fetching papers ---")
    papers = fetch_and_rank(config)
    if not papers:
        print("[main] No papers found, exiting.")
        return

    # 3. 生成播报稿
    print("\n--- Step 2: Generating script ---")
    script = generate_script(papers, config)

    # 保存播报稿文本
    script_path = f"docs/episodes/{today}.txt"
    os.makedirs(os.path.dirname(script_path), exist_ok=True)
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)
    print(f"[main] Script saved to {script_path}")

    # 4. 语音合成
    print("\n--- Step 3: Synthesizing audio ---")
    audio_filename = f"{today}.mp3"
    audio_path = f"docs/episodes/{audio_filename}"
    synthesize_audio(script, audio_path, config)

    # 5. 更新 Feed
    print("\n--- Step 4: Publishing ---")
    papers_data = [
        {"title": p.title, "url": p.url, "arxiv_id": p.arxiv_id}
        for p in papers
    ]
    episode_title = f"Paper Morning {today}"
    episode_desc = f"今日学术播报: {', '.join(p.title[:30] for p in papers[:3])}..."

    episode = add_episode(
        date_str=today,
        title=episode_title,
        description=episode_desc,
        audio_filename=audio_filename,
        script=script,
        papers_data=papers_data,
        config=config,
    )

    generate_episode_page(episode, script, config)
    generate_rss_feed(config)
    generate_index_page(config)

    print("\n" + "=" * 60)
    print(f"  Done! Episode: {episode_title}")
    print(f"  Audio: {audio_path}")
    print(f"  Feed:  docs/feed.xml")
    print("=" * 60)


if __name__ == "__main__":
    main()
