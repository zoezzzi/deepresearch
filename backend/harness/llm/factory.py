from typing import Dict, Type, Optional
from harness.llm.base import LLMClient
from harness.llm.langchain_client import LangChainClient
from harness.config import get_harness_settings
from harness.logger import logger

settings = get_harness_settings()


# 简单的客户端缓存（代替连接池，保持同步 API 兼容性）
_client_cache: Dict[str, LLMClient] = {}


class LLMFactory:
    _clients: Dict[str, Type[LLMClient]] = {
        "qwen": LangChainClient,
        "langchain": LangChainClient,
        "openai": LangChainClient,
        "custom": LangChainClient,
        "ollama": LangChainClient,
        "lmstudio": LangChainClient
    }

    @classmethod
    def register_client(cls, name: str, client_class: Type[LLMClient]) -> None:
        cls._clients[name] = client_class
        logger.info(f"Registered LLM client: {name}")

    @classmethod
    def create_client(cls, name: Optional[str] = None) -> LLMClient:
        if name is None:
            name = settings.LLM_PROVIDER
        
        if name not in cls._clients:
            raise ValueError(f"Unknown LLM client: {name}. Available: {list(cls._clients.keys())}")
        logger.debug(f"Creating LLM client: {name}")
        return cls._clients[name]()


def get_llm_client(name: Optional[str] = None) -> LLMClient:
    """
    获取 LLM 客户端（使用缓存进行复用）

    Args:
        name: LLM 提供商名称（如果为 None，使用默认值）

    Returns:
        LLMClient 实例
    """
    cache_key = name or settings.LLM_PROVIDER
    
    if cache_key not in _client_cache:
        logger.debug(f"[LLMClientCache] 创建新的 LLM 客户端: {cache_key}")
        _client_cache[cache_key] = LLMFactory.create_client(name)
    else:
        logger.debug(f"[LLMClientCache] 复用已有的 LLM 客户端: {cache_key}")
    
    return _client_cache[cache_key]


def clear_llm_client_cache():
    """清空 LLM 客户端缓存"""
    _client_cache.clear()
    logger.info("[LLMClientCache] 缓存已清空")


