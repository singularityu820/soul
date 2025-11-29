"""Chat-related routes."""

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse

from ..dependencies import get_chat_service, get_chat_storage
from ..schemas import ChatMessage, ChatMessageIn, ChatThreadCreateIn, ChatThreadOut
from ..services.chat.service import ChatService
from ..services.chat.storage import ChatStorage
from ..services.chat.realtime_storage import RealtimeTranscriptStorage
from datetime import datetime

router = APIRouter()


@router.get("/chat/threads", response_model=list[ChatThreadOut])
async def list_threads(chat: ChatService = Depends(get_chat_service)) -> list[ChatThreadOut]:
    return await chat.list_threads()


@router.post("/chat/threads", response_model=ChatThreadOut, status_code=201)
async def create_thread(
    payload: ChatThreadCreateIn,
    chat: ChatService = Depends(get_chat_service),
) -> ChatThreadOut:
    return await chat.create_thread(payload.title, payload.participants)


@router.get("/chat/threads/{thread_id}", response_model=ChatThreadOut)
async def get_thread(
    thread_id: str,
    chat: ChatService = Depends(get_chat_service),
) -> ChatThreadOut:
    thread = await chat.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@router.delete("/chat/threads/{thread_id}", status_code=204)
async def delete_thread(
    thread_id: str,
    chat: ChatService = Depends(get_chat_service),
) -> Response:
    success = await chat.delete_thread(thread_id)
    if not success:
        raise HTTPException(status_code=404, detail="Thread not found")
    return Response(status_code=204)


@router.get("/chat/threads/{thread_id}/messages", response_model=list[ChatMessage])
async def get_messages(
    thread_id: str,
    limit: int = 100,
    chat: ChatService = Depends(get_chat_service),
) -> list[ChatMessage]:
    thread = await chat.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return await chat.history(thread_id, limit=limit)


@router.get("/chat/recent-messages", response_model=list[ChatMessage])
async def get_recent_messages_by_username(
    username: str | None = Cookie(None),
    limit: int = 3,
) -> list[ChatMessage]:
    """
    获取当前登录用户最近的聊天消息
    从cookie中读取username，返回该用户最近的limit条消息
    """
    if not username:
        raise HTTPException(status_code=401, detail="Username not found in cookie")
    
    # 使用 RealtimeTranscriptStorage 替代历史 ChatStorage，返回最近的实时转录
    rt_storage = RealtimeTranscriptStorage()
    rt_items = rt_storage.get_transcripts_by_username(username, limit)

    out = []
    for item in rt_items:
        try:
            created_at = datetime.fromisoformat(item["created_at"]) if isinstance(item["created_at"], str) else item["created_at"]
        except Exception:
            created_at = datetime.utcnow()

        role = item.get("role") or "user"
        # schema uses 'agent' instead of 'assistant'
        if role == "assistant":
            role = "agent"

        out.append(
            ChatMessage(
                message_id=item.get("id") or uuid.uuid4().hex,
                thread_id=item.get("session_id") or "",
                role=role,
                text=item.get("text") or "",
                created_at=created_at,
                language="zh",
                username=username,
            )
        )

    return out


@router.post("/chat/threads/{thread_id}/messages", response_model=ChatMessage, status_code=201)
async def post_message(
    thread_id: str,
    payload: ChatMessageIn,
    username: str | None = Cookie(None),
    chat: ChatService = Depends(get_chat_service),
) -> ChatMessage:
    thread = await chat.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    message = await chat.add_user_message(thread_id, payload.text, payload.language)
    
    # 保存消息到数据库，关联username
    if username:
        storage = get_chat_storage()
        storage.save_message(message, username)
    
    return message


@router.post("/chat/threads/{thread_id}/text-messages", response_model=ChatMessage, status_code=201)
async def post_text_message(
    thread_id: str,
    payload: ChatMessageIn,
    username: str | None = Cookie(None),
    chat: ChatService = Depends(get_chat_service),
) -> ChatMessage:
    """
    独立文本聊天消息接口，不依赖情绪识别系统
    """
    thread = await chat.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    message = await chat.add_user_message(thread_id, payload.text, payload.language, use_text_chat=True)
    
    # 保存消息到数据库，使用特殊的用户名前缀区分文本聊天记录
    # 这样在获取普通用户聊天记录时就不会包含文本聊天记录
    text_chat_username = f"text_chat_{thread_id}"
    storage = get_chat_storage()
    storage.save_message(message, text_chat_username)
    
    return message


@router.post("/chat/threads/{thread_id}/text-messages-stream")
async def post_text_message_stream(
    thread_id: str,
    payload: ChatMessageIn,
    username: str | None = Cookie(None),
    chat: ChatService = Depends(get_chat_service),
):
    """
    独立文本聊天消息流式响应接口，使用Server-Sent Events (SSE)格式
    """
    thread = await chat.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    # 直接调用_append_message添加用户消息，不触发_text_chat_follow_up函数
    # 从_conversation_history获取历史消息时需要内存中的消息
    user_message = await chat._append_message(
        thread_id=thread_id,
        role="user",
        text=payload.text,
        language=payload.language,
        emotion=None,
        agent_message=None,
    )
    
    # 使用特殊的用户名前缀区分文本聊天记录
    text_chat_username = f"text_chat_{thread_id}"
    storage = get_chat_storage()
    storage.save_message(user_message, text_chat_username)
    
    async def generate():
        """生成SSE格式的流式响应"""
        try:
            # 流式生成AI回复
            async for chunk in chat.stream_text_chat_response(thread_id, payload.text, payload.language):
                # 发送每个文本块
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            
            # 发送完成事件
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            # 发送错误事件
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用Nginx缓冲
        }
    )


@router.get("/chat/user/{username}/recent")
async def get_recent_messages_for_user(
    username: str,
    limit: int = 3,
) -> dict:
    """返回给定用户名的最近聊天消息与实时转录（合并、按时间降序）。

    返回格式：{"messages": [ChatMessageLike, ...]}
    """
    # 新架构：仅从 RealtimeTranscriptStorage 获取最近聊天记录（包含 user/assistant）
    rt_storage = RealtimeTranscriptStorage()
    rt_items = rt_storage.get_transcripts_by_username(username, limit)

    # 将实时转录转换为与 ChatMessage 兼容的 dict
    rt_msgs = []
    for item in rt_items:
        try:
            created_at = datetime.fromisoformat(item["created_at"]) if isinstance(item["created_at"], str) else item["created_at"]
        except Exception:
            created_at = datetime.utcnow()
        role = item.get("role") or "user"
        if role == "assistant":
            role = "agent"
        rt_msgs.append({
            "message_id": item["id"],
            "thread_id": item["session_id"],
            "role": role,
            "text": item["text"],
            "created_at": created_at,
            "language": "zh",
            "username": username,
        })

    # 合并并按 created_at 降序（最近的在前），限制总条数为 limit
    # Only realtime messages
    combined = rt_msgs
    # sort by created_at desc
    def _created_at_key(x):
        v = x.get("created_at")
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v)
            except Exception:
                return datetime.utcnow()
        if isinstance(v, datetime):
            return v
        return datetime.utcnow()

    combined.sort(key=_created_at_key, reverse=True)
    combined = combined[:limit]

    return {"messages": combined}
