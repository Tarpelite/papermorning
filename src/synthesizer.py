"""
synthesizer.py - 语音合成模块
使用 edge-tts 将播报稿转换为 MP3 音频
"""

import asyncio
import edge_tts


async def _synthesize(text: str, output_path: str, config: dict) -> str:
    """异步合成语音"""
    tts_config = config["tts"]

    communicate = edge_tts.Communicate(
        text=text,
        voice=tts_config["voice"],
        rate=tts_config.get("rate", "+0%"),
        volume=tts_config.get("volume", "+0%"),
        pitch=tts_config.get("pitch", "+0Hz"),
    )

    await communicate.save(output_path)
    return output_path


def synthesize_audio(script: str, output_path: str, config: dict) -> str:
    """
    将播报稿合成为MP3音频
    
    Args:
        script: 播报稿文本
        output_path: 输出MP3文件路径
        config: 配置字典
    
    Returns:
        输出文件路径
    """
    tts_config = config["tts"]
    print(f"[synthesizer] Voice: {tts_config['voice']}")
    print(f"[synthesizer] Rate: {tts_config.get('rate', '+0%')}")
    print(f"[synthesizer] Generating audio -> {output_path}")

    asyncio.run(_synthesize(script, output_path, config))

    # 打印文件大小
    import os
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"[synthesizer] Done! File size: {size_mb:.2f} MB")

    return output_path
