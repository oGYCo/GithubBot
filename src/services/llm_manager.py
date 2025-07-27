"""
LLM 模型管理器
负责根据配置动态加载和实例化不同的大语言模型
支持 OpenAI、Azure、HuggingFace、Ollama、DeepSeek、Gemini 等多种提供商
"""

import logging
from typing import Dict, Optional, Union
from langchain_openai import ChatOpenAI, OpenAI, AzureChatOpenAI
from langchain_community.llms import HuggingFacePipeline
from langchain_huggingface import ChatHuggingFace
from langchain_community.chat_models import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models import BaseLLM, BaseChatModel
from ..core.config import settings

logger = logging.getLogger(__name__)


class LLMConfig:
    """LLM 模型配置类
    provider (提供商): 指定使用哪个大模型服务，例如 openai, azure, ollama 等。代码会将其转换为小写以方便后续处理。
    model_name (模型名称): 指定要使用的具体模型，例如 gpt-4o 或 llama3.1。
    api_key (API 密钥): 用于访问需要付费或认证的 API 服务的密钥。
    api_base (API 基础地址): 指定 API 的服务器地址。这对于连接自托管模型、代理服务或非官方服务（如 DeepSeek）非常有用。
    api_version (API 版本): 专用于某些特定服务（如 Azure OpenAI）的 API 版本号。
    deployment_name (部署名称): 也是专用于 Azure OpenAI 的参数，指定在 Azure 上的部署名。
    temperature (温度参数): 控制模型输出的随机性。值越高，输出越随机、越有创意；值越低，输出越确定、越保守。
    max_tokens (最大令牌数): 限制模型单次生成内容的最大长度。
    **kwargs (额外参数): 这是一个非常灵活的设计，允许您传入任何其他特定于某个模型或提供商的参数，这些参数会被收集到一个名为 extra_params 的字典中。
    """

    def __init__(
            self,
            provider: str,
            model_name: str,
            api_key: Optional[str] = None,
            api_base: Optional[str] = None,
            api_version: Optional[str] = None,
            deployment_name: Optional[str] = None,
            temperature: float = 0.7,
            max_tokens: Optional[int] = None,
            **kwargs
    ):
        self.provider = provider.lower()
        self.model_name = model_name
        self.api_key = api_key
        self.api_base = api_base
        self.api_version = api_version
        self.deployment_name = deployment_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra_params = kwargs


class LLMManager:
    """LLM 模型管理器"""

    @staticmethod
    def get_llm(config: LLMConfig) -> Union[BaseLLM, BaseChatModel]:
        """
        根据配置动态创建 LLM 模型实例

        Args:
            config: LLM 模型配置

        Returns:
            LangChain LLM 或 ChatModel 实例

        Raises:
            ValueError: 当提供商不支持时
            Exception: 当模型加载失败时
        """
        logger.info(f"正在加载 {config.provider} 的 {config.model_name} 模型")

        try:
            if config.provider == "openai":
                return LLMManager._create_openai_llm(config)

            elif config.provider == "azure":
                return LLMManager._create_azure_llm(config)

            elif config.provider == "huggingface":
                return LLMManager._create_huggingface_llm(config)

            elif config.provider == "ollama":
                return LLMManager._create_ollama_llm(config)

            elif config.provider == "deepseek":
                return LLMManager._create_deepseek_llm(config)

            elif config.provider == "google" or config.provider == "gemini":
                return LLMManager._create_google_llm(config)

            elif config.provider == "qwen":
                return LLMManager._create_qwen_llm(config)

            else:
                raise ValueError(f"不支持的 LLM 提供商: {config.provider}")

        except Exception as e:
            logger.error(f"加载 {config.provider} 模型失败: {str(e)}")
            raise

    @staticmethod
    def _create_openai_llm(config: LLMConfig) -> ChatOpenAI:
        """创建 OpenAI LLM 实例"""
        params = {
            "model": config.model_name,
            "temperature": config.temperature,
            "max_retries": 3,
            **config.extra_params
        }

        if config.max_tokens:
            params["max_tokens"] = config.max_tokens
        if config.api_key:
            params["api_key"] = config.api_key
        if config.api_base:
            params["base_url"] = config.api_base

        return ChatOpenAI(**params)

    @staticmethod
    def _create_azure_llm(config: LLMConfig) -> AzureChatOpenAI:
        """创建 Azure OpenAI LLM 实例"""
        params = {
            "model": config.model_name,
            "temperature": config.temperature,
            "max_retries": 3,
            **config.extra_params
        }

        if config.max_tokens:
            params["max_tokens"] = config.max_tokens
        if config.api_key:
            params["api_key"] = config.api_key
        if config.api_base:
            params["azure_endpoint"] = config.api_base
        if config.api_version:
            params["api_version"] = config.api_version
        if config.deployment_name:
            params["azure_deployment"] = config.deployment_name

        return AzureChatOpenAI(**params)

    @staticmethod
    def _create_huggingface_llm(config: LLMConfig) -> Union[ChatHuggingFace, HuggingFacePipeline]:
        """创建 HuggingFace LLM 实例"""
        params = {
            "model": config.model_name,
            "temperature": config.temperature,
            **config.extra_params
        }

        if config.max_tokens:
            params["max_new_tokens"] = config.max_tokens

        # 如果指定了 API 基础地址，则使用 API 方式
        if config.api_base:
            from langchain_huggingface import HuggingFaceEndpoint
            endpoint_params = {
                "endpoint_url": config.api_base,
                "task": "text-generation",
                **params
            }
            if config.api_key:
                endpoint_params["huggingfacehub_api_token"] = config.api_key

            endpoint = HuggingFaceEndpoint(**endpoint_params)
            return ChatHuggingFace(llm=endpoint)
        else:
            # 使用本地 pipeline
            pipeline = HuggingFacePipeline.from_model_id(
                model_id=config.model_name,
                task="text-generation",
                model_kwargs={"temperature": config.temperature},
                pipeline_kwargs={"max_new_tokens": config.max_tokens or 512}
            )
            return ChatHuggingFace(llm=pipeline)

    @staticmethod
    def _create_ollama_llm(config: LLMConfig) -> ChatOllama:
        """创建 Ollama LLM 实例"""
        params = {
            "model": config.model_name,
            "temperature": config.temperature,
            **config.extra_params
        }

        if config.max_tokens:
            params["num_predict"] = config.max_tokens
        if config.api_base:
            params["base_url"] = config.api_base
        else:
            params["base_url"] = "http://localhost:11434"

        return ChatOllama(**params)

    @staticmethod
    def _create_deepseek_llm(config: LLMConfig) -> ChatOpenAI:
        """创建 DeepSeek LLM 实例（使用 OpenAI 兼容接口）"""
        params = {
            "model": config.model_name,
            "temperature": config.temperature,
            "max_retries": 3,
            "base_url": config.api_base or "https://api.deepseek.com",
            **config.extra_params
        }

        if config.max_tokens:
            params["max_tokens"] = config.max_tokens
        if config.api_key:
            params["api_key"] = config.api_key

        return ChatOpenAI(**params)

    @staticmethod
    def _create_google_llm(config: LLMConfig) -> ChatGoogleGenerativeAI:
        """创建 Google Generative AI LLM 实例"""
        params = {
            "model": config.model_name,
            "temperature": config.temperature,
            **config.extra_params
        }

        if config.max_tokens:
            params["max_output_tokens"] = config.max_tokens
        if config.api_key:
            params["google_api_key"] = config.api_key

        return ChatGoogleGenerativeAI(**params)

    @staticmethod
    def _create_qwen_llm(config: LLMConfig) -> ChatOpenAI:
        """创建 通义千问 LLM 实例（使用 OpenAI 兼容接口）"""
        params = {
            "model": config.model_name,
            "temperature": config.temperature,
            "max_retries": 3,
            "base_url": config.api_base or "https://dashscope.aliyuncs.com/compatible-mode/v1",
            **config.extra_params
        }

        if config.max_tokens:
            params["max_tokens"] = config.max_tokens
            
        # API Key 优先级：配置中的 api_key > 环境变量 QWEN_API_KEY > 环境变量 DASHSCOPE_API_KEY
        api_key = config.api_key or settings.QWEN_API_KEY or settings.DASHSCOPE_API_KEY
        if api_key:
            params["api_key"] = api_key

        return ChatOpenAI(**params)


def get_llm(
        provider: str,
        model_name: str,
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs
) -> Union[BaseLLM, BaseChatModel]:
    """
    便捷函数：根据参数创建 LLM 模型

    Args:
        provider: 提供商名称
        model_name: 模型名称
        api_key: API 密钥
        temperature: 温度参数
        **kwargs: 其他配置参数

    Returns:
        LangChain LLM 实例
    """
    config = LLMConfig(
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        temperature=temperature,
        **kwargs
    )
    return LLMManager.get_llm(config)


# 预定义的常用模型配置
COMMON_LLM_MODELS = {
    "openai": {
        "gpt-4o": "gpt-4o",
        "gpt-4o-mini": "gpt-4o-mini",
        "gpt-4-turbo": "gpt-4-turbo-preview",
        "gpt-3.5-turbo": "gpt-3.5-turbo",
    },
    "deepseek": {
        "deepseek-chat": "deepseek-chat",
        "deepseek-resaoner": "deepseek-resaoner",
    },
    "huggingface": {
        "qwen2.5-7b": "Qwen/Qwen2.5-7B-Instruct",
        "qwen2.5-14b": "Qwen/Qwen2.5-14B-Instruct",
        "llama3.1-8b": "meta-llama/Llama-3.1-8B-Instruct",
        "glm4-9b": "THUDM/glm-4-9b-chat",
        "yi-6b": "01-ai/Yi-6B-Chat",
    },
    "ollama": {
        "llama3.1": "llama3.1",
        "qwen2.5": "qwen2.5",
        "glm4": "glm4",
        "deepseek-coder": "deepseek-coder",
        "codellama": "codellama",
    },
    "google": {
        "gemini-pro": "gemini-pro",
        "gemini-1.5-pro": "gemini-1.5-pro",
        "gemini-1.5-flash": "gemini-1.5-flash",
        "gemini-2.5-pro": "gemini-2.5-pro",
        "gemini-2.5-flash": "gemini-2.5-flash",
    },
    "qwen": {
        "qwen-turbo": "qwen-turbo",
        "qwen-plus": "qwen-plus",
        "qwen-max": "qwen-max",
        "qwen-long": "qwen-long",
        "qwen2.5-72b-instruct": "qwen2.5-72b-instruct",
        "qwen2.5-32b-instruct": "qwen2.5-32b-instruct",
        "qwen2.5-14b-instruct": "qwen2.5-14b-instruct",
        "qwen2.5-7b-instruct": "qwen2.5-7b-instruct",
    }
}


def get_available_llm_models(provider: str) -> Dict[str, str]:
    """
    获取指定提供商的可用 LLM 模型列表

    Args:
        provider: 提供商名称

    Returns:
        模型名称到模型ID的映射字典
    """
    return COMMON_LLM_MODELS.get(provider.lower(), {})
