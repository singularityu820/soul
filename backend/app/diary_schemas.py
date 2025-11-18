from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DiaryEntry(BaseModel):
    """日记条目数据模型"""
    diary_id: str = Field(description="日记唯一标识符")
    user_id: str = Field(description="用户ID")
    title: str = Field(description="日记标题")
    content: str = Field(description="日记完整内容")
    preview: str = Field(description="日记预览内容（前几十个字）")
    entry_number: int = Field(description="日记序号（第几篇日记）")
    emotion_tags: List[str] = Field(default_factory=list, description="情绪标签")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")


class DiaryEntryCreate(BaseModel):
    """创建日记条目的请求模型"""
    user_id: str = Field(description="用户ID")
    title: str = Field(description="日记标题")
    content: str = Field(description="日记完整内容")
    emotion_tags: List[str] = Field(default_factory=list, description="情绪标签")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")


class DiaryEntryUpdate(BaseModel):
    """更新日记条目的请求模型"""
    title: Optional[str] = Field(None, description="日记标题")
    content: Optional[str] = Field(None, description="日记完整内容")
    emotion_tags: Optional[List[str]] = Field(None, description="情绪标签")
    metadata: Optional[Dict[str, Any]] = Field(None, description="额外元数据")


class DiaryEntryOut(BaseModel):
    """日记条目输出模型"""
    diary_id: str = Field(description="日记唯一标识符")
    user_id: str = Field(description="用户ID")
    title: str = Field(description="日记标题")
    preview: str = Field(description="日记预览内容（前几十个字）")
    entry_number: int = Field(description="日记序号（第几篇日记）")
    emotion_tags: List[str] = Field(default_factory=list, description="情绪标签")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class DiaryListOut(BaseModel):
    """日记列表输出模型"""
    diaries: List[DiaryEntryOut] = Field(description="日记列表")
    total_count: int = Field(description="总日记数")
    user_id: str = Field(description="用户ID")


class DiaryStatsOut(BaseModel):
    """日记统计信息输出模型"""
    total_diaries: int = Field(description="总日记数")
    latest_diary: Optional[DiaryEntryOut] = Field(None, description="最新日记")
    emotion_tag_counts: Dict[str, int] = Field(default_factory=dict, description="情绪标签统计")
    user_id: str = Field(description="用户ID")