"""WebSocket endpoints."""

import asyncio
import base64
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict

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
# Voice Stream WebSocket - Qwen Omni Realtime
# ============================================================================

@router.websocket("/ws/voice-stream")
async def voice_stream_websocket(
    websocket: WebSocket,
    session_id: str = None,
):
    """
    实时语音流WebSocket端点，使用 Qwen-Omni-Realtime 全模态大模型。
    支持实时语音对话，音频直接转文本+音频输出，保留工具调用能力。
    """
    # 生成会话ID（如果未提供）
    if not session_id:
        session_id = uuid.uuid4().hex
    
    qwen_session = None
    
    # 从 Cookie 中获取 username
    username = websocket.cookies.get("username")
    logger.info(f"[Qwen Omni] Voice stream WebSocket connected: {session_id}, username: {username}")

    try:
        await websocket.accept()
        
        from ..services.agent.qwen_omni_realtime import (
            QwenOmniRealtimeHub,
            QwenOmniRealtimeConfig
        )
        
        chat_storage = get_chat_storage()
        
        # 定义转录回调：保存用户消息
        def on_transcript(transcript: str):
            """处理用户语音转录"""
            try:
                logger.info(f"[Qwen Omni] User transcript: {transcript}")
                
                # 保存用户消息到数据库（关联username）
                if username and transcript.strip():
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
                        logger.info(f"[Qwen Omni] Saved user message for username: {username}")
                    except Exception as e:
                        logger.error(f"[Qwen Omni] Failed to save user message: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"[Qwen Omni] Error in transcript callback: {e}", exc_info=True)
        
        # 定义音频回调：模型生成的音频直接转发（已包含在事件中）
        def on_audio(audio_b64: str):
            """处理模型生成的音频"""
            # Qwen Omni 会在事件处理中自动发送音频到客户端
            pass
        
        # 定义工具调用回调：保留 agent 工具调用能力
        def on_tool_call(tool_call: Dict[str, Any]) -> Any:
            """处理工具调用"""
            try:
                from ..services.agent import ConversationalAgent
                from ..dependencies import agent as global_agent
                
                function_name = tool_call.get("function", {}).get("name")
                arguments = tool_call.get("function", {}).get("arguments", {})
                
                logger.info(f"[Qwen Omni] Tool call: {function_name}({arguments})")
                
                # 这里可以集成现有的 agent 工具
                # 示例：调用记忆工具、情绪识别等
                # result = global_agent.execute_tool(function_name, arguments)
                
                # 临时返回一个占位结果
                result = {"status": "success", "message": f"工具 {function_name} 已执行"}
                logger.info(f"[Qwen Omni] Tool result: {result}")
                return result
                
            except Exception as e:
                logger.error(f"[Qwen Omni] Tool call error: {e}", exc_info=True)
                return {"status": "error", "message": str(e)}
        
        # 创建 Qwen Omni Realtime 配置
        config = QwenOmniRealtimeConfig(
            model="qwen-omni-turbo-realtime",
            voice="Chelsie",  # 千雪音色
            enable_vad=True,
            instructions="你是一个友好、有帮助的AI助手。请用简洁、自然的语言回答用户的问题。"
        )
        
        # 创建会话管理器
        qwen_hub = QwenOmniRealtimeHub(config=config)
        
        # 创建 Qwen Omni 会话
        qwen_session = await qwen_hub.create_session(
            websocket=websocket,
            session_id=session_id,
            on_transcript=on_transcript,
            on_audio=on_audio,
            on_tool_call=on_tool_call
        )
        
        logger.info(f"[Qwen Omni] Session {session_id} ready")
        
        # 发送就绪消息
        await websocket.send_json({
            "type": "ready",
            "session_id": session_id,
            "model": "qwen-omni-turbo-realtime"
        })
        
        # 接收音频流和控制消息
        # 支持多轮对话：当 Qwen Omni 会话关闭后自动重建
        while True:
            # 检查会话是否关闭，如果关闭则重建
            if qwen_session.is_closed:
                logger.info(f"[Qwen Omni] Session closed, recreating for next turn...")
                qwen_session = await qwen_hub.create_session(
                    websocket=websocket,
                    session_id=f"{session_id}_{uuid.uuid4().hex[:8]}",  # 新的子会话 ID
                    on_transcript=on_transcript,
                    on_audio=on_audio,
                    on_tool_call=on_tool_call
                )
                await websocket.send_json({
                    "type": "ready",
                    "session_id": session_id,
                    "message": "Ready for next turn"
                })
            
            try:
                message = await websocket.receive()
            except WebSocketDisconnect:
                logger.info(f"[Qwen Omni] Client disconnected: {session_id}")
                break
            except RuntimeError as e:
                if "disconnect" in str(e).lower():
                    logger.info(f"[Qwen Omni] Connection closed: {session_id}")
                    break
                raise
            
            # 检查断开连接消息
            if message.get("type") == "websocket.disconnect":
                logger.info(f"[Qwen Omni] Client disconnected: {session_id}")
                break
            
            if "bytes" in message:
                # 二进制音频数据 - 转换为 Base64 并发送到 Qwen Omni
                audio_data = message["bytes"]
                logger.debug(f"[Qwen Omni] Received audio chunk: {len(audio_data)} bytes")
                audio_b64 = base64.b64encode(audio_data).decode('ascii')
                await qwen_session.append_audio(audio_b64)
                
            elif "text" in message:
                # JSON 控制消息
                data = json.loads(message["text"])
                msg_type = data.get("type")
                
                if msg_type == "stop" or msg_type == "close":
                    logger.info(f"[Qwen Omni] Received {msg_type} signal")
                    break
                    
                elif msg_type == "image":
                    # 支持图片输入（视频通话场景）
                    image_b64 = data.get("image")
                    if image_b64:
                        await qwen_session.append_image(image_b64)
                        logger.info(f"[Qwen Omni] Appended image to session")
                
                elif msg_type == "config":
                    # 动态配置更新（如果需要）
                    logger.info(f"[Qwen Omni] Config update request: {data}")
                    
            else:
                logger.warning(f"[Qwen Omni] Unknown message type: {message}")
        
    except WebSocketDisconnect:
        logger.info(f"[Qwen Omni] WebSocket disconnected: {session_id}")
    except RuntimeError as e:
        if "disconnect" in str(e).lower():
            logger.info(f"[Qwen Omni] Connection closed: {session_id}")
        else:
            logger.error(f"[Qwen Omni] Runtime error: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"[Qwen Omni] Error: {e}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        if qwen_session:
            try:
                await qwen_session.close()
            except Exception as close_error:
                logger.warning(f"[Qwen Omni] Failed to close session: {close_error}")
        if qwen_hub and session_id:
            try:
                await qwen_hub.remove_session(session_id)
            except Exception as remove_error:
                logger.warning(f"[Qwen Omni] Failed to remove session: {remove_error}")
        try:
            await websocket.close()
        except:
            pass
