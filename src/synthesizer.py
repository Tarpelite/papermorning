"""
synthesizer.py - 语音合成模块
使用 edge-tts 将播报稿转换为 MP3 音频
支持背景音乐混合（开头/结尾渐入渐出 + 正文低音量垫底）
"""

import asyncio
import os
import re
import tempfile
import edge_tts

MAX_CHUNK_CHARS = 500

FALLBACK_VOICES = [
    "zh-CN-XiaoxiaoNeural",
    "zh-CN-XiaoyiNeural",
    "zh-CN-XiaohanNeural",
    "zh-CN-XiaomengNeural",
    "zh-CN-YunyangNeural",
]


async def _find_valid_voice(preferred: str) -> str:
    """验证语音是否可用, 不可用则从 fallback 列表中选一个"""
    voices = await edge_tts.list_voices()
    available = {v["ShortName"] for v in voices}

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
    """将长文本按句子切分为合适长度的 chunk"""
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


async def _synthesize_voice(text: str, output_path: str, config: dict):
    """分段合成语音部分"""
    tts_config = config["tts"]
    voice = await _find_valid_voice(tts_config["voice"])

    chunks = _split_text(text)
    print(f"[synthesizer] Split into {len(chunks)} chunks")

    with tempfile.TemporaryDirectory() as tmpdir:
        chunk_files = []
        for i, chunk in enumerate(chunks):
            chunk_path = os.path.join(tmpdir, f"chunk_{i:03d}.mp3")
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await _synthesize_chunk(chunk, chunk_path, voice, config)
                    chunk_files.append(chunk_path)
                    print(f"  [synthesizer] Chunk {i+1}/{len(chunks)}: {len(chunk)} chars -> OK")
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait = (attempt + 1) * 2
                        print(f"  [synthesizer] Chunk {i+1} attempt {attempt+1} failed, retry in {wait}s...")
                        await asyncio.sleep(wait)
                    else:
                        print(f"  [synthesizer] Chunk {i+1}/{len(chunks)}: FAILED ({e})")

        if not chunk_files:
            raise RuntimeError("All chunks failed to synthesize")

        print(f"[synthesizer] Successfully synthesized {len(chunk_files)}/{len(chunks)} chunks")

        with open(output_path, "wb") as outfile:
            for cf in chunk_files:
                with open(cf, "rb") as infile:
                    outfile.write(infile.read())


def _mix_bgm(voice_path: str, output_path: str, config: dict):
    """
    将语音和背景音乐混合:
    - 开头: 2秒纯BGM引入, 然后BGM渐弱
    - 正文: BGM以低音量垫底
    - 结尾: BGM渐强, 2秒纯BGM收尾
    """
    from pydub import AudioSegment

    bgm_config = config.get("bgm", {})
    bgm_path = bgm_config.get("file")

    if not bgm_path or not os.path.exists(bgm_path):
        print(f"[synthesizer] No BGM file found at '{bgm_path}', skipping mix")
        # 无BGM时直接复制
        if voice_path != output_path:
            import shutil
            shutil.copy2(voice_path, output_path)
        return

    print(f"[synthesizer] Mixing BGM: {bgm_path}")

    voice = AudioSegment.from_mp3(voice_path)
    bgm = AudioSegment.from_mp3(bgm_path)

    # BGM参数
    intro_ms = bgm_config.get("intro_duration_ms", 2500)    # 纯BGM引入时长
    outro_ms = bgm_config.get("outro_duration_ms", 3000)    # 纯BGM收尾时长
    fade_ms = bgm_config.get("fade_duration_ms", 1500)      # 渐变时长
    bgm_volume_db = bgm_config.get("body_volume_db", -22)   # 正文期间BGM相对音量

    # 确保BGM足够长 (循环)
    total_needed = len(voice) + intro_ms + outro_ms + 2000  # 多留2秒余量
    while len(bgm) < total_needed:
        bgm = bgm + bgm

    # 构建BGM轨道:
    # [intro: 原音量] [fade_down] [body: 低音量] [fade_up] [outro: 原音量]
    bgm_intro = bgm[:intro_ms]                              # 引入段, 原音量
    bgm_body = bgm[intro_ms:intro_ms + len(voice)]          # 正文段
    bgm_body = bgm_body + bgm_volume_db                     # 降低音量
    bgm_outro = bgm[intro_ms + len(voice):intro_ms + len(voice) + outro_ms]  # 收尾段

    # 对正文段做首尾渐变, 使过渡平滑
    bgm_body = bgm_body.fade_in(fade_ms).fade_out(fade_ms)

    # 构建语音轨道: 前面加静音对齐intro
    silence_intro = AudioSegment.silent(duration=intro_ms)
    voice_padded = silence_intro + voice

    # 构建完整BGM轨道
    bgm_full = bgm_intro + bgm_body + bgm_outro
    bgm_full = bgm_full.fade_out(fade_ms)  # 最后整体淡出

    # 对齐长度 (取较长的)
    if len(bgm_full) > len(voice_padded):
        voice_padded = voice_padded + AudioSegment.silent(duration=len(bgm_full) - len(voice_padded))
    elif len(voice_padded) > len(bgm_full):
        bgm_full = bgm_full + AudioSegment.silent(duration=len(voice_padded) - len(bgm_full))

    # 混合
    mixed = voice_padded.overlay(bgm_full)

    # 导出
    mixed.export(output_path, format="mp3", bitrate="192k")
    print(f"[synthesizer] Mixed output: {len(mixed)/1000:.1f}s")


def synthesize_audio(script: str, output_path: str, config: dict) -> str:
    """
    将播报稿合成为 MP3 音频 (可选混合BGM)
    """
    tts_config = config["tts"]
    print(f"[synthesizer] Preferred voice: {tts_config['voice']}")
    print(f"[synthesizer] Rate: {tts_config.get('rate', '+0%')}")
    print(f"[synthesizer] Text length: {len(script)} chars")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 判断是否需要混BGM
    bgm_config = config.get("bgm", {})
    has_bgm = bgm_config.get("enabled", False) and bgm_config.get("file")

    if has_bgm:
        # 先合成纯语音到临时文件, 再混合BGM
        voice_path = output_path.replace(".mp3", "_voice.mp3")
        print(f"[synthesizer] Generating voice -> {voice_path}")
        asyncio.run(_synthesize_voice(script, voice_path, config))

        print(f"[synthesizer] Mixing with BGM -> {output_path}")
        _mix_bgm(voice_path, output_path, config)

        # 清理临时语音文件
        if os.path.exists(voice_path):
            os.remove(voice_path)
    else:
        print(f"[synthesizer] Generating audio (no BGM) -> {output_path}")
        asyncio.run(_synthesize_voice(script, output_path, config))

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"[synthesizer] Done! File size: {size_mb:.2f} MB")

    return output_path
