"""
Embedding 模型管理器
负责根据配置动态加载和实例化不同的 Embedding 模型
支持 OpenAI、Azure、HuggingFace、Ollama、Gemini、DeepSeek、千问等多种提供商
提供批量向量化、速率限制处理、异常重试等高级功能
"""

import logging
import time
import asyncio
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from langchain_openai import OpenAIEmbeddings, AzureOpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.embeddings import Embeddings
from ..core.config import settings
logger = logging.getLogger(__name__)


@dataclass
class EmbeddingConfig:
    """Embedding 模型配置类"""
    provider: str
    model_name: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    api_version: Optional[str] = None
    deployment_name: Optional[str] = None
    batch_size: int = 32
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: int = 60
    extra_params: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """初始化后处理"""
        self.provider = self.provider.lower()

        # 验证必需参数
        if not self.model_name:
            raise ValueError("model_name 不能为空")

        # 根据提供商设置默认值
        if self.provider == "azure" and not self.api_version:
            self.api_version = "2024-02-01"

        if self.provider == "ollama" and not self.api_base:
            self.api_base = "http://localhost:11434"

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'EmbeddingConfig':
        """从字典创建配置"""
        # 确保 extra_params 不为 None
        if config_dict.get('extra_params') is None:
            config_dict = config_dict.copy()
            config_dict['extra_params'] = {}
        return cls(**config_dict)


class EmbeddingError(Exception):
    """Embedding 相关异常"""
    pass


class RateLimitError(EmbeddingError):
    """速率限制异常"""
    pass


class APIKeyError(EmbeddingError):
    """API密钥异常"""
    pass


class BatchEmbeddingProcessor:
    """批量向量化处理器"""

    def __init__(self, embedding_model: Embeddings, config: EmbeddingConfig):
        self.embedding_model = embedding_model
        self.config = config
        self.logger = logging.getLogger(__name__)

    async def embed_documents_with_retry(self, texts: List[str]) -> List[List[float]]:
        """
        批量向量化文档，支持重试和速率限制处理

        Args:
            texts: 文本列表

        Returns:
            向量列表

        Raises:
            EmbeddingError: 向量化失败
        """
        if not texts:
            return []

        all_embeddings = []

        # 分批处理
        for i in range(0, len(texts), self.config.batch_size):
            batch = texts[i:i + self.config.batch_size]
            batch_embeddings = await self._embed_batch_with_retry(batch)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    async def _embed_batch_with_retry(self, batch: List[str]) -> List[List[float]]:
        """
        处理单个批次，支持重试

        Args:
            batch: 文本批次

        Returns:
            向量列表
        """
        last_exception = None

        for attempt in range(self.config.max_retries + 1):
            try:
                self.logger.debug(f"处理批次，大小: {len(batch)}, 尝试: {attempt + 1}")

                # 调用实际的向量化
                embeddings = await self._call_embedding_api(batch)

                # 验证结果
                if len(embeddings) != len(batch):
                    raise EmbeddingError(f"返回的向量数量({len(embeddings)})与输入文本数量({len(batch)})不匹配")

                self.logger.debug(f"批次处理成功，返回 {len(embeddings)} 个向量")
                return embeddings

            except Exception as e:
                last_exception = e
                self.logger.warning(f"批次处理失败 (尝试 {attempt + 1}/{self.config.max_retries + 1}): {str(e)}")

                # 判断是否是速率限制错误
                if self._is_rate_limit_error(e):
                    if attempt < self.config.max_retries:
                        # 指数退避
                        delay = self.config.retry_delay * (2 ** attempt)
                        self.logger.info(f"遇到速率限制，等待 {delay} 秒后重试")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise RateLimitError(f"达到最大重试次数，仍遇到速率限制: {str(e)}")

                # 判断是否是API密钥错误
                if self._is_api_key_error(e):
                    raise APIKeyError(f"API密钥无效或已过期: {str(e)}")

                # 其他错误，如果还有重试机会就继续
                if attempt < self.config.max_retries:
                    await asyncio.sleep(self.config.retry_delay)
                    continue

        # 所有重试都失败了
        raise EmbeddingError(f"批次处理最终失败: {str(last_exception)}")

    async def _call_embedding_api(self, texts: List[str]) -> List[List[float]]:
        """
        调用实际的向量化API

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        try:
            # 如果模型支持异步，使用异步方法
            if hasattr(self.embedding_model, 'aembed_documents'):
                return await self.embedding_model.aembed_documents(texts)
            else:
                # 否则在线程池中运行同步方法
                import asyncio
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    self.embedding_model.embed_documents,
                    texts
                )
        except Exception as e:
            self.logger.error(f"调用embedding API失败: {str(e)}")
            raise

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """检查是否是速率限制错误"""
        error_str = str(error).lower()
        rate_limit_indicators = [
            'rate limit',
            'too many requests',
            'quota exceeded',
            '429',
            'rate_limit_exceeded'
        ]
        return any(indicator in error_str for indicator in rate_limit_indicators)

    def _is_api_key_error(self, error: Exception) -> bool:
        """检查是否是API密钥错误"""
        error_str = str(error).lower()
        api_key_indicators = [
            'api key',
            'invalid key',
            'unauthorized',
            '401',
            'authentication',
            'invalid_api_key'
        ]
        return any(indicator in error_str for indicator in api_key_indicators)


class EmbeddingManager:
    """Embedding 模型管理器"""

    # 支持的提供商映射
    SUPPORTED_PROVIDERS = {
        'openai': '_create_openai_embeddings',
        'azure': '_create_azure_embeddings',
        'azure_openai': '_create_azure_embeddings',
        'huggingface': '_create_huggingface_embeddings',
        'hf': '_create_huggingface_embeddings',
        'ollama': '_create_ollama_embeddings',
        'google': '_create_google_embeddings',
        'gemini': '_create_google_embeddings',
        'deepseek': '_create_deepseek_embeddings',
        'qwen': '_create_qwen_embeddings',
        'zhipu': '_create_zhipu_embeddings',
        'baichuan': '_create_baichuan_embeddings',
        'cohere': '_create_cohere_embeddings',
        'mistral': '_create_mistral_embeddings',
        'jina': '_create_jina_embeddings',
    }

    @staticmethod
    def get_embedding_model(config: EmbeddingConfig) -> Embeddings:
        """
        根据配置动态创建 Embedding 模型实例

        Args:
            config: Embedding 模型配置

        Returns:
            LangChain Embeddings 实例

        Raises:
            ValueError: 当提供商不支持时
            EmbeddingError: 当模型加载失败时
        """
        logger.info(f"正在加载 {config.provider} 的 {config.model_name} 模型")
        logger.info(f"🔍 [调试] EmbeddingManager - 接收到的config: provider={config.provider}, model={config.model_name}, api_key={'***' if config.api_key else 'None'}")

        # 检查提供商是否支持
        if config.provider not in EmbeddingManager.SUPPORTED_PROVIDERS:
            supported = list(EmbeddingManager.SUPPORTED_PROVIDERS.keys())
            raise ValueError(f"不支持的 embedding 提供商: {config.provider}。支持的提供商: {supported}")

        try:
            # 动态调用相应的创建方法
            method_name = EmbeddingManager.SUPPORTED_PROVIDERS[config.provider]
            logger.info(f"🔍 [调试] EmbeddingManager - 将调用方法: {method_name}")
            method = getattr(EmbeddingManager, method_name)
            result = method(config)
            logger.info(f"🔍 [调试] EmbeddingManager - 创建的模型类型: {type(result)}")
            return result

        except Exception as e:
            logger.error(f"加载 {config.provider} 模型失败: {str(e)}")
            raise EmbeddingError(f"模型加载失败: {str(e)}") from e

    @staticmethod
    def create_batch_processor(config: EmbeddingConfig) -> BatchEmbeddingProcessor:
        """
        创建批量处理器

        Args:
            config: Embedding 配置

        Returns:
            批量处理器实例
        """
        embedding_model = EmbeddingManager.get_embedding_model(config)
        return BatchEmbeddingProcessor(embedding_model, config)


    @staticmethod
    def _create_openai_embeddings(config: EmbeddingConfig) -> OpenAIEmbeddings:
        """创建 OpenAI Embeddings 实例"""
        try:
            params = {
                "model": config.model_name,
                "show_progress_bar": True,
                "max_retries": config.max_retries,
                "timeout": config.timeout,
                **config.extra_params
            }

            if config.api_key:
                params["api_key"] = config.api_key
            if config.api_base:
                params["base_url"] = config.api_base

            return OpenAIEmbeddings(**params)
        except Exception as e:
            raise EmbeddingError(f"创建 OpenAI 模型失败: {str(e)}") from e

    @staticmethod
    def _create_azure_embeddings(config: EmbeddingConfig) -> AzureOpenAIEmbeddings:
        """创建 Azure OpenAI Embeddings 实例"""
        try:
            params = {
                "model": config.model_name,
                "show_progress_bar": True,
                "max_retries": config.max_retries,
                "timeout": config.timeout,
                **config.extra_params
            }

            if config.api_key:
                params["api_key"] = config.api_key
            if config.api_base:
                params["azure_endpoint"] = config.api_base
            if config.api_version:
                params["api_version"] = config.api_version
            if config.deployment_name:
                params["azure_deployment"] = config.deployment_name

            return AzureOpenAIEmbeddings(**params)
        except Exception as e:
            raise EmbeddingError(f"创建 Azure OpenAI 模型失败: {str(e)}") from e

    @staticmethod
    def _create_huggingface_embeddings(config: EmbeddingConfig) -> HuggingFaceEmbeddings:
        """创建 HuggingFace Embeddings 实例"""
        try:
            params = {
                "model_name": config.model_name,
                "show_progress": True,
                **config.extra_params
            }

            # 如果指定了 API 基础地址，则使用 API 方式
            if config.api_base:
                params["api_url"] = config.api_base
                if config.api_key:
                    params["api_key"] = config.api_key

            return HuggingFaceEmbeddings(**params)
        except Exception as e:
            raise EmbeddingError(f"创建 HuggingFace 模型失败: {str(e)}") from e

    @staticmethod
    def _create_ollama_embeddings(config: EmbeddingConfig) -> OllamaEmbeddings:
        """创建 Ollama Embeddings 实例"""
        try:
            params = {
                "model": config.model_name,
                "base_url": config.api_base or "http://localhost:11434",
                **config.extra_params
            }

            return OllamaEmbeddings(**params)
        except Exception as e:
            raise EmbeddingError(f"创建 Ollama 模型失败: {str(e)}") from e

    @staticmethod
    def _create_google_embeddings(config: EmbeddingConfig) -> GoogleGenerativeAIEmbeddings:
        """创建 Google Generative AI Embeddings 实例"""
        try:
            params = {
                "model": config.model_name,
                **config.extra_params
            }

            if config.api_key:
                params["google_api_key"] = config.api_key

            return GoogleGenerativeAIEmbeddings(**params)
        except Exception as e:
            raise EmbeddingError(f"创建 Google 模型失败: {str(e)}") from e

    @staticmethod
    def _create_deepseek_embeddings(config: EmbeddingConfig) -> OpenAIEmbeddings:
        """创建 DeepSeek Embeddings 实例（使用 OpenAI 兼容接口）"""
        try:
            params = {
                "model": config.model_name,
                "base_url": config.api_base or "https://api.deepseek.com/v1",
                "show_progress_bar": True,
                "max_retries": config.max_retries,
                "timeout": config.timeout,
                **config.extra_params
            }

            if config.api_key:
                params["api_key"] = config.api_key

            return OpenAIEmbeddings(**params)
        except Exception as e:
            raise EmbeddingError(f"创建 DeepSeek 模型失败: {str(e)}") from e

    @staticmethod
    def _create_qwen_embeddings(config: EmbeddingConfig) -> OpenAIEmbeddings:
        """创建 通义千问 Embeddings 实例（使用 OpenAI 兼容接口）"""
        try:
            # API Key 优先级：配置中的 api_key > 环境变量 QWEN_API_KEY > 环境变量 DASHSCOPE_API_KEY
            api_key = config.api_key or settings.QWEN_API_KEY or settings.DASHSCOPE_API_KEY
            
            if not api_key:
                raise EmbeddingError("通义千问模型需要 API Key，请在请求中提供 api_key 或在 .env 文件中设置 QWEN_API_KEY 或 DASHSCOPE_API_KEY")
            
            params = {
                "model": config.model_name,
                "api_key": api_key,
                "base_url": config.api_base or "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "show_progress_bar": True,
                "max_retries": config.max_retries,
                "timeout": config.timeout,
                "tiktoken_enabled": False,  # 对于非 OpenAI 实现禁用 tiktoken
                **config.extra_params
            }

            return OpenAIEmbeddings(**params)
        except Exception as e:
            raise EmbeddingError(f"创建 通义千问 模型失败: {str(e)}") from e

    @staticmethod
    def _create_zhipu_embeddings(config: EmbeddingConfig) -> OpenAIEmbeddings:
        """创建 智谱 AI Embeddings 实例（使用 OpenAI 兼容接口）"""
        try:
            params = {
                "model": config.model_name,
                "base_url": config.api_base or "https://open.bigmodel.cn/api/paas/v4",
                "show_progress_bar": True,
                "max_retries": config.max_retries,
                "timeout": config.timeout,
                **config.extra_params
            }

            if config.api_key:
                params["api_key"] = config.api_key

            return OpenAIEmbeddings(**params)
        except Exception as e:
            raise EmbeddingError(f"创建 智谱 AI 模型失败: {str(e)}") from e

    @staticmethod
    def _create_baichuan_embeddings(config: EmbeddingConfig) -> OpenAIEmbeddings:
        """创建 百川 AI Embeddings 实例（使用 OpenAI 兼容接口）"""
        try:
            params = {
                "model": config.model_name,
                "base_url": config.api_base or "https://api.baichuan-ai.com/v1",
                "show_progress_bar": True,
                "max_retries": config.max_retries,
                "timeout": config.timeout,
                **config.extra_params
            }

            if config.api_key:
                params["api_key"] = config.api_key

            return OpenAIEmbeddings(**params)
        except Exception as e:
            raise EmbeddingError(f"创建 百川 AI 模型失败: {str(e)}") from e

    @staticmethod
    def _create_cohere_embeddings(config: EmbeddingConfig):
        """创建 Cohere Embeddings 实例"""
        try:
            # 尝试导入 Cohere embeddings
            try:
                from langchain_cohere import CohereEmbeddings
            except ImportError:
                raise EmbeddingError("需要安装 langchain_cohere: pip install langchain_cohere")

            params = {
                "model": config.model_name,
                "max_retries": config.max_retries,
                **config.extra_params
            }

            if config.api_key:
                params["cohere_api_key"] = config.api_key

            return CohereEmbeddings(**params)
        except Exception as e:
            raise EmbeddingError(f"创建 Cohere 模型失败: {str(e)}") from e

    @staticmethod
    def _create_mistral_embeddings(config: EmbeddingConfig):
        """创建 Mistral Embeddings 实例"""
        try:
            # 尝试导入 Mistral embeddings
            try:
                from langchain_mistralai import MistralAIEmbeddings
            except ImportError:
                raise EmbeddingError("需要安装 langchain_mistralai: pip install langchain_mistralai")

            params = {
                "model": config.model_name,
                "max_retries": config.max_retries,
                **config.extra_params
            }

            if config.api_key:
                params["mistral_api_key"] = config.api_key
            if config.api_base:
                params["endpoint"] = config.api_base

            return MistralAIEmbeddings(**params)
        except Exception as e:
            raise EmbeddingError(f"创建 Mistral 模型失败: {str(e)}") from e

    @staticmethod
    def _create_jina_embeddings(config: EmbeddingConfig) -> OpenAIEmbeddings:
        """创建 Jina AI Embeddings 实例（使用 OpenAI 兼容接口）"""
        try:
            params = {
                "model": config.model_name,
                "base_url": config.api_base or "https://api.jina.ai/v1",
                "show_progress_bar": True,
                "max_retries": config.max_retries,
                "timeout": config.timeout,
                **config.extra_params
            }

            if config.api_key:
                params["api_key"] = config.api_key

            return OpenAIEmbeddings(**params)
        except Exception as e:
            raise EmbeddingError(f"创建 Jina AI 模型失败: {str(e)}") from e

    @staticmethod
    def get_supported_providers() -> List[str]:
        """获取支持的提供商列表"""
        return list(EmbeddingManager.SUPPORTED_PROVIDERS.keys())

    @staticmethod
    def validate_config(config: EmbeddingConfig) -> bool:
        """
        验证配置是否有效

        Args:
            config: 配置对象

        Returns:
            配置是否有效

        Raises:
            ValueError: 配置无效时
        """
        if not config.provider:
            raise ValueError("provider 不能为空")

        if not config.model_name:
            raise ValueError("model_name 不能为空")

        if config.provider not in EmbeddingManager.SUPPORTED_PROVIDERS:
            supported = EmbeddingManager.get_supported_providers()
            raise ValueError(f"不支持的提供商: {config.provider}。支持的提供商: {supported}")

        # 检查特定提供商的必需参数
        if config.provider in ['openai', 'azure', 'deepseek', 'qwen', 'zhipu', 'baichuan', 'jina']:
            if not config.api_key:
                logger.warning(f"{config.provider} 通常需要 API 密钥")

        if config.provider == 'azure':
            if not config.api_base:
                raise ValueError("Azure 提供商需要 api_base (Azure endpoint)")

        return True



def get_embedding_model(
        provider: str,
        model_name: str,
        api_key: Optional[str] = None,
        **kwargs
) -> Embeddings:
    """
    便捷函数：根据参数创建 Embedding 模型

    Args:
        provider: 提供商名称
        model_name: 模型名称
        api_key: API 密钥
        **kwargs: 其他配置参数

    Returns:
        LangChain Embeddings 实例
    """
    config = EmbeddingConfig(
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        **kwargs
    )
    return EmbeddingManager.get_embedding_model(config)


def create_embedding_config_from_request(request_data: Dict[str, Any]) -> EmbeddingConfig:
    """
    从 API 请求数据创建 EmbeddingConfig

    Args:
        request_data: API 请求中的 embedding_config 数据

    Returns:
        EmbeddingConfig 实例
    """
    return EmbeddingConfig.from_dict(request_data)


async def embed_texts_with_config(
        texts: List[str],
        config: EmbeddingConfig
) -> List[List[float]]:
    """
    使用配置对文本进行向量化的便捷函数

    Args:
        texts: 要向量化的文本列表
        config: Embedding 配置

    Returns:
        向量列表
    """
    processor = EmbeddingManager.create_batch_processor(config)
    return await processor.embed_documents_with_retry(texts)


# 预定义的常用模型配置
COMMON_EMBEDDING_MODELS = {
    "openai": {
        "text-embedding-3-small": "text-embedding-3-small",
        "text-embedding-3-large": "text-embedding-3-large",
        "text-embedding-ada-002": "text-embedding-ada-002",
    },
    "azure": {
        "text-embedding-3-small": "text-embedding-3-small",
        "text-embedding-3-large": "text-embedding-3-large",
        "text-embedding-ada-002": "text-embedding-ada-002",
    },
    "huggingface": {
        "bge-large-zh-v1.5": "BAAI/bge-large-zh-v1.5",
        "bge-base-zh-v1.5": "BAAI/bge-base-zh-v1.5",
        "bge-small-zh-v1.5": "BAAI/bge-small-zh-v1.5",
        "bge-large-en-v1.5": "BAAI/bge-large-en-v1.5",
        "bge-base-en-v1.5": "BAAI/bge-base-en-v1.5",
        "bge-small-en-v1.5": "BAAI/bge-small-en-v1.5",
        "text2vec-base": "shibing624/text2vec-base-chinese",
        "text2vec-large": "shibing624/text2vec-large-chinese",
        "m3e-base": "moka-ai/m3e-base",
        "m3e-large": "moka-ai/m3e-large",
        "gte-large": "thenlper/gte-large",
        "gte-base": "thenlper/gte-base",
        "sentence-t5-base": "sentence-transformers/sentence-t5-base",
        "all-mpnet-base-v2": "sentence-transformers/all-mpnet-base-v2",
        "all-MiniLM-L6-v2": "sentence-transformers/all-MiniLM-L6-v2",
    },
    "ollama": {
        "nomic-embed-text": "nomic-embed-text",
        "mxbai-embed-large": "mxbai-embed-large",
        "bge-large": "bge-large",
        "bge-base": "bge-base",
        "snowflake-arctic-embed": "snowflake-arctic-embed",
        "all-minilm": "all-minilm",
    },
    "google": {
        "embedding-001": "models/embedding-001",
        "text-embedding-004": "models/text-embedding-004",
        "textembedding-gecko": "models/textembedding-gecko",
        "textembedding-gecko-multilingual": "models/textembedding-gecko-multilingual",
    },
    "deepseek": {
        "deepseek-embeddings": "deepseek-embeddings",
    },
    "qwen": {
        "text-embedding-v1": "text-embedding-v1",
        "text-embedding-v2": "text-embedding-v2",
        "text-embedding-v3": "text-embedding-v3",
        "text-embedding-v4": "text-embedding-v4",
    },
    "zhipu": {
        "embedding-2": "embedding-2",
        "embedding-3": "embedding-3",
    },
    "baichuan": {
        "Baichuan-Text-Embedding": "Baichuan-Text-Embedding",
    },
    "cohere": {
        "embed-english-v3.0": "embed-english-v3.0",
        "embed-multilingual-v3.0": "embed-multilingual-v3.0",
        "embed-english-light-v3.0": "embed-english-light-v3.0",
        "embed-multilingual-light-v3.0": "embed-multilingual-light-v3.0",
    },
    "mistral": {
        "mistral-embed": "mistral-embed",
    },
    "jina": {
        "jina-embeddings-v2-base-en": "jina-embeddings-v2-base-en",
        "jina-embeddings-v2-base-zh": "jina-embeddings-v2-base-zh",
        "jina-embeddings-v2-base-de": "jina-embeddings-v2-base-de",
        "jina-embeddings-v2-base-es": "jina-embeddings-v2-base-es",
    }
}


def get_available_models(provider: str) -> Dict[str, str]:
    """
    获取指定提供商的可用模型列表

    Args:
        provider: 提供商名称

    Returns:
        模型名称到模型ID的映射字典
    """
    return COMMON_EMBEDDING_MODELS.get(provider.lower(), {})


def get_all_providers() -> List[str]:
    """获取所有支持的提供商列表"""
    return list(COMMON_EMBEDDING_MODELS.keys())


def get_provider_info(provider: str) -> Dict[str, Any]:
    """
    获取提供商信息

    Args:
        provider: 提供商名称

    Returns:
        包含提供商信息的字典
    """
    provider = provider.lower()

    info = {
        "name": provider,
        "models": get_available_models(provider),
        "requires_api_key": provider in ['openai', 'azure', 'google', 'deepseek', 'qwen', 'zhipu', 'baichuan', 'cohere', 'mistral', 'jina'],
        "requires_endpoint": provider in ['azure', 'ollama'],
        "supports_local": provider in ['huggingface', 'ollama'],
    }

    # 添加默认端点信息
    default_endpoints = {
        'openai': 'https://api.openai.com/v1',
        'deepseek': 'https://api.deepseek.com/v1',
        'qwen': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'zhipu': 'https://open.bigmodel.cn/api/paas/v4',
        'baichuan': 'https://api.baichuan-ai.com/v1',
        'jina': 'https://api.jina.ai/v1',
        'ollama': 'http://localhost:11434',
        'cohere': 'https://api.cohere.ai',
        'mistral': 'https://api.mistral.ai',
    }

    if provider in default_endpoints:
        info["default_endpoint"] = default_endpoints[provider]

    return info


def get_recommended_models() -> Dict[str, Dict[str, str]]:
    """
    获取推荐的模型配置

    Returns:
        按用途分类的推荐模型
    """
    return {
        "中文通用": {
            "provider": "qwen",
            "model": "text-embedding-v4",
            "description": "阿里云通义千问最新向量化模型，支持100+语种和代码"
        },
        "中文本地": {
            "provider": "huggingface",
            "model": "bge-large-zh-v1.5",
            "description": "适合中文文档的本地部署向量化模型"
        },
        "英文通用": {
            "provider": "openai",
            "model": "text-embedding-3-large",
            "description": "OpenAI 最新的大型向量化模型"
        },
        "多语言": {
            "provider": "huggingface",
            "model": "gte-large",
            "description": "支持多种语言的通用模型"
        },
        "代码": {
            "provider": "openai",
            "model": "text-embedding-3-small",
            "description": "适合代码向量化的轻量模型"
        },
        "本地部署": {
            "provider": "ollama",
            "model": "nomic-embed-text",
            "description": "本地部署的开源向量化模型"
        },
        "经济型": {
            "provider": "huggingface",
            "model": "all-MiniLM-L6-v2",
            "description": "轻量级、快速的向量化模型"
        }
    }