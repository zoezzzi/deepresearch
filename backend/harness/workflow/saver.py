"""
工作流状态持久化管理器

提供 AsyncPostgresSaver 的初始化和访问管理
用于 LangGraph 工作流的状态持久化
"""
import asyncio
from typing import Dict, Any, Optional
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.runnables import RunnableConfig

from harness.logger import logger
from harness.config import get_harness_settings
from harness.db.async_pool import get_connection_pool, check_pool_health


class CheckpointConnectionError(Exception):
    """Checkpoint 连接错误"""
    def __init__(self, message: str, thread_id: str = None, retry_count: int = 0):
        self.thread_id = thread_id
        self.retry_count = retry_count
        super().__init__(f"[CheckpointConnectionError] {message} | thread_id={thread_id} | retries={retry_count}")


class AsyncPostgresSaverManager:
    """
    AsyncPostgresSaver 管理器
    
    负责管理 AsyncPostgresSaver 的生命周期：
    - 初始化
    - 健康检查
    - 自动重连
    - 清理
    """
    MAX_RETRIES = 3
    BASE_DELAY = 1.0
    MAX_DELAY = 30.0

    def __init__(self):
        self._saver: Optional[AsyncPostgresSaver] = None
        self._initialized = False

    async def _check_health(self) -> bool:
        """检查 saver 健康状态"""
        try:
            pool_healthy = await check_pool_health()
            if not pool_healthy:
                logger.debug("[AsyncPostgresSaverManager] Pool health check failed")
                return False

            if self._saver is not None:
                try:
                    test_config = RunnableConfig(configurable={"thread_id": "__health_check__"})
                    await self._saver.aget(test_config)
                    return True
                except Exception as e:
                    logger.debug(f"[AsyncPostgresSaverManager] Saver health check failed: {e}")
                    return False

            return True
        except Exception as e:
            logger.debug(f"[AsyncPostgresSaverManager] Health check error: {e}")
            return False

    async def _initialize_saver(self) -> None:
        """初始化 saver"""
        pool = get_connection_pool()

        async with pool.connection() as conn:
            self._saver = AsyncPostgresSaver(conn)
            self._initialized = True

        logger.info("[AsyncPostgresSaverManager] AsyncPostgresSaver initialized successfully")

    async def initialize_and_verify(self) -> AsyncPostgresSaver:
        """初始化并验证 saver"""
        logger.info("[AsyncPostgresSaverManager] Initializing and verifying saver...")

        await self._initialize_saver()

        test_config = RunnableConfig(configurable={"thread_id": "__init_verify__"})
        try:
            await self._saver.aget(test_config)
            logger.info("[AsyncPostgresSaverManager] Saver initialized and verified successfully")
            return self._saver
        except Exception as e:
            logger.error(f"[AsyncPostgresSaverManager] Saver verification failed: {e}")
            self._saver = None
            self._initialized = False
            raise

    async def get_saver(self, thread_id: str = None) -> AsyncPostgresSaver:
        """
        获取 saver 实例
        
        如果 saver 不可用，会自动重试初始化
        """
        if self._saver is not None and await self._check_health():
            return self._saver

        logger.warning("[AsyncPostgresSaverManager] Saver not available, entering retry loop...")

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(f"[AsyncPostgresSaverManager] Retry attempt {attempt + 1}/{self.MAX_RETRIES}")

                await self._initialize_saver()

                if await self._check_health():
                    logger.info(f"[AsyncPostgresSaverManager] Saver available after {attempt + 1} attempts")
                    return self._saver
                else:
                    logger.warning(f"[AsyncPostgresSaverManager] Saver initialized but health check failed")
                    self._saver = None
                    self._initialized = False

            except Exception as e:
                last_error = e
                logger.warning(f"[AsyncPostgresSaverManager] Retry attempt {attempt + 1} failed: {e}")

                self._saver = None
                self._initialized = False

            if attempt < self.MAX_RETRIES - 1:
                delay = min(self.BASE_DELAY * (2 ** attempt), self.MAX_DELAY)
                logger.info(f"[AsyncPostgresSaverManager] Retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)

        error_msg = f"无法连接到 Checkpoint 存储，已重试 {self.MAX_RETRIES} 次"
        if last_error:
            error_msg += f"，最后错误: {last_error}"

        logger.error(f"[AsyncPostgresSaverManager] {error_msg}")
        raise CheckpointConnectionError(
            message=error_msg,
            thread_id=thread_id,
            retry_count=self.MAX_RETRIES
        )

    async def close(self):
        """关闭 saver"""
        if self._saver is not None:
            logger.info("[AsyncPostgresSaverManager] Cleaning up saver reference")
            self._saver = None
            self._initialized = False

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized and self._saver is not None


# 全局单例实例
_saver_manager: Optional[AsyncPostgresSaverManager] = None


def get_saver_manager() -> AsyncPostgresSaverManager:
    """获取 saver 管理器单例"""
    global _saver_manager
    if _saver_manager is None:
        _saver_manager = AsyncPostgresSaverManager()
    return _saver_manager


def reset_saver_manager():
    """重置 saver 管理器（主要用于测试）"""
    global _saver_manager
    _saver_manager = None


async def setup_checkpointer():
    """
    设置 checkpoint 表
    
    在应用启动时调用，确保数据库表已创建
    """
    settings = get_harness_settings()

    logger.info(f"[AsyncPostgresSaverManager] Setting up checkpoint tables for database: {settings.POSTGRES_DB}")

    try:
        pool = get_connection_pool()
        async with pool.connection() as conn:
            saver = AsyncPostgresSaver(conn)
            await saver.setup()
            logger.info("[AsyncPostgresSaverManager] Checkpoint tables verified/created successfully")
    except Exception as e:
        logger.error(f"[AsyncPostgresSaverManager] Failed to setup checkpoint tables: {e}")
        import traceback
        logger.error(f"[AsyncPostgresSaverManager] Traceback: {traceback.format_exc()}")
        raise RuntimeError(f"Checkpoint 表初始化失败: {e}") from e
