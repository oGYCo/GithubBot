"""
数据库会话管理
负责创建和管理数据库连接和会话
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from ..core.config import settings
from .models import Base


# 创建数据库引擎
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    # SQLite 特殊配置
    poolclass=StaticPool if settings.DATABASE_URL.startswith("sqlite") else None,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():
    """创建所有数据库表"""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    获取数据库会话的依赖项
    用于 FastAPI 的依赖注入
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Session:
    """
    直接获取数据库会话
    用于非 FastAPI 环境（如 Celery 任务）
    """
    return SessionLocal()