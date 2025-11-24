"""WebSocket endpoints."""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Cookie, Depends, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from starlette.websockets import WebSocketState

from ..dependencies import (
    get_chat_service,
    get_chat_storage,
    get_llm_service,
    get_pipeline,
    get_real_eeg_processor,
    get_tts_service,
    get_voice_stream_hub,
)
from ..schemas import ChatEvent, ChatMessage, PipelineEvent
from ..services.chat.service import ChatService
from ..services.emotion import EmotionPipeline
from ..utils.audio import fetch_audio_from_url

router = APIRouter()
logger = logging.getLogger(__name__)

# ============================================================================
# Pipeline WebSocket
# ============================================================================

@router.websocket("/ws/pipeline")
async def pipeline_stream(
    websocket: WebSocket,
    pipeline: EmotionPipeline = Depends(get_pipeline),
) -> None:
    await websocket.accept()
    queue = pipeline.subscribe()

    try:
        if pipeline.latest_state:
            initial_event = PipelineEvent(
                emotion=pipeline.latest_state,
                avatar=pipeline.avatar.translate(pipeline.latest_state),
                agent_message=pipeline.latest_message,
            )
            await websocket.send_json(jsonable_encoder(initial_event))

        while True:
            event = await queue.get()
            await websocket.send_json(jsonable_encoder(event))
    except WebSocketDisconnect:
        logger.debug("Pipeline websocket disconnected")
    except Exception:
        logger.exception("Pipeline websocket encountered an error")
    finally:
        pipeline.unsubscribe(queue)
        if websocket.application_state != WebSocketState.DISCONNECTED:
            await websocket.close()


# ============================================================================
# Chat WebSocket
# ============================================================================

@router.websocket("/ws/chat")
async def chat_stream(
    websocket: WebSocket,
    chat: ChatService = Depends(get_chat_service),
) -> None:
    await websocket.accept()
    thread_id = websocket.query_params.get("thread_id")
    queue = await chat.subscribe()

    try:
        if thread_id:
            history = await chat.history(thread_id)
            for message in history:
                await websocket.send_json(
                    jsonable_encoder(ChatEvent(thread_id=thread_id, message=message))
                )

        while True:
            event = await queue.get()
            if thread_id and event.thread_id != thread_id:
                continue
            await websocket.send_json(jsonable_encoder(event))
    except WebSocketDisconnect:
        logger.debug("Chat websocket disconnected")
    except Exception:
        logger.exception("Chat websocket encountered an error")
    finally:
        chat.unsubscribe(queue)
        if websocket.application_state != WebSocketState.DISCONNECTED:
            await websocket.close()


# ============================================================================
# Real EEG WebSocket
# ============================================================================

@router.websocket("/eeg/real/stream/{room_id}")
async def websocket_real_eeg_stream(
    websocket: WebSocket,
    room_id: str
):
    """WebSocket端点，用于实时传输真实脑电数据和情绪分析结果"""
    await websocket.accept()
    logger.info(f"WebSocket connection established for real EEG stream in room {room_id}")
    
    try:
        real_eeg_processor = get_real_eeg_processor()
        
        # 检查是否有设备连接
        devices = await real_eeg_processor.get_device_status()
        if not devices:
            await websocket.send_json({
                "type": "error",
                "message": "没有可用的EEG设备"
            })
            await websocket.close()
            return
        
        # 使用第一个可用设备
        device_id = devices[0]["id"]
        
        # 如果设备未开始流式传输，则启动它
        is_streaming = await real_eeg_processor.is_streaming(device_id)
        if not is_streaming:
            await real_eeg_processor.start_streaming(device_id)
        
        # 持续发送数据
        while True:
            try:
                # 获取最新数据
                data = await real_eeg_processor.get_latest_data(device_id, 100)
                
                # 分析情绪
                emotion = await real_eeg_processor.analyze_emotion(device_id)
                
                # 发送数据
                await websocket.send_json({
                    "type": "eeg_data",
                    "device_id": device_id,
                    "timestamp": time.time(),
                    "data": data,
                    "emotion": emotion
                })
                
                # 等待一段时间再发送下一批数据
                await asyncio.sleep(0.1)  # 10Hz更新率
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for room {room_id}")
                break
            except Exception as e:
                logger.error(f"Error sending EEG data: {e}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "message": f"发送EEG数据时出错: {str(e)}"
                })
                break
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for room {room_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        await websocket.send_json({
            "type": "error",
            "message": f"WebSocket错误: {str(e)}"
        })
    finally:
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()


# ============================================================================
# Voice Stream WebSocket
# ============================================================================

@router.websocket("/ws/voice-stream")
async def voice_stream_websocket(
    websocket: WebSocket,
    session_id: str = None,
):
    """实时语音流WebSocket端点，实现智能断句和流式TTS"""
    # 生成会话ID（如果未提供）
    if not session_id:
        session_id = uuid.uuid4().hex
    
    session = None
    
    # 从 Cookie 中获取 username
    username = websocket.cookies.get("username")
    logger.info(f"Voice stream WebSocket connected: {session_id}, username: {username}")

    try:
        await websocket.accept()
        
        voice_stream_hub = get_voice_stream_hub()
        # Replace legacy LLM/TTS with Qwen realtime (tool calling retained via llm_service)
        llm_service = get_llm_service()  # still used for tool calls if needed
        tts_service = get_tts_service()  # fallback TTS if realtime audio not requested
        chat_storage = get_chat_storage()
        
        # 定义转录回调函数
        async def on_transcript(transcript: str):
            """处理转录文本，生成响应并合成语音"""
            try:
                logger.info(f"[Voice Stream] Received transcript: {transcript}")
                
                # 发送转录文本到客户端
                await session.send_message("transcript", {"text": transcript})
                
                # 保存用户消息到数据库（关联username）
                if username:
                    try:
                        user_message = ChatMessage(
                            message_id=uuid.uuid4().hex,
                            thread_id=session_id,
                            role="user",
                            text=transcript,
                            created_at=datetime.utcnow(),
                            language="zh",
                        )
                        chat_storage.save_message(user_message, username)
                        logger.info(f"[Voice Stream] Saved user message for username: {username}")
                    except Exception as e:
                        logger.error(f"[Voice Stream] Failed to save user message: {e}", exc_info=True)
                
                # 构建对话消息
                messages = [
                    {"role": "system", "content": "你是一个友好、有帮助的AI助手。请用简洁、自然的语言回答用户的问题。"},
                    {"role": "user", "content": transcript}
                ]
                
                # 断句缓冲区
                sentence_buffer = []
                full_response = ""
                segment_count = 0
                
                # 断句标点符号
                BREAK_PUNCTUATION = {"。", "！", "？", "!", "?", "；", ";", "\n"}
                MIN_SENTENCE_LENGTH = 12
                MAX_SENTENCE_LENGTH = 100
                
                def should_break_sentence(text: str) -> bool:
                    """判断是否应该断句"""
                    if len(text) < MIN_SENTENCE_LENGTH:
                        return False
                    
                    if text and text[-1] in BREAK_PUNCTUATION:
                        return True
                    
                    if "<emotion:" in text or "<lang:" in text or "<voice:" in text:
                        return True
                    
                    if len(text) >= MAX_SENTENCE_LENGTH:
                        for i in range(len(text) - 1, max(0, len(text) - 20), -1):
                            if text[i] in BREAK_PUNCTUATION:
                                return True
                        return True
                    
                    return False
                
                async def process_sentence(sentence: str, seg_id: int):
                    """处理一个句子：TTS + 发送"""
                    try:
                        logger.info(f"[Sentence {seg_id}] Processing: {sentence[:50]}...")
                        
                        # TTS 合成
                        async for audio_url in tts_service.synthesize_stream(
                            text=sentence,
                            voice="zhichu_emo",
                            locale="zh-CN",
                        ):
                            logger.info(f"[Sentence {seg_id}] TTS generated: {audio_url}")
                            
                            # 下载音频数据
                            audio_data = await fetch_audio_from_url(audio_url)
                            if audio_data:
                                # 添加到音频队列
                                await session.audio_queue_hook.add_audio(
                                    audio_data=audio_data,
                                    segment_id=seg_id,
                                    text=sentence
                                )
                                
                                # 发送音频 URL
                                await session.send_message("tts_audio", {
                                    "url": audio_url,
                                    "segment_id": seg_id,
                                    "text": sentence
                                })
                            
                    except Exception as e:
                        logger.error(f"[Sentence {seg_id}] TTS failed: {e}", exc_info=True)
                
                # Keepalive任务
                keepalive_task = None
                keepalive_running = True
                keepalive_count = 0
                
                async def send_keepalive():
                    """保持连接活跃"""
                    nonlocal keepalive_count
                    while keepalive_running:
                        await asyncio.sleep(2)
                        if keepalive_running:
                            try:
                                keepalive_count += 1
                                await session.send_status("generating")
                            except Exception as e:
                                logger.warning(f"Keepalive failed: {e}")
                                break
                
                try:
                    keepalive_task = asyncio.create_task(send_keepalive())
                    logger.info("[Voice Stream] Started LLM streaming with smart sentence breaking")
                    
                    # Qwen Omni Realtime now handles speech->text+audio directly on client side.
                    # Server fallback: still use llm_service for tool calls or text completion if needed.
                    async for chunk in llm_service.generate_stream(
                        prompt="",
                        messages=messages,
                        temperature=0.7
                    ):
                        sentence_buffer.append(chunk)
                        full_response += chunk
                        await session.send_message("response_chunk", {"text": chunk})
                        current_text = "".join(sentence_buffer)
                        if should_break_sentence(current_text):
                            segment_count += 1
                            logger.info(f"[Voice Stream] Breaking sentence #{segment_count}: {current_text[:30]}...")
                            await process_sentence(current_text.strip(), segment_count)
                            sentence_buffer.clear()
                    
                    # 处理剩余的文本
                    remaining_text = "".join(sentence_buffer).strip()
                    if remaining_text:
                        segment_count += 1
                        logger.info(f"[Voice Stream] Processing remaining text as segment #{segment_count}")
                        await process_sentence(remaining_text, segment_count)
                    
                    logger.info(f"[Voice Stream] LLM complete. Generated {segment_count} segments.")
                    
                    # 保存AI响应消息到数据库
                    if username:
                        try:
                            assistant_message = ChatMessage(
                                message_id=uuid.uuid4().hex,
                                thread_id=session_id,
                                role="assistant",
                                text=full_response,
                                created_at=datetime.utcnow(),
                                language="zh",
                            )
                            chat_storage.save_message(assistant_message, username)
                            logger.info(f"[Voice Stream] Saved assistant message for username: {username}")
                        except Exception as e:
                            logger.error(f"[Voice Stream] Failed to save assistant message: {e}", exc_info=True)
                    
                    # 发送完整响应
                    await session.send_response(full_response)
                    
                    # 发送完成标记
                    await session.send_message("generation_complete", {
                        "segments": segment_count,
                        "total_text": full_response
                    })
                    
                except Exception as e:
                    logger.error(f"[Voice Stream] Error in LLM streaming: {e}", exc_info=True)
                    await session.send_error(str(e))
                finally:
                    # 停止 keepalive
                    keepalive_running = False
                    if keepalive_task:
                        keepalive_task.cancel()
                        try:
                            await keepalive_task
                        except asyncio.CancelledError:
                            pass
                    logger.info(f"[Voice Stream] Stopped keepalive (sent {keepalive_count} pings)")
                
                await session.send_status("idle")
                return full_response
                
            except Exception as e:
                logger.error(f"Error in transcript callback: {e}", exc_info=True)
                await session.send_error(str(e))
                return ""
        
        # 创建会话
        session = await voice_stream_hub.create_session(
            websocket=websocket,
            session_id=session_id,
            on_transcript=on_transcript,
        )
        
        # 启动后台任务
        await session.start_background_tasks()
        
        # 发送就绪消息
        await session.send_message("ready", {"session_id": session_id})
        
        # 接收音频流
        while not session._closed:
            message = await websocket.receive()
            
            # 检查断开连接消息
            if message.get("type") == "websocket.disconnect":
                logger.info(f"Client disconnected: {session_id}")
                break
            
            if "bytes" in message:
                # 二进制音频数据
                audio_data = message["bytes"]
                await session.handle_audio_data(audio_data)
                
            elif "text" in message:
                # JSON 控制消息
                data = json.loads(message["text"])
                
                if data.get("type") == "stop":
                    logger.info("Received stop signal")
                    await session.flush_pending_audio("stop-signal")
                    await session.audio_queue_hook.interrupt()
                    break
                elif data.get("type") == "interrupt":
                    logger.info("Received interrupt signal")
                    await session.audio_queue_hook.interrupt()
                elif data.get("type") == "status":
                    status = await session.audio_queue_hook.get_status()
                    await session.send_message("queue_status", status)
                    
            else:
                logger.warning(f"Unknown message type: {message}")
        
    except WebSocketDisconnect:
        logger.info(f"Voice stream WebSocket disconnected: {session_id}")
    except RuntimeError as e:
        if "disconnect" in str(e).lower():
            logger.info(f"Voice stream connection closed: {session_id}")
        else:
            logger.error(f"Voice stream runtime error: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Voice stream error: {e}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        if session:
            try:
                await session.flush_pending_audio("connection-closed")
            except Exception as flush_error:
                logger.warning("Failed to flush audio on shutdown: %s", flush_error)
        if session_id:
            await voice_stream_hub.remove_session(session_id)
        try:
            await websocket.close()
        except:
            pass
