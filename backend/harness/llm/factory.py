from typing import Dict, Type, Optional, Tuple
import threading
import time
from harness.llm.base import LLMClient
from harness.llm.langchain_client import LangChainClient
from harness.config import get_harness_settings
from harness.logger import logger

settings = get_harness_settings()

_TTL_SECONDS = 30 * 60

_client_cache: Dict[str, Tuple[LLMClient, float]] = {}
_cache_lock = threading.Lock()


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

    使用双重检查锁定模式：
    1. 快速路径（无锁）：缓存命中时直接返回，零锁开销
    2. 慢速路径（加锁）：仅在首次创建或 TTL 过期时获取锁

    缓存自动过期：30 分钟未访问的实例将被重新创建

    Args:
        name: LLM 提供商名称（如果为 None，使用默认值）

    Returns:
        LLMClient 实例
    """
    cache_key = name or settings.LLM_PROVIDER

    entry = _client_cache.get(cache_key)
    if entry is not None:
        client, created_at = entry
        if time.monotonic() - created_at < _TTL_SECONDS:
            return client

    with _cache_lock:
        entry = _client_cache.get(cache_key)
        if entry is not None:
            client, created_at = entry
            if time.monotonic() - created_at < _TTL_SECONDS:
                return client
        logger.debug(f"[LLMClientCache] Creating new LLM client: {cache_key}")
        _client_cache[cache_key] = (LLMFactory.create_client(name), time.monotonic())

    return _client_cache[cache_key][0]


async def clear_llm_client_cache():
    """清空所有 LLM 客户端缓存，先关闭底层连接再释放实例"""
    with _cache_lock:
        clients = [c for c, _ in _client_cache.values()]
        _client_cache.clear()
    for client in clients:
        try:
            await client.close()
        except Exception as e:
            logger.warning(f"[LLMClientCache] Error closing client: {e}")
    logger.info("[LLMClientCache] Cache cleared")


async def remove_llm_client(name: Optional[str] = None):
    """
    移除指定 LLM 客户端缓存

    用于配置变更后定向清理某个客户端的缓存，避免全局清空的影响。

    Args:
        name: LLM 提供商名称（如果为 None，使用默认值）
    """
    cache_key = name or settings.LLM_PROVIDER
    removed_client = None
    with _cache_lock:
        if cache_key in _client_cache:
            removed_client, _ = _client_cache.pop(cache_key)
    if removed_client is not None:
        try:
            await removed_client.close()
        except Exception as e:
            logger.warning(f"[LLMClientCache] Error closing client: {e}")
        logger.info(f"[LLMClientCache] Removed cached client: {cache_key}")