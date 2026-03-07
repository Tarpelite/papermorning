"""
synthesizer.py - 语音合成模块
使用 edge-tts 将播报稿转换为 MP3 音频
分段合成以避免长文本导致 NoAudioReceived 错误
"""

import asyncio
import os
import re
import tempfile
import edge_tts

# edge-tts 单次合成的安全文本长度上限 (字符数)
MAX_CHUNK_CHARS = 500

# 已验证可用的中文女声 (按知性成熟程度排序, 作为 fallback 链)
FALLBACK_VOICES = [
    "zh-CN-XiaoxiaoNeural",     # 通用女声, 最稳定
    "zh-CN-XiaoyiNeural",       # 温暖女声
    "zh-CN-XiaohanNeural",      # 情感丰富女声
    "zh-CN-XiaomengNeural",     # 甜美女声
    "zh-CN-YunyangNeural",      # 新闻男声 (最后兜底)
]


async def _find_valid_voice(preferred: str) -> str:
    """验证语音是否可用, 不可用则从 fallback 列表中选一个"""
    voices = await edge_tts.list_voices()
    available = {v["ShortName"] for v in voices}

    # 打印可用的中文语音供调试
    zh_voices = sorted(v["ShortName"] for v in voices if v["ShortName"].startswith("zh-CN"))
    print(f"[synthesizer] Available zh-CN voices: {zh_voices}")

    if preferred in available:
        print(f"[synthesizer] Using preferred voice: {preferred}")
        return preferred

    print(f"[synthesizer] WARNING: '{preferred}' not available, trying fallbacks...")
    for fb in FALLBACK_VOICES:
        if fb in available:
            print(f"[synthesizer] Using fallback voice: {fb}")
            return fb

    raise RuntimeError(f"No valid zh-CN voice found! Available: {zh_voices}")


def _split_text(text: str) -> list[str]:
    """
    将长文本按句子/段落切分为合适长度的 chunk。
    优先按段落分，段落内再按句号/问号/感叹号分句，
    确保每个 chunk 不超过 MAX_CHUNK_CHARS。
    """
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    chunks = []
    for para in paragraphs:
        if len(para) <= MAX_CHUNK_CHARS:
            chunks.append(para)
        else:
            sentences = re.split(r'(?<=[。？！；.?!;])', para)
            current = ""
            for sent in sentences:
                if not sent.strip():
                    continue
                if len(current) + len(sent) <= MAX_CHUNK_CHARS:
                    current += sent
                else:
                    if current:
                        chunks.append(current)
                    if len(sent) > MAX_CHUNK_CHARS:
                        for i in range(0, len(sent), MAX_CHUNK_CHARS):
                            chunks.append(sent[i:i + MAX_CHUNK_CHARS])
                    else:
                        current = sent
                        continue
                    current = ""
            if current:
                chunks.append(current)

    return [c for c in chunks if c.strip()]


async def _synthesize_chunk(text: str, output_path: str, voice: str, config: dict):
    """合成单个文本 chunk"""
    tts_config = config["tts"]
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=tts_config.get("rate", "+0%"),
        volume=tts_config.get("volume", "+0%"),
        pitch=tts_config.get("pitch", "+0Hz"),
    )
    await communicate.save(output_path)


async def _synthesize_all(text: str, output_path: str, config: dict):
    """分段合成并拼接 MP3"""
    tts_config = config["tts"]

    # 先验证语音可用性
    voice = await _find_valid_voice(tts_config["voice"])

    chunks = _split_text(text)
    print(f"[synthesizer] Split into {len(chunks)} chunks")

    with tempfile.TemporaryDirectory() as tmpdir:
        chunk_files = []
        for i, chunk in enumerate(chunks):
            chunk_path = os.path.join(tmpdir, f"chunk_{i:03d}.mp3")
            max_retries = 3
            success = False

            for attempt in range(max_retries):
                try:
                    await _synthesize_chunk(chunk, chunk_path, voice, config)
                    chunk_files.append(chunk_path)
                    print(f"  [synthesizer] Chunk {i+1}/{len(chunks)}: {len(chunk)} chars -> OK")
                    success = True
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait = (attempt + 1) * 2
                        print(f"  [synthesizer] Chunk {i+1} attempt {attempt+1} failed, retry in {wait}s...")
                        await asyncio.sleep(wait)
                    else:
                        print(f"  [synthesizer] Chunk {i+1}/{len(chunks)}: FAILED after {max_retries} attempts ({e})")
                        print(f"  [synthesizer] Failed text preview: {chunk[:100]}...")

        if not chunk_files:
            raise RuntimeError("All chunks failed to synthesize")

        print(f"[synthesizer] Successfully synthesized {len(chunk_files)}/{len(chunks)} chunks")

        # MP3 是基于帧的格式，可以直接拼接二进制数据
        with open(output_path, "wb") as outfile:
            for cf in chunk_files:
                with open(cf, "rb") as infile:
                    outfile.write(infile.read())


def synthesize_audio(script: str, output_path: str, config: dict) -> str:
    """
    将播报稿合成为 MP3 音频
    """
    tts_config = config["tts"]
    print(f"[synthesizer] Preferred voice: {tts_config['voice']}")
    print(f"[synthesizer] Rate: {tts_config.get('rate', '+0%')}")
    print(f"[synthesizer] Text length: {len(script)} chars")
    print(f"[synthesizer] Generating audio -> {output_path}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    asyncio.run(_synthesize_all(script, output_path, config))

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"[synthesizer] Done! File size: {size_mb:.2f} MB")

    return output_path
