"""
仓库分析相关的 Pydantic 模式定义
定义 API 请求和响应的数据结构
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from enum import Enum

class EmbeddingProvider(str, Enum):
    """Embedding 模型提供商枚举"""
    OPENAI = "openai"
    AZURE = "azure"
    HUGGINGFACE = "huggingface"
    OLLAMA = "ollama"
    GOOGLE = "google"

class LLMProvider(str, Enum):
    """LLM 模型提供商枚举"""
    OPENAI = "openai"
    AZURE = "azure"
    HUGGINGFACE = "huggingface"
    OLLAMA = "ollama"
    DEEPSEEK = "deepseek"
    GOOGLE = "google"


class GenerationMode(str, Enum):
    """生成模式枚举"""
    SERVICE = "service"  # 在服务端生成答案
    PLUGIN = "plugin"    # 只返回上下文，由插件生成答案


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

class EmbeddingConfig(BaseModel):
    provider: EmbeddingProvider
    model_name: str
    api_key: str | None = None
    api_base: str | None = None
    api_version: str | None = None
    deployment_name: str | None = None
    extra_params: Dict[str, Any] | None = None

class LLMConfig(BaseModel):
    provider: LLMProvider
    model_name: str
    api_key: str | None = None
    api_base: str | None = None
    api_version: str | None = None
    deployment_name: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    extra_params: Dict[str, Any] | None = None

class RepoAnalyzeRequest(BaseModel):
    repo_url: str
    embedding_config: EmbeddingConfig

class RepoAnalyzeResponse(BaseModel):
    """仓库分析响应模型"""
    session_id: str
    message: str
    status: TaskStatus = TaskStatus.PENDING

    class Config:
        use_enum_values = True

class QueryRequest(BaseModel):
    session_id: str
    question: str
    generation_mode: str
    llm_config: LLMConfig | None = None

class RetrievedChunk(BaseModel):
    """检索到的文档块"""
    id: str
    content: str
    file_path: str
    start_line: Optional[int] = None
    score: float
    metadata: Optional[Dict[str, Any]] = {}

class QueryResponse(BaseModel):
    answer: str | None = None
    retrieved_context: List[RetrievedChunk] | None = None
    generation_mode: str | None = None
    generation_time: int | None = None
    retrieval_time: int | None = None
    total_time: int | None = None

class SessionStatusResponse(BaseModel):
    """会话状态响应模型"""
    session_id: str
    repository_url: str
    repository_name: Optional[str] = None
    repository_owner: Optional[str] = None
    status: TaskStatus
    error_message: Optional[str] = None
    total_files: int = 0
    processed_files: int = 0
    total_chunks: int = 0
    indexed_chunks: int = 0
    progress_percentage: float = 0.0
    embedding_config: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    processing_duration: Optional[float] = None

    class Config:
        use_enum_values = True

class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: str
    detail: Optional[str] = None
    error_code: Optional[str] = None

class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status: str = "healthy"
    version: str
    timestamp: str
    services: Dict[str, str] = {}

class FileInfo(BaseModel):
    """文件信息模型"""
    file_path: str
    file_type: str
    file_extension: Optional[str] = None
    file_size: int
    line_count: Optional[int] = None
    is_processed: str
    chunk_count: int = 0
    error_message: Optional[str] = None

class SessionFilesResponse(BaseModel):
    """会话文件列表响应模型"""
    session_id: str
    total_files: int
    files: List[FileInfo]


class ModelInfo(BaseModel):
    """模型信息"""
    provider: str
    model_name: str
    model_id: str


class AvailableModelsResponse(BaseModel):
    """可用模型列表响应"""
    embedding_models: Dict[str, List[ModelInfo]]
    llm_models: Dict[str, List[ModelInfo]]