"""WebSocket endpoints."""

import asyncio
import base64
import json
import logging
import os
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
    get_speech_tool,
)
from ..dependencies import agent as global_agent, memory as agent_memory
from ..services.chat.realtime_storage import RealtimeTranscriptStorage
from ..schemas import ChatEvent, ChatMessage, PipelineEvent
from ..schemas import EmotionState
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
    logger.info(f"WebSocket chat connection established for thread_id: {thread_id}")
    queue = await chat.subscribe()
    logger.info(f"Subscribed to chat service, queue size: {queue.qsize()}")

    try:
        # 发送连接确认消息，包含WebSocket连接标识
        await websocket.send_json({
            "type": "connection_established",
            "source": "websocket",
            "thread_id": thread_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        if thread_id:
            history = await chat.history(thread_id)
            logger.info(f"Found {len(history)} messages in history for thread {thread_id}")
            for message in history:
                # 只发送非stream_chunk类型的消息，避免与HTTP流式响应冲突
                if hasattr(message, 'type') and message.type == "stream_chunk":
                    continue
                    
                await websocket.send_json(
                    jsonable_encoder(ChatEvent(
                        thread_id=thread_id, 
                        message=message,
                        source="websocket"  # 添加来源标识
                    ))
                )
                logger.debug(f"Sent history message: {message.role} - {message.text[:30]}...")

        while True:
            event = await queue.get()
            logger.debug(f"Received event from queue: {event.thread_id}, type: {event.type}")
            if thread_id and event.thread_id != thread_id:
                logger.debug(f"Skipping event for different thread: {event.thread_id}")
                continue
                
            # 跳过stream_chunk类型的事件，这些应该通过HTTP流式响应处理
            if hasattr(event, 'type') and event.type == "stream_chunk":
                logger.debug(f"Skipping stream_chunk event to avoid conflict with HTTP streaming")
                continue
                
            # 添加WebSocket来源标识，帮助前端区分消息来源
            if hasattr(event, 'message'):
                event.source = "websocket"
            
            await websocket.send_json(jsonable_encoder(event))
            logger.debug(f"Sent event to WebSocket: {event.thread_id}")
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
    
    # 从 Cookie 中获取 username；如未提供则回退到 query param（前端可能把 username 作为 query 参数传入）
    username = websocket.cookies.get("username") or websocket.query_params.get("username")
    logger.info(f"[Qwen Omni] Voice stream WebSocket connected: {session_id}, username: {username}")

    try:
        await websocket.accept()
        
        from ..services.agent.qwen_omni_realtime import (
            QwenOmniRealtimeHub,
            QwenOmniRealtimeConfig
        )
        
        chat_storage = get_chat_storage()
        realtime_storage = RealtimeTranscriptStorage()
        speech_tool = get_speech_tool()

        # 定义转录回调：将实时转录持久化到独立表，不触发 ChatService/agent 的后续处理
        def on_transcript(transcript: str):
            """处理用户语音转录

            持久化到 `realtime_transcripts`，以便保留通话记录但避免触发聊天服务的 agent 跟进。
            若需要同时将实时转录写入主聊天存储以供历史查看/迁移，可设置 `SAVE_REALTIME_TRANSCRIPTS=1`。
            """
            try:
                logger.info(f"[Qwen Omni] User transcript: {transcript}")

                if transcript and transcript.strip():
                    try:
                        # always persist to dedicated realtime storage
                        rt_id = uuid.uuid4().hex
                        realtime_storage.save_transcript(rt_id, session_id, "user", transcript, {"username": username})
                        logger.info(f"[Qwen Omni] Persisted realtime transcript id={rt_id} session={session_id}")
                    except Exception as e:
                        logger.error(f"[Qwen Omni] Failed to persist realtime transcript: {e}", exc_info=True)

                    # optional: also save to main chat storage when explicit env var is set
                    save_flag = os.environ.get("SAVE_REALTIME_TRANSCRIPTS", "0") == "1"
                    if save_flag and username:
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
                            logger.info(f"[Qwen Omni] Also saved user message to chat storage for username: {username}")
                        except Exception as e:
                            logger.error(f"[Qwen Omni] Failed to save user message to chat storage: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"[Qwen Omni] Error in transcript callback: {e}", exc_info=True)
        
        # 定义音频回调：模型生成的音频直接转发（已包含在事件中）
        def on_audio(audio_b64: str):
            """处理模型生成的音频"""
            # Qwen Omni 会在事件处理中自动发送音频到客户端
            pass

        # 定义工具调用回调：将模型的工具调用映射到本地 agent/memory 功能
        def on_tool_call(tool_call: Dict[str, Any]) -> Any:
            """处理模型请求的工具调用（同步返回结果）。

            支持的函数示例：
            - memory.add_dialogue
            - memory.add_event
            - memory.search
            - memory.snapshot
            - agent.respond_with_context  (会调用 agent 并等待结果，返回简单结构)
            """
            try:
                function = tool_call.get("function", {})
                function_name = function.get("name")
                arguments = function.get("arguments", {}) or {}

                logger.info(f"[Qwen Omni] Tool call requested: {function_name} args={arguments}")

                # 记忆相关操作（同步）
                if function_name == "memory.add_dialogue":
                    speaker = arguments.get("speaker", "user")
                    utterance = arguments.get("utterance", "")
                    record_id = agent_memory.add_dialogue(speaker, utterance)
                    return {"status": "ok", "id": record_id}

                if function_name == "memory.add_event":
                    text = arguments.get("text")
                    tags = arguments.get("tags")
                    metadata = arguments.get("metadata")
                    record_id = agent_memory.add_event(text, tags=tags, metadata=metadata)
                    return {"status": "ok", "id": record_id}

                if function_name == "memory.search":
                    query = arguments.get("query", "")
                    limit = int(arguments.get("limit", 5))
                    items = agent_memory.search(query, limit=limit)
                    # Convert to serializable form
                    result = []
                    for it in items:
                        try:
                            result.append({"id": getattr(it, 'record_id', None), "content": getattr(it, 'content', str(it))})
                        except Exception:
                            result.append({"content": str(it)})
                    return {"status": "ok", "results": result}

                if function_name == "memory.snapshot":
                    snap = agent_memory.snapshot()
                    return {"status": "ok", "snapshot": snap}

                # agent 生成回复（异步）：我们同步等待结果（超时保护）
                if function_name == "agent.respond":
                    user_text = arguments.get("user_text")
                    # use latest pipeline emotion if available
                    emotion = None
                    try:
                        pipeline = get_pipeline()
                        # get_pipeline is async in dependencies; pipeline is globally available too
                        emotion = None
                    except Exception:
                        emotion = None

                    loop = asyncio.get_event_loop()
                    try:
                        fut = asyncio.run_coroutine_threadsafe(
                            global_agent.respond_with_context(emotion, user_text=user_text), loop
                        )
                        agent_message = fut.result(timeout=10)
                        # Record agent message into memory
                        try:
                            agent_memory.record_agent_message(agent_message.text, proactive=False)
                        except Exception:
                            pass
                        # Return key fields
                        return {"status": "ok", "text": agent_message.text, "audio_reference": agent_message.audio_reference}
                    except Exception as e:
                        logger.exception(f"[Qwen Omni] agent.respond failed: {e}")
                        return {"status": "error", "message": str(e)}

                # 默认占位：返回一个简单成功响应
                return {"status": "ok", "message": f"Executed {function_name}"}

            except Exception as e:
                logger.exception(f"[Qwen Omni] Tool call error: {e}")
                return {"status": "error", "message": str(e)}
        
        # (使用上面定义的 on_tool_call，将模型的工具调用映射到本地 agent/memory 功能)
        
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
        # 回调：当模型生成最终文本回复时，持久化为 realtime_transcripts（role=assistant）
        def _on_model_response(text: str):
            try:
                if text and text.strip():
                    rt_id = uuid.uuid4().hex
                    try:
                        realtime_storage.save_transcript(rt_id, session_id, "assistant", text, {"username": username})
                        logger.info(f"[Qwen Omni] Persisted assistant transcript id={rt_id} session={session_id}")
                    except Exception as e:
                        logger.error(f"[Qwen Omni] Failed to persist assistant transcript: {e}", exc_info=True)
            except Exception as e:
                logger.exception(f"Error in on_model_response: {e}")

        qwen_session = await qwen_hub.create_session(
            websocket=websocket,
            session_id=session_id,
            on_transcript=on_transcript,
            on_audio=on_audio,
            on_tool_call=on_tool_call,
            on_response=_on_model_response,
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
                # 异步发送音频到 speech emotion tool 并广播到 pipeline（用于前端 EEG 显示）
                async def _process_speech_emotion(chunk: bytes):
                    try:
                        await speech_tool.update_from_audio(chunk)
                        ch = await speech_tool.analyze()
                        # 构造一个简化的 EmotionState 并广播
                        emotion_state = EmotionState(
                            label=ch.label,
                            confidence=ch.confidence,
                            mood_score=ch.mood_score,
                            components=[ch],
                        )
                        try:
                            pipeline = await get_pipeline()
                            await pipeline._broadcast(PipelineEvent(emotion=emotion_state))
                            logger.debug(f"[Qwen Omni] Broadcasted speech emotion: {ch.label}")
                        except Exception as e:
                            logger.exception(f"[Qwen Omni] Failed broadcasting pipeline event: {e}")
                    except Exception as e:
                        logger.exception(f"[Qwen Omni] Speech emotion processing failed: {e}")

                asyncio.create_task(_process_speech_emotion(audio_data))
                
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

