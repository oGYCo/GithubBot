"""
数据库模型定义
定义应用的 SQLAlchemy ORM 模型
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalysisSession(Base):
    """分析会话模型"""
    __tablename__ = "analysis_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False)
    task_id = Column(String(64), nullable=True, index=True)  # Celery 任务 ID
    repository_url = Column(String(512), nullable=False)
    repository_name = Column(String(256), nullable=True)
    repository_owner = Column(String(128), nullable=True)

    # 任务状态
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING, nullable=False)
    error_message = Column(Text, nullable=True)

    # 处理统计
    total_files = Column(Integer, default=0)
    processed_files = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    indexed_chunks = Column(Integer, default=0)

    # 模型配置
    embedding_config = Column(JSON, nullable=True)

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<AnalysisSession(session_id={self.session_id}, status={self.status})>"

    @property
    def processing_duration(self) -> Optional[float]:
        """计算处理时长（秒）"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def progress_percentage(self) -> float:
        """计算处理进度百分比"""
        if self.total_chunks == 0:
            return 0.0
        return (self.indexed_chunks / self.total_chunks) * 100

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "session_id": self.session_id,
            "task_id": self.task_id,
            "repository_url": self.repository_url,
            "repository_name": self.repository_name,
            "repository_owner": self.repository_owner,
            "status": self.status.value if hasattr(self.status, 'value') else self.status,
            "error_message": self.error_message,
            "total_files": self.total_files,
            "processed_files": self.processed_files,
            "total_chunks": self.total_chunks,
            "indexed_chunks": self.indexed_chunks,
            "progress_percentage": self.progress_percentage,
            "embedding_config": self.embedding_config,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "processing_duration": self.processing_duration
        }


class QueryLog(Base):
    """查询日志模型"""
    __tablename__ = "query_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), index=True, nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)

    # 检索信息
    retrieved_chunks_count = Column(Integer, default=0)
    vector_search_results = Column(JSON, nullable=True)
    bm25_search_results = Column(JSON, nullable=True)
    final_context = Column(JSON, nullable=True)

    # 生成配置
    generation_mode = Column(String(32), default="service")  # service 或 plugin
    llm_config = Column(JSON, nullable=True)

    # 性能指标
    retrieval_time = Column(Integer, nullable=True)  # 毫秒
    generation_time = Column(Integer, nullable=True)  # 毫秒
    total_time = Column(Integer, nullable=True)  # 毫秒

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<QueryLog(session_id={self.session_id}, question={self.question[:50]}...)>"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "question": self.question,
            "answer": self.answer,
            "retrieved_chunks_count": self.retrieved_chunks_count,
            "generation_mode": self.generation_mode,
            "llm_config": self.llm_config,
            "retrieval_time": self.retrieval_time,
            "generation_time": self.generation_time,
            "total_time": self.total_time,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class FileMetadata(Base):
    """文件元数据模型"""
    __tablename__ = "file_metadata"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), index=True, nullable=False)
    file_path = Column(String(1024), nullable=False)
    file_type = Column(String(32), nullable=False)  # code, document, config, etc.
    file_extension = Column(String(16), nullable=True)
    file_size = Column(Integer, nullable=False)  # bytes
    line_count = Column(Integer, nullable=True)

    # 内容摘要
    content_summary = Column(Text, nullable=True)
    key_symbols = Column(JSON, nullable=True)  # 函数名、类名等
    dependencies = Column(JSON, nullable=True)  # 依赖信息

    # 处理状态
    is_processed = Column(String(16), default="pending")  # pending, success, failed, skipped
    chunk_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<FileMetadata(file_path={self.file_path}, is_processed={self.is_processed})>"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "file_path": self.file_path,
            "file_type": self.file_type,
            "file_extension": self.file_extension,
            "file_size": self.file_size,
            "line_count": self.line_count,
            "content_summary": self.content_summary,
            "key_symbols": self.key_symbols,
            "dependencies": self.dependencies,
            "is_processed": self.is_processed,
            "chunk_count": self.chunk_count,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None
        }