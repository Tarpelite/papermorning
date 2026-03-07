"""
feed_generator.py - 播客 RSS Feed 生成模块
生成标准 Podcast RSS 2.0 Feed，可被苹果播客/小宇宙/Pocket Casts等客户端订阅
"""

import os
import json
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent


EPISODES_DIR = "docs/episodes"
EPISODES_INDEX = "docs/episodes/index.json"


def _load_episodes_index() -> list[dict]:
    """加载已有的 episodes 索引"""
    if os.path.exists(EPISODES_INDEX):
        with open(EPISODES_INDEX, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_episodes_index(episodes: list[dict]):
    """保存 episodes 索引"""
    os.makedirs(os.path.dirname(EPISODES_INDEX), exist_ok=True)
    with open(EPISODES_INDEX, "w", encoding="utf-8") as f:
        json.dump(episodes, f, ensure_ascii=False, indent=2)


def add_episode(
    date_str: str,
    title: str,
    description: str,
    audio_filename: str,
    script: str,
    papers_data: list[dict],
    config: dict,
) -> dict:
    """添加一期新节目到索引"""
    episodes = _load_episodes_index()

    episode = {
        "date": date_str,
        "title": title,
        "description": description,
        "audio_file": audio_filename,
        "script": script[:500] + "..." if len(script) > 500 else script,
        "papers": papers_data,
        "published_at": datetime.utcnow().isoformat() + "Z",
    }

    # 去重 (同日期只保留最新)
    episodes = [ep for ep in episodes if ep["date"] != date_str]
    episodes.insert(0, episode)

    # 保留最近 N 期
    max_episodes = config["publish"]["max_episodes"]
    episodes = episodes[:max_episodes]

    _save_episodes_index(episodes)
    return episode


def generate_rss_feed(config: dict):
    """生成播客 RSS XML feed"""
    pub = config["publish"]
    episodes = _load_episodes_index()

    # RSS 2.0 root
    rss = Element("rss", version="2.0")
    rss.set("xmlns:itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
    rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")

    channel = SubElement(rss, "channel")

    # 频道元信息
    SubElement(channel, "title").text = pub["podcast_title"]
    SubElement(channel, "description").text = pub["podcast_description"]
    SubElement(channel, "language").text = pub["podcast_language"]
    SubElement(channel, "link").text = pub["site_url"]
    SubElement(channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}author").text = pub["podcast_author"]
    SubElement(channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}summary").text = pub["podcast_description"]

    # 封面图
    image = SubElement(channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}image")
    image.set("href", pub.get("podcast_cover", ""))

    # 分类
    cat = SubElement(channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}category")
    cat.set("text", "Science")

    # 逐期生成 item
    for ep in episodes:
        item = SubElement(channel, "item")
        SubElement(item, "title").text = ep["title"]
        SubElement(item, "description").text = ep.get("description", "")

        # 音频 enclosure - 播客客户端靠这个下载音频
        audio_url = f"{pub['site_url']}/episodes/{ep['audio_file']}"
        audio_path = os.path.join(EPISODES_DIR, ep["audio_file"])
        file_size = os.path.getsize(audio_path) if os.path.exists(audio_path) else 0

        enclosure = SubElement(item, "enclosure")
        enclosure.set("url", audio_url)
        enclosure.set("length", str(file_size))
        enclosure.set("type", "audio/mpeg")

        SubElement(item, "guid").text = audio_url
        SubElement(item, "pubDate").text = ep.get("published_at", "")
        SubElement(item, "{http://www.itunes.com/dtds/podcast-1.0.dtd}duration").text = "300"  # ~5min

    # 写出 XML
    tree = ElementTree(rss)
    indent(tree, space="  ")

    feed_path = "docs/feed.xml"
    os.makedirs(os.path.dirname(feed_path), exist_ok=True)
    tree.write(feed_path, encoding="unicode", xml_declaration=True)

    print(f"[feed] Generated {feed_path} with {len(episodes)} episodes")
    return feed_path


def generate_episode_page(episode: dict, script: str, config: dict):
    """为每期生成一个简单的 HTML 页面 (方便浏览器直接看)"""
    pub = config["publish"]
    audio_url = f"episodes/{episode['audio_file']}"

    papers_html = ""
    for p in episode.get("papers", []):
        papers_html += f'<li><a href="{p["url"]}" target="_blank">{p["title"]}</a></li>\n'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{episode['title']}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
               max-width: 680px; margin: 0 auto; padding: 24px; color: #1a1a1a;
               background: #fafafa; }}
        h1 {{ font-size: 1.5em; margin-bottom: 8px; }}
        .date {{ color: #666; margin-bottom: 20px; }}
        audio {{ width: 100%; margin: 20px 0; }}
        .script {{ background: #fff; padding: 20px; border-radius: 8px;
                   line-height: 1.8; white-space: pre-wrap; border: 1px solid #eee; }}
        .papers {{ margin-top: 24px; }}
        .papers h2 {{ font-size: 1.1em; margin-bottom: 12px; }}
        .papers li {{ margin: 8px 0; }}
        .papers a {{ color: #0066cc; text-decoration: none; }}
        .papers a:hover {{ text-decoration: underline; }}
        .nav {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #eee; }}
        .nav a {{ color: #666; text-decoration: none; }}
    </style>
</head>
<body>
    <h1>{episode['title']}</h1>
    <p class="date">{episode['date']}</p>

    <audio controls preload="metadata">
        <source src="{audio_url}" type="audio/mpeg">
        你的浏览器不支持音频播放
    </audio>

    <div class="script">{script}</div>

    <div class="papers">
        <h2>本期涉及论文</h2>
        <ul>{papers_html}</ul>
    </div>

    <div class="nav">
        <a href="./">← 返回首页</a> ·
        <a href="feed.xml">RSS 订阅</a>
    </div>
</body>
</html>"""

    page_path = f"docs/{episode['date']}.html"
    with open(page_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[feed] Generated episode page: {page_path}")
    return page_path


def generate_index_page(config: dict):
    """生成首页 index.html"""
    pub = config["publish"]
    episodes = _load_episodes_index()

    episodes_html = ""
    for ep in episodes:
        episodes_html += f"""
        <div class="episode">
            <a href="{ep['date']}.html">{ep['title']}</a>
            <span class="date">{ep['date']}</span>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{pub['podcast_title']}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
               max-width: 680px; margin: 0 auto; padding: 24px; color: #1a1a1a;
               background: #fafafa; }}
        h1 {{ font-size: 1.8em; margin-bottom: 4px; }}
        .subtitle {{ color: #666; margin-bottom: 32px; }}
        .episode {{ padding: 12px 0; border-bottom: 1px solid #eee;
                    display: flex; justify-content: space-between; align-items: center; }}
        .episode a {{ color: #1a1a1a; text-decoration: none; font-weight: 500; }}
        .episode a:hover {{ color: #0066cc; }}
        .episode .date {{ color: #999; font-size: 0.9em; }}
        .subscribe {{ margin-top: 32px; padding: 16px; background: #fff;
                      border-radius: 8px; border: 1px solid #eee; }}
        .subscribe code {{ background: #f0f0f0; padding: 4px 8px; border-radius: 4px;
                           font-size: 0.85em; word-break: break-all; }}
    </style>
</head>
<body>
    <h1>{pub['podcast_title']}</h1>
    <p class="subtitle">{pub['podcast_description']}</p>

    <div class="episodes">{episodes_html}</div>

    <div class="subscribe">
        <strong>订阅播客</strong><br>
        复制以下 RSS 链接到你的播客客户端 (苹果播客/小宇宙/Pocket Casts):<br><br>
        <code>{pub['site_url']}/feed.xml</code>
    </div>
</body>
</html>"""

    index_path = "docs/index.html"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[feed] Generated index page: {index_path}")
