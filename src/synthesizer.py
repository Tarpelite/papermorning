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


def _split_text(text: str) -> list[str]:
    """
    将长文本按句子/段落切分为合适长度的 chunk。
    优先按段落分，段落内再按句号/问号/感叹号分句，
    确保每个 chunk 不超过 MAX_CHUNK_CHARS。
    """
    # 先按换行分段
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    chunks = []
    for para in paragraphs:
        if len(para) <= MAX_CHUNK_CHARS:
            chunks.append(para)
        else:
            # 按中文句号、问号、感叹号、分号分句
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
                    # 如果单句就超长，强制按长度切
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


async def _synthesize_chunk(text: str, output_path: str, config: dict):
    """合成单个文本 chunk"""
    tts_config = config["tts"]
    communicate = edge_tts.Communicate(
        text=text,
        voice=tts_config["voice"],
        rate=tts_config.get("rate", "+0%"),
        volume=tts_config.get("volume", "+0%"),
        pitch=tts_config.get("pitch", "+0Hz"),
    )
    await communicate.save(output_path)


async def _synthesize_all(text: str, output_path: str, config: dict):
    """分段合成并拼接 MP3"""
    chunks = _split_text(text)
    print(f"[synthesizer] Split into {len(chunks)} chunks")

    # 用临时目录存放各段音频
    with tempfile.TemporaryDirectory() as tmpdir:
        chunk_files = []
        for i, chunk in enumerate(chunks):
            chunk_path = os.path.join(tmpdir, f"chunk_{i:03d}.mp3")
            try:
                await _synthesize_chunk(chunk, chunk_path, config)
                chunk_files.append(chunk_path)
                print(f"  [synthesizer] Chunk {i+1}/{len(chunks)}: {len(chunk)} chars -> OK")
            except Exception as e:
                print(f"  [synthesizer] Chunk {i+1}/{len(chunks)}: FAILED ({e}), skipping")
                continue

        if not chunk_files:
            raise RuntimeError("All chunks failed to synthesize")

        # MP3 是基于帧的格式，可以直接拼接二进制数据
        with open(output_path, "wb") as outfile:
            for cf in chunk_files:
                with open(cf, "rb") as infile:
                    outfile.write(infile.read())


def synthesize_audio(script: str, output_path: str, config: dict) -> str:
    """
    将播报稿合成为 MP3 音频

    Args:
        script: 播报稿文本
        output_path: 输出 MP3 文件路径
        config: 配置字典

    Returns:
        输出文件路径
    """
    tts_config = config["tts"]
    print(f"[synthesizer] Voice: {tts_config['voice']}")
    print(f"[synthesizer] Rate: {tts_config.get('rate', '+0%')}")
    print(f"[synthesizer] Text length: {len(script)} chars")
    print(f"[synthesizer] Generating audio -> {output_path}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    asyncio.run(_synthesize_all(script, output_path, config))

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"[synthesizer] Done! File size: {size_mb:.2f} MB")

    return output_path
