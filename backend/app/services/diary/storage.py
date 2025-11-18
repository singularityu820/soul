from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ...diary_schemas import DiaryEntry, DiaryEntryCreate, DiaryEntryUpdate, DiaryEntryOut

logger = logging.getLogger(__name__)


class DiaryStorageService:
    """日记存储服务，使用SQLite数据库"""
    
    def __init__(self, db_path: str = None) -> None:
        """初始化日记存储服务
        
        Args:
            db_path: SQLite数据库路径，默认使用backend/storage/diary.sqlite3
        """
        if db_path is None:
            # 默认存储在backend/storage/diary.sqlite3
            # 从当前文件位置找到backend目录
            backend_dir = Path(__file__).parent.parent.parent
            db_path = backend_dir / "storage" / "diary.sqlite3"
            
            # 确保storage目录存在
            storage_dir = backend_dir / "storage"
            storage_dir.mkdir(exist_ok=True)
        
        self.db_path = str(db_path)
        self._local = threading.local()
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接"""
        if not hasattr(self._local, "connection"):
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    def _init_db(self) -> None:
        """初始化数据库表结构"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 创建日记表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diaries (
                diary_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                preview TEXT NOT NULL,
                entry_number INTEGER NOT NULL,
                emotion_tags TEXT,  -- JSON格式存储标签列表
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                metadata TEXT  -- JSON格式存储元数据
            )
        """)
        
        # 创建用户日记计数表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_diary_counts (
                user_id TEXT PRIMARY KEY,
                count INTEGER NOT NULL DEFAULT 0
            )
        """)
        
        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_diaries_user_id ON diaries(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_diaries_created_at ON diaries(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_diaries_entry_number ON diaries(user_id, entry_number)")
        
        conn.commit()
        logger.info(f"Diary database initialized at {self.db_path}")
    
    def _get_next_entry_number(self, user_id: str) -> int:
        """获取用户的下一篇日记序号"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 从计数表获取
        cursor.execute("SELECT count FROM user_diary_counts WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if row:
            next_number = row["count"] + 1
            cursor.execute(
                "UPDATE user_diary_counts SET count = ? WHERE user_id = ?",
                (next_number, user_id)
            )
        else:
            # 如果计数表中没有记录，从日记表中查询
            cursor.execute(
                "SELECT MAX(entry_number) as max_number FROM diaries WHERE user_id = ?",
                (user_id,)
            )
            max_row = cursor.fetchone()
            next_number = (max_row["max_number"] or 0) + 1
            
            # 插入计数表
            cursor.execute(
                "INSERT INTO user_diary_counts (user_id, count) VALUES (?, ?)",
                (user_id, next_number)
            )
        
        conn.commit()
        return next_number
    
    def _generate_preview(self, content: str, preview_length: int = 50) -> str:
        """生成日记预览内容
        
        Args:
            content: 日记完整内容
            preview_length: 预览长度（字符数）
            
        Returns:
            预览内容
        """
        # 移除多余的空白字符
        content = ' '.join(content.split())
        
        if len(content) <= preview_length:
            return content
        
        # 截取指定长度并确保不在单词中间截断
        preview = content[:preview_length]
        last_space = preview.rfind(' ')
        
        if last_space > preview_length * 0.8:  # 如果最后一个空格位置合理
            preview = preview[:last_space]
        
        return preview + "..."
    
    def create_diary(self, diary_create: DiaryEntryCreate) -> DiaryEntry:
        """创建新的日记条目
        
        Args:
            diary_create: 日记创建请求
            
        Returns:
            创建的日记条目
        """
        import json
        import uuid
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        diary_id = uuid.uuid4().hex
        entry_number = self._get_next_entry_number(diary_create.user_id)
        preview = self._generate_preview(diary_create.content)
        now = datetime.utcnow()
        
        cursor.execute("""
            INSERT INTO diaries (
                diary_id, user_id, title, content, preview, entry_number,
                emotion_tags, created_at, updated_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            diary_id,
            diary_create.user_id,
            diary_create.title,
            diary_create.content,
            preview,
            entry_number,
            json.dumps(diary_create.emotion_tags),
            now,
            now,
            json.dumps(diary_create.metadata)
        ))
        
        conn.commit()
        
        return DiaryEntry(
            diary_id=diary_id,
            user_id=diary_create.user_id,
            title=diary_create.title,
            content=diary_create.content,
            preview=preview,
            entry_number=entry_number,
            emotion_tags=diary_create.emotion_tags,
            created_at=now,
            updated_at=now,
            metadata=diary_create.metadata
        )
    
    def get_diary(self, diary_id: str) -> Optional[DiaryEntry]:
        """根据ID获取日记条目
        
        Args:
            diary_id: 日记ID
            
        Returns:
            日记条目，如果不存在则返回None
        """
        import json
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM diaries WHERE diary_id = ?", (diary_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return DiaryEntry(
            diary_id=row["diary_id"],
            user_id=row["user_id"],
            title=row["title"],
            content=row["content"],
            preview=row["preview"],
            entry_number=row["entry_number"],
            emotion_tags=json.loads(row["emotion_tags"]) if row["emotion_tags"] else [],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            metadata=json.loads(row["metadata"]) if row["metadata"] else {}
        )
    
    def update_diary(self, diary_id: str, diary_update: DiaryEntryUpdate) -> Optional[DiaryEntry]:
        """更新日记条目
        
        Args:
            diary_id: 日记ID
            diary_update: 日记更新请求
            
        Returns:
            更新后的日记条目，如果不存在则返回None
        """
        import json
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 获取现有日记
        cursor.execute("SELECT * FROM diaries WHERE diary_id = ?", (diary_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        # 准备更新字段
        updates = {}
        if diary_update.title is not None:
            updates["title"] = diary_update.title
        if diary_update.content is not None:
            updates["content"] = diary_update.content
            updates["preview"] = self._generate_preview(diary_update.content)
        if diary_update.emotion_tags is not None:
            updates["emotion_tags"] = json.dumps(diary_update.emotion_tags)
        if diary_update.metadata is not None:
            updates["metadata"] = json.dumps(diary_update.metadata)
        
        if not updates:
            return self.get_diary(diary_id)
        
        # 添加更新时间
        updates["updated_at"] = datetime.utcnow().isoformat()
        
        # 构建SQL更新语句
        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values()) + [diary_id]
        
        cursor.execute(f"UPDATE diaries SET {set_clause} WHERE diary_id = ?", values)
        conn.commit()
        
        return self.get_diary(diary_id)
    
    def delete_diary(self, diary_id: str) -> bool:
        """删除日记条目
        
        Args:
            diary_id: 日记ID
            
        Returns:
            是否成功删除
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM diaries WHERE diary_id = ?", (diary_id,))
        deleted = cursor.rowcount > 0
        
        if deleted:
            # 更新用户日记计数
            cursor.execute("""
                SELECT user_id FROM diaries WHERE diary_id = ?
            """, (diary_id,))
            row = cursor.fetchone()
            
            if row:
                user_id = row["user_id"]
                cursor.execute("""
                    UPDATE user_diary_counts SET count = count - 1 WHERE user_id = ?
                """, (user_id,))
        
        conn.commit()
        return deleted
    
    def get_user_diaries(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0,
        order_by: str = "created_at DESC"
    ) -> List[DiaryEntry]:
        """获取用户的日记列表
        
        Args:
            user_id: 用户ID
            limit: 返回数量限制
            offset: 偏移量
            order_by: 排序方式
            
        Returns:
            日记条目列表
        """
        import json
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(f"""
            SELECT * FROM diaries 
            WHERE user_id = ? 
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
        """, (user_id, limit, offset))
        
        rows = cursor.fetchall()
        
        return [
            DiaryEntry(
                diary_id=row["diary_id"],
                user_id=row["user_id"],
                title=row["title"],
                content=row["content"],
                preview=row["preview"],
                entry_number=row["entry_number"],
                emotion_tags=json.loads(row["emotion_tags"]) if row["emotion_tags"] else [],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                metadata=json.loads(row["metadata"]) if row["metadata"] else {}
            )
            for row in rows
        ]
    
    def get_latest_diary(self, user_id: str) -> Optional[DiaryEntry]:
        """获取用户的最新日记
        
        Args:
            user_id: 用户ID
            
        Returns:
            最新日记条目，如果不存在则返回None
        """
        diaries = self.get_user_diaries(user_id, limit=1, order_by="created_at DESC")
        return diaries[0] if diaries else None
    
    def get_diary_count(self, user_id: str) -> int:
        """获取用户的日记总数
        
        Args:
            user_id: 用户ID
            
        Returns:
            日记总数
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM diaries WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        return row["count"] if row else 0
    
    def search_diaries(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
        offset: int = 0
    ) -> List[DiaryEntry]:
        """搜索用户的日记
        
        Args:
            user_id: 用户ID
            query: 搜索关键词
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            匹配的日记条目列表
        """
        import json
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        search_query = f"%{query}%"
        cursor.execute("""
            SELECT * FROM diaries 
            WHERE user_id = ? AND (title LIKE ? OR content LIKE ?)
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (user_id, search_query, search_query, limit, offset))
        
        rows = cursor.fetchall()
        
        return [
            DiaryEntry(
                diary_id=row["diary_id"],
                user_id=row["user_id"],
                title=row["title"],
                content=row["content"],
                preview=row["preview"],
                entry_number=row["entry_number"],
                emotion_tags=json.loads(row["emotion_tags"]) if row["emotion_tags"] else [],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                metadata=json.loads(row["metadata"]) if row["metadata"] else {}
            )
            for row in rows
        ]
    
    def get_emotion_tag_counts(self, user_id: str) -> Dict[str, int]:
        """获取用户情绪标签统计
        
        Args:
            user_id: 用户ID
            
        Returns:
            情绪标签及其使用次数的字典
        """
        import json
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT emotion_tags FROM diaries WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        
        tag_counts = {}
        for row in rows:
            if row["emotion_tags"]:
                tags = json.loads(row["emotion_tags"])
                for tag in tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        return tag_counts