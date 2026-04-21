"""
LLM 客户端连接池

用于管理 LLM 客户端实例，减少重复创建的开销
"""
import asyncio
from typing import Dict, Any, Optional, Tuple
from harness.config import get_harness_settings
from harness.logger import logger
from harness.llm.langchain_client import LangChainClient

settings = get_harness_settings()


class LLMClientPool:
    """
    LLM 客户端连接池

    管理不同配置的 LLM 客户端实例，避免重复创建
    """
    
    def __init__(self):
        self._pool: Dict[Tuple[str, float], LangChainClient] = {}
        self._lock = asyncio.Lock()
        logger.info("[LLMClientPool] 初始化 LLM 客户端连接池")
    
    async def get_client(
        self,
        model: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> LangChainClient:
        """
        获取或创建 LLM 客户端

        Args:
            model: 模型名称（如果为 None，使用默认值）
            temperature: 温度参数（如果为 None，使用默认值）

        Returns:
            LangChainClient 实例
        """
        if model is None:
            model = settings.LLM_MODEL_ID
        if temperature is None:
            temperature = settings.LLM_TEMPERATURE
        
        key = (model, temperature)
        
        async with self._lock:
            if key not in self._pool:
                logger.debug(f"[LLMClientPool] 创建新的 LLM 客户端: model={model}, temperature={temperature}")
                client = LangChainClient()
                self._pool[key] = client
            else:
                logger.debug(f"[LLMClientPool] 复用已有的 LLM 客户端: model={model}, temperature={temperature}")
            
            return self._pool[key]
    
    def clear(self):
        """清空连接池"""
        self._pool.clear()
        logger.info("[LLMClientPool] 连接池已清空")
    
    @property
    def size(self) -> int:
        """当前连接池大小"""
        return len(self._pool)


# 全局单例
_pool_instance: Optional[LLMClientPool] = None


def get_llm_client_pool() -> LLMClientPool:
    """
    获取全局 LLM 客户端连接池单例

    Returns:
        LLMClientPool 实例
    """
    global _pool_instance
    if _pool_instance is None:
        _pool_instance = LLMClientPool()
    return _pool_instance
