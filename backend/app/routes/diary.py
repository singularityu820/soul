from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

from ..diary_schemas import DiaryEntry, DiaryEntryCreate, DiaryEntryUpdate, DiaryEntryOut
from ..services.diary import DiaryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diary", tags=["diary"])


def get_diary_service() -> DiaryService:
    """依赖注入：获取日记服务实例"""
    return DiaryService()


@router.post("/", response_model=DiaryEntryOut, status_code=201)
async def create_diary(
    diary_create: DiaryEntryCreate,
    diary_service: DiaryService = Depends(get_diary_service)
):
    """创建新的日记条目"""
    try:
        return diary_service.create_diary(diary_create)
    except Exception as e:
        logger.error(f"Error creating diary: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create diary")


@router.get("/{diary_id}", response_model=DiaryEntry)
async def get_diary(
    diary_id: str,
    diary_service: DiaryService = Depends(get_diary_service)
):
    """根据ID获取日记条目"""
    diary = diary_service.get_diary(diary_id)
    if not diary:
        raise HTTPException(status_code=404, detail="Diary not found")
    return diary


@router.put("/{diary_id}", response_model=DiaryEntry)
async def update_diary(
    diary_id: str,
    diary_update: DiaryEntryUpdate,
    diary_service: DiaryService = Depends(get_diary_service)
):
    """更新日记条目"""
    diary = diary_service.update_diary(diary_id, diary_update)
    if not diary:
        raise HTTPException(status_code=404, detail="Diary not found")
    return diary


@router.delete("/{diary_id}", status_code=204)
async def delete_diary(
    diary_id: str,
    diary_service: DiaryService = Depends(get_diary_service)
):
    """删除日记条目"""
    success = diary_service.delete_diary(diary_id)
    if not success:
        raise HTTPException(status_code=404, detail="Diary not found")


@router.get("/user/{user_id}", response_model=List[DiaryEntryOut])
async def get_user_diaries(
    user_id: str,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    order_by: str = Query("created_at DESC", regex="^(created_at|entry_number) (ASC|DESC)$"),
    diary_service: DiaryService = Depends(get_diary_service)
):
    """获取用户的日记列表"""
    return diary_service.get_user_diaries(user_id, limit, offset, order_by)


@router.get("/user/{user_id}/latest", response_model=DiaryEntryOut)
async def get_latest_diary(
    user_id: str,
    diary_service: DiaryService = Depends(get_diary_service)
):
    """获取用户的最新日记"""
    diary = diary_service.get_latest_diary(user_id)
    if not diary:
        raise HTTPException(status_code=404, detail="No diaries found for user")
    return diary


@router.get("/user/{user_id}/count")
async def get_diary_count(
    user_id: str,
    diary_service: DiaryService = Depends(get_diary_service)
):
    """获取用户的日记总数"""
    count = diary_service.get_diary_count(user_id)
    return {"count": count}


@router.get("/user/{user_id}/search", response_model=List[DiaryEntryOut])
async def search_diaries(
    user_id: str,
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    diary_service: DiaryService = Depends(get_diary_service)
):
    """搜索用户的日记"""
    return diary_service.search_diaries(user_id, query, limit, offset)


@router.get("/user/{user_id}/emotion-tags")
async def get_emotion_tag_counts(
    user_id: str,
    diary_service: DiaryService = Depends(get_diary_service)
):
    """获取用户情绪标签统计"""
    return diary_service.get_emotion_tag_counts(user_id)


@router.get("/user/{user_id}/previews")
async def get_diary_previews_with_numbers(
    user_id: str,
    limit: int = Query(5, ge=1, le=20),
    diary_service: DiaryService = Depends(get_diary_service)
):
    """获取用户最新日记的预览内容和序号，专门用于前端显示"""
    previews = diary_service.get_diary_previews_with_numbers(user_id, limit)
    
    # 如果没有日记，返回空列表
    if not previews:
        return []
    
    return {
        "user_id": user_id,
        "previews": previews,
        "total_count": diary_service.get_diary_count(user_id)
    }