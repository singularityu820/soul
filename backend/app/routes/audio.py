"""Audio-related routes."""

import logging
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from ..dependencies import get_asr_service, get_llm_service, get_tts_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/audio/conversation")
async def audio_conversation(
    audio: UploadFile = File(...),
    thread_id: Optional[str] = Form(None),
    voice: str = Form("zhichu_emo"),
    locale: str = Form("zh-CN"),
) -> dict:
    """
    音频对话接口 - WebRTC 的替代方案
    
    上传音频文件,执行 ASR → LLM → TTS 流程,返回响应音频
    
    Args:
        audio: 音频文件 (WAV, MP3, OGG 等)
        thread_id: 对话线程 ID (可选,用于保持上下文)
        voice: TTS 语音 (默认: zhichu_emo)
        locale: 语音地区 (默认: zh-CN)
    
    Returns:
        {
            "transcript": "用户说的话",
            "response_text": "AI 回复文本",
            "audio_url": "响应音频的 URL 或 base64"
        }
    """
    try:
        asr_service = get_asr_service()
        llm_service = get_llm_service()
        tts_service = get_tts_service()
        
        # 1. 读取音频数据
        audio_data = await audio.read()
        logger.info(f"Received audio upload: {len(audio_data)} bytes, content_type={audio.content_type}")
        
        # 2. ASR 转录
        logger.info("Starting ASR transcription...")
        transcript = await asr_service.transcribe(audio_data)
        logger.info(f"ASR transcript: {transcript}")
        
        if not transcript or not transcript.strip():
            raise HTTPException(status_code=400, detail="无法识别语音内容")
        
        # 3. LLM 生成响应
        logger.info("Generating LLM response...")
    
        # 简单对话(不使用 agent 的复杂流程)
        # 构建对话上下文
        if thread_id:
            # 获取最近几条消息作为上下文
            try:
                history_response = await httpx.AsyncClient().get(
                    f"http://localhost:8000/chat/threads/{thread_id}/messages",
                    timeout=5.0
                )
                if history_response.status_code == 200:
                    history = history_response.json()
                    context_messages = history[-5:] if len(history) > 5 else history
                    context = "\n".join([
                        f"{'用户' if msg.get('role') == 'user' else 'AI'}: {msg.get('content', '')}"
                        for msg in context_messages
                    ])
                    prompt = f"{context}\n用户: {transcript}\nAI:"
                else:
                    prompt = f"用户: {transcript}\nAI:"
            except:
                prompt = f"用户: {transcript}\nAI:"
        else:
            prompt = f"用户: {transcript}\nAI:"
        
        response_text = await llm_service.generate(prompt=prompt, temperature=0.7)
        logger.info(f"LLM response: {response_text}")
        
        # 4. TTS 合成
        logger.info("Synthesizing TTS audio...")
        tts_result = await tts_service.synthesize(
            text=response_text,
            voice=voice,
            locale=locale,
        )
        
        # 5. 返回结果
        return {
            "transcript": transcript,
            "response_text": response_text,
            "audio_reference": tts_result.audio_reference,
            "tts_provider": tts_result.provider.value,
            "voice": tts_result.voice,
            "locale": tts_result.locale,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Audio conversation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理音频失败: {str(e)}")


@router.get("/audio/download")
async def download_audio(reference: str) -> Response:
    """
    下载音频文件
    
    Args:
        reference: 音频引用 (URL 或文件路径)
    
    Returns:
        音频文件内容
    """
    try:
        # 如果是 HTTP URL,下载它
        if reference.startswith("http://") or reference.startswith("https://"):
            async with httpx.AsyncClient() as client:
                response = await client.get(reference)
                response.raise_for_status()
                return Response(
                    content=response.content,
                    media_type="audio/wav",
                    headers={
                        "Content-Disposition": f'attachment; filename="response.wav"'
                    }
                )
        
        # 如果是本地文件路径
        file_path = Path(reference)
        if file_path.exists():
            with open(file_path, "rb") as f:
                content = f.read()
            return Response(
                content=content,
                media_type="audio/wav",
                headers={
                    "Content-Disposition": f'attachment; filename="{file_path.name}"'
                }
            )
        
        raise HTTPException(status_code=404, detail="音频文件不存在")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Audio download failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"下载音频失败: {str(e)}")
