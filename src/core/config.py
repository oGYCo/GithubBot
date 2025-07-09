"""
应用配置模块
负责从环境变量加载和管理所有配置信息
"""

import logging
import os
from pathlib import Path
from typing import List, Optional, Any

from dotenv import load_dotenv
from pydantic import AnyHttpUrl, field_validator, ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


# .env 文件路径
env_path = Path(".") / ".env"
if env_path.is_file():
    load_dotenv(dotenv_path=env_path)


class Settings(BaseSettings):
    """应用配置模型"""
    # model_config in V2 replaces the Config class in V1
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra='ignore' # Ignore extra fields from environment
    )

    # --- 应用基本配置 ---
    APP_NAME: str = "RepoInsight Service"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    API_KEY: Optional[str] = None
    CORS_ORIGINS: str = ""

    @field_validator("CORS_ORIGINS", mode='after')
    def parse_cors_origins(cls, v: str) -> List[str]:
        """解析 CORS_ORIGINS 字符串为 URL 列表"""
        if not v:
            return []

        # 去除可能的引号
        v = v.strip().strip("'\"")

        # 如果是 JSON 数组格式
        if v.startswith("[") and v.endswith("]"):
            try:
                import json
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(url).strip() for url in parsed if url]
            except json.JSONDecodeError:
                pass

        # 否则作为逗号分隔的字符串处理
        return [url.strip() for url in v.split(",") if url.strip()]

    # --- 服务端口配置 ---
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # --- 数据库配置 (PostgreSQL) ---
    POSTGRES_USER: str = "user"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "repoinsight"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: Optional[str] = None

    @field_validator("DATABASE_URL", mode='before')
    def assemble_db_connection(cls, v: Optional[str], info: ValidationInfo) -> str:
        if isinstance(v, str):
            return v
        values = info.data
        return (
            f"postgresql+psycopg2://{values.get('POSTGRES_USER')}:{values.get('POSTGRES_PASSWORD')}"
            f"@{values.get('POSTGRES_HOST')}:{values.get('POSTGRES_PORT')}/{values.get('POSTGRES_DB')}"
        )

    # --- 消息队列配置 (Redis) ---
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_URL: Optional[str] = None

    @field_validator("REDIS_URL", mode='before')
    def assemble_redis_connection(cls, v: Optional[str], info: ValidationInfo) -> str:
        if isinstance(v, str):
            return v
        values = info.data
        return f"redis://{values.get('REDIS_HOST')}:{values.get('REDIS_PORT')}/0"

    # --- 向量数据库配置 (ChromaDB) ---
    CHROMA_SERVER_URL: Optional[str] = None
    CHROMA_SERVER_HOST: str = "chromadb"
    CHROMA_SERVER_PORT: int = 8000

    @field_validator("CHROMA_SERVER_URL", mode='before')
    def assemble_chroma_connection(cls, v: Optional[str], info: ValidationInfo) -> str:
        if isinstance(v, str):
            return v
        values = info.data
        return f"http://{values.get('CHROMA_SERVER_HOST')}:{values.get('CHROMA_SERVER_PORT')}"

    # --- LLM 和 Embedding 模型 API Keys ---
    OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    COHERE_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    HUGGINGFACE_HUB_API_TOKEN: Optional[str] = None
    MISTRAL_API_KEY: Optional[str] = None

    # --- Git 配置 ---
    GIT_CLONE_DIR: str = "/tmp/repo_clones"


# 全局配置实例
settings = Settings()


# 日志设置
def setup_logging():
    logging.basicConfig(
        level=settings.LOG_LEVEL.upper(),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # 可以为特定的库设置不同的日志级别
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def validate_config():
    """在应用启动时验证关键配置"""
    if settings.API_KEY:
        logging.info("API Key 已配置。")
    else:
        logging.warning("警告: API_KEY 未设置，API 将无保护。")