import asyncio
from typing import Dict, Any, Optional
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.runnables import RunnableConfig

from common.logger import logger
from common.config import get_settings
from common.exceptions import CheckpointConnectionError
from infrastructure.db.async_pool import get_connection_pool, check_pool_health


class AsyncPostgresSaverManager:
    """
    管理 AsyncPostgresSaver 的生命周期
    
    遵循"快速失败"和"显式处理"原则：
    - 启动时强制验证，失败立即终止
    - 运行时带重试机制，失败抛出明确异常
    - 彻底移除 InMemorySaver 降级逻辑
    """

    # 重试配置
    MAX_RETRIES = 3
    BASE_DELAY = 1.0  # 秒
    MAX_DELAY = 30.0  # 秒

    def __init__(self):
        self._saver: Optional[AsyncPostgresSaver] = None
        self._initialized = False

    async def _check_health(self) -> bool:
        """
        检查 saver 健康状态
        
        验证连接池健康，并尝试执行一次简单的数据库操作。
        
        Returns:
            True 如果健康，False 否则
        """
        try:
            # 首先检查连接池健康
            pool_healthy = await check_pool_health()
            if not pool_healthy:
                logger.debug("[AsyncPostgresSaverManager] Pool health check failed")
                return False

            # 如果 saver 已初始化，尝试执行一次 get 操作验证
            if self._saver is not None:
                try:
                    # 使用一个测试 thread_id 执行 aget 操作（异步接口）
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
        """
        初始化 AsyncPostgresSaver
        
        从连接池获取连接创建 saver 实例。
        
        Raises:
            Exception: 初始化失败时抛出
        """
        pool = get_connection_pool()
        
        async with pool.connection() as conn:
            self._saver = AsyncPostgresSaver(conn)
            self._initialized = True
            
        logger.info("[AsyncPostgresSaverManager] AsyncPostgresSaver initialized successfully")

    async def initialize_and_verify(self) -> AsyncPostgresSaver:
        """
        初始化并验证 saver（用于启动时强制检查）
        
        初始化 saver 并执行一次数据库操作验证。
        
        Returns:
            AsyncPostgresSaver: 初始化并验证成功的 saver
            
        Raises:
            Exception: 初始化或验证失败时抛出
        """
        logger.info("[AsyncPostgresSaverManager] Initializing and verifying saver...")
        
        # 初始化 saver
        await self._initialize_saver()
        
        # 验证 saver 可用性（执行一次 aget 操作）
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
        获取 saver 实例，带重试和熔断机制
        
        如果 saver 已初始化且健康，直接返回。
        否则进入重试逻辑，重试耗尽后抛出 CheckpointConnectionError。
        
        Args:
            thread_id: 工作流线程ID，用于错误日志记录
            
        Returns:
            AsyncPostgresSaver: 可用的 saver 实例
            
        Raises:
            CheckpointConnectionError: 连接失败且重试耗尽时抛出
        """
        # 如果已初始化且健康，直接返回
        if self._saver is not None and await self._check_health():
            return self._saver

        # 需要重新初始化，进入重试逻辑
        logger.warning("[AsyncPostgresSaverManager] Saver not available, entering retry loop...")
        
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(f"[AsyncPostgresSaverManager] Retry attempt {attempt + 1}/{self.MAX_RETRIES}")
                
                # 尝试初始化
                await self._initialize_saver()
                
                # 验证健康状态
                if await self._check_health():
                    logger.info(f"[AsyncPostgresSaverManager] Saver available after {attempt + 1} attempts")
                    return self._saver
                else:
                    # 初始化成功但健康检查失败，清理后重试
                    logger.warning(f"[AsyncPostgresSaverManager] Saver initialized but health check failed")
                    self._saver = None
                    self._initialized = False
                    
            except Exception as e:
                last_error = e
                logger.warning(f"[AsyncPostgresSaverManager] Retry attempt {attempt + 1} failed: {e}")
                
                # 清理失败状态
                self._saver = None
                self._initialized = False
            
            # 计算退避延迟（指数退避）
            if attempt < self.MAX_RETRIES - 1:
                delay = min(self.BASE_DELAY * (2 ** attempt), self.MAX_DELAY)
                logger.info(f"[AsyncPostgresSaverManager] Retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)
        
        # 重试耗尽，抛出明确异常
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
        """
        关闭 saver
        
        清理 saver 引用，连接池由全局管理。
        """
        if self._saver is not None:
            logger.info("[AsyncPostgresSaverManager] Cleaning up saver reference")
            self._saver = None
            self._initialized = False

    def is_initialized(self) -> bool:
        """检查 saver 是否已初始化"""
        return self._initialized and self._saver is not None


# 全局管理器实例
_saver_manager: Optional[AsyncPostgresSaverManager] = None


def get_saver_manager() -> AsyncPostgresSaverManager:
    """获取 AsyncPostgresSaverManager 单例实例"""
    global _saver_manager
    if _saver_manager is None:
        _saver_manager = AsyncPostgresSaverManager()
    return _saver_manager


async def setup_checkpointer():
    """
    初始化 checkpoint 表（首次运行时需要调用）
    
    使用连接池获取连接来创建表。
    失败时抛出异常，不静默处理。
    
    Raises:
        Exception: 设置失败时抛出
    """
    settings = get_settings()
    
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
