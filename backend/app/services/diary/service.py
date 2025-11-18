from __future__ import annotations

import logging
from typing import List, Optional

from ...diary_schemas import DiaryEntry, DiaryEntryCreate, DiaryEntryUpdate, DiaryEntryOut
from .storage import DiaryStorageService

logger = logging.getLogger(__name__)


class DiaryService:
    """日记服务类，提供日记相关业务逻辑"""
    
    def __init__(self, storage: DiaryStorageService = None) -> None:
        """初始化日记服务
        
        Args:
            storage: 日记存储服务，默认创建新实例
        """
        self.storage = storage or DiaryStorageService()
    
    def create_diary(self, diary_create: DiaryEntryCreate) -> DiaryEntryOut:
        """创建新的日记条目
        
        Args:
            diary_create: 日记创建请求
            
        Returns:
            创建的日记条目输出模型
        """
        diary = self.storage.create_diary(diary_create)
        logger.info(f"Created diary {diary.diary_id} for user {diary.user_id}")
        
        return DiaryEntryOut(
            diary_id=diary.diary_id,
            user_id=diary.user_id,
            title=diary.title,
            preview=diary.preview,
            entry_number=diary.entry_number,
            emotion_tags=diary.emotion_tags,
            created_at=diary.created_at,
            updated_at=diary.updated_at
        )
    
    def get_diary(self, diary_id: str) -> Optional[DiaryEntry]:
        """根据ID获取日记条目
        
        Args:
            diary_id: 日记ID
            
        Returns:
            日记条目，如果不存在则返回None
        """
        return self.storage.get_diary(diary_id)
    
    def update_diary(self, diary_id: str, diary_update: DiaryEntryUpdate) -> Optional[DiaryEntry]:
        """更新日记条目
        
        Args:
            diary_id: 日记ID
            diary_update: 日记更新请求
            
        Returns:
            更新后的日记条目，如果不存在则返回None
        """
        diary = self.storage.update_diary(diary_id, diary_update)
        if diary:
            logger.info(f"Updated diary {diary_id}")
        
        return diary
    
    def delete_diary(self, diary_id: str) -> bool:
        """删除日记条目
        
        Args:
            diary_id: 日记ID
            
        Returns:
            是否成功删除
        """
        success = self.storage.delete_diary(diary_id)
        if success:
            logger.info(f"Deleted diary {diary_id}")
        
        return success
    
    def get_user_diaries(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0,
        order_by: str = "created_at DESC"
    ) -> List[DiaryEntryOut]:
        """获取用户的日记列表
        
        Args:
            user_id: 用户ID
            limit: 返回数量限制
            offset: 偏移量
            order_by: 排序方式
            
        Returns:
            日记条目输出模型列表
        """
        diaries = self.storage.get_user_diaries(user_id, limit, offset, order_by)
        
        return [
            DiaryEntryOut(
                diary_id=diary.diary_id,
                user_id=diary.user_id,
                title=diary.title,
                preview=diary.preview,
                entry_number=diary.entry_number,
                emotion_tags=diary.emotion_tags,
                created_at=diary.created_at,
                updated_at=diary.updated_at
            )
            for diary in diaries
        ]
    
    def get_latest_diary(self, user_id: str) -> Optional[DiaryEntryOut]:
        """获取用户的最新日记
        
        Args:
            user_id: 用户ID
            
        Returns:
            最新日记条目输出模型，如果不存在则返回None
        """
        diary = self.storage.get_latest_diary(user_id)
        
        if not diary:
            return None
        
        return DiaryEntryOut(
            diary_id=diary.diary_id,
            user_id=diary.user_id,
            title=diary.title,
            preview=diary.preview,
            entry_number=diary.entry_number,
            emotion_tags=diary.emotion_tags,
            created_at=diary.created_at,
            updated_at=diary.updated_at
        )
    
    def get_diary_count(self, user_id: str) -> int:
        """获取用户的日记总数
        
        Args:
            user_id: 用户ID
            
        Returns:
            日记总数
        """
        return self.storage.get_diary_count(user_id)
    
    def search_diaries(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
        offset: int = 0
    ) -> List[DiaryEntryOut]:
        """搜索用户的日记
        
        Args:
            user_id: 用户ID
            query: 搜索关键词
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            匹配的日记条目输出模型列表
        """
        diaries = self.storage.search_diaries(user_id, query, limit, offset)
        
        return [
            DiaryEntryOut(
                diary_id=diary.diary_id,
                user_id=diary.user_id,
                title=diary.title,
                preview=diary.preview,
                entry_number=diary.entry_number,
                emotion_tags=diary.emotion_tags,
                created_at=diary.created_at,
                updated_at=diary.updated_at
            )
            for diary in diaries
        ]
    
    def get_emotion_tag_counts(self, user_id: str) -> dict[str, int]:
        """获取用户情绪标签统计
        
        Args:
            user_id: 用户ID
            
        Returns:
            情绪标签及其使用次数的字典
        """
        return self.storage.get_emotion_tag_counts(user_id)
    
    def get_diary_previews_with_numbers(self, user_id: str, limit: int = 5) -> List[dict]:
        """获取用户最新日记的预览内容和序号，专门用于前端显示
        
        Args:
            user_id: 用户ID
            limit: 返回数量限制，默认5篇
            
        Returns:
            包含日记预览和序号的字典列表
        """
        diaries = self.storage.get_user_diaries(
            user_id=user_id,
            limit=limit,
            offset=0,
            order_by="created_at DESC"
        )
        
        return [
            {
                "diary_id": diary.diary_id,
                "entry_number": diary.entry_number,
                "preview": diary.preview,
                "title": diary.title,
                "created_at": diary.created_at
            }
            for diary in diaries
        ]