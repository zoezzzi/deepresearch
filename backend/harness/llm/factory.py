"""LLM client factory with a process-wide cache.

The cache key is the provider name and entries carry a TTL. Expired clients are
closed asynchronously when an event loop is available, so destructors never
block the request thread.
"""

import asyncio
import threading
import time

from harness.config import get_harness_settings
from harness.llm.base import LLMClient
from harness.llm.langchain_client import LangChainClient
from harness.logger import logger

settings = get_harness_settings()

_TTL_SECONDS = 30 * 60

_client_cache: dict[str, tuple[LLMClient, float]] = {}
_cache_lock = threading.Lock()


def _schedule_client_close(client: LLMClient) -> None:
    """调度异步关闭旧客户端，释放底层 HTTP 连接池。"""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(client.close())
    except RuntimeError:
        logger.warning("[LLMClientCache] No running event loop, cannot close old client")


class LLMFactory:
    """Map provider names to client implementations.

    All providers reuse ``LangChainClient`` (OpenAI-compatible protocol) by
    default; ``register_client`` swaps in a custom implementation.
    """

    _clients: dict[str, type[LLMClient]] = {
        "qwen": LangChainClient,
        "langchain": LangChainClient,
        "openai": LangChainClient,
        "custom": LangChainClient,
        "ollama": LangChainClient,
        "lmstudio": LangChainClient,
    }

    @classmethod
    def register_client(cls, name: str, client_class: type[LLMClient]) -> None:
        """Override the implementation used for a provider name."""
        cls._clients[name] = client_class
        logger.info(f"Registered LLM client: {name}")

    @classmethod
    def create_client(cls, name: str | None = None) -> LLMClient:
        """Instantiate a new (uncached) client for the given provider."""
        if name is None:
            name = settings.LLM_PROVIDER

        if name not in cls._clients:
            raise ValueError(f"Unknown LLM client: {name}. Available: {list(cls._clients.keys())}")
        logger.debug(f"Creating LLM client: {name}")
        return cls._clients[name]()


def get_llm_client(name: str | None = None) -> LLMClient:
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

    old_client = None
    with _cache_lock:
        entry = _client_cache.get(cache_key)
        if entry is not None:
            client, created_at = entry
            if time.monotonic() - created_at < _TTL_SECONDS:
                return client

        old_entry = _client_cache.get(cache_key)
        if old_entry is not None:
            old_client = old_entry[0]

        logger.debug(f"[LLMClientCache] Creating new LLM client: {cache_key}")
        _client_cache[cache_key] = (LLMFactory.create_client(name), time.monotonic())

    if old_client is not None:
        _schedule_client_close(old_client)

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


async def remove_llm_client(name: str | None = None):
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
