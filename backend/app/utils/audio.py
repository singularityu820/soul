"""Audio utility functions."""

import logging

import httpx

logger = logging.getLogger(__name__)


async def fetch_audio_from_url(url: str) -> bytes | None:
    """
    从 URL 下载音频数据并转换为 PCM 格式。
    
    Args:
        url: 音频文件 URL (可能是 WAV, MP3 等)
    
    Returns:
        PCM 16-bit 音频数据，如果失败返回 None
    """
    try:
        # 跳过占位 URL
        if url.startswith(("sandbox://", "empty://", "error://", "missing-key://")):
            logger.debug("Skipping placeholder audio URL: %s", url)
            return None
        
        # 下载音频文件
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            if not response.is_success:
                logger.error("Failed to download audio from %s: %s", url, response.status_code)
                return None
            
            audio_data = response.content
            
        # TODO: 如果需要格式转换（WAV → PCM），可以使用 av 库
        # 当前假设 TTS 返回的是 WAV 格式，直接返回
        # 实际使用中可能需要解析 WAV header 并提取 PCM 数据
        
        logger.info("Downloaded %d bytes of audio from %s", len(audio_data), url)
        return audio_data
        
    except Exception as e:
        logger.exception("Error fetching audio from %s: %s", url, e)
        return None
