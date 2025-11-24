"""Chat-related routes."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException
from fastapi.responses import Response

from ..dependencies import get_chat_service, get_chat_storage
from ..schemas import ChatMessage, ChatMessageIn, ChatThreadCreateIn, ChatThreadOut
from ..services.chat.service import ChatService
from ..services.chat.storage import ChatStorage

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
    
    storage = get_chat_storage()
    messages = storage.get_recent_messages_by_username(username, limit)
    return messages


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
