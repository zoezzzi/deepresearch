from typing import Dict, Any, Optional
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langchain_core.runnables import RunnableConfig
from infrastructure.logger import logger
from infrastructure.config import get_settings
from common.utils.time_utils import get_current_utc_time


class InMemorySaver(BaseCheckpointSaver):
    serde = JsonPlusSerializer()

    def __init__(self):
        super().__init__()
        self._storage: Dict[str, Dict[str, Any]] = {}
        logger.warning("InMemorySaver initialized - this should only be used for testing!")

    def get(self, config: RunnableConfig) -> Optional[Dict[str, Any]]:
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return None
        
        checkpoint = self._storage.get(thread_id)
        if checkpoint:
            logger.debug(f"Retrieved checkpoint for thread {thread_id}")
        return checkpoint

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> RunnableConfig:
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            raise ValueError("thread_id is required in config")
        
        self._storage[thread_id] = {
            **checkpoint,
            "metadata": metadata,
            "saved_at": get_current_utc_time()
        }
        logger.debug(f"Saved checkpoint for thread {thread_id}")
        return config

    def list(self, config: RunnableConfig, limit: Optional[int] = None) -> Any:
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return []
        
        checkpoint = self._storage.get(thread_id)
        if checkpoint:
            return [checkpoint]
        return []


_in_memory_saver_instance: Optional[InMemorySaver] = None


def get_in_memory_saver() -> InMemorySaver:
    global _in_memory_saver_instance
    if _in_memory_saver_instance is None:
        _in_memory_saver_instance = InMemorySaver()
    return _in_memory_saver_instance


class AsyncPostgresSaverManager:
    """
    管理 AsyncPostgresSaver 的生命周期
    由于 AsyncPostgresSaver 是异步上下文管理器，需要通过此类来管理
    """

    def __init__(self):
        self._db_uri = None
        self._saver = None
        self._is_in_memory = False
        self._context_manager = None

    async def _is_connection_alive(self) -> bool:
        """
        检查数据库连接是否仍然存活
        通过尝试使用 saver 来检测连接状态
        """
        if self._saver is None or self._is_in_memory:
            return False

        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            if isinstance(self._saver, AsyncPostgresSaver):
                # 尝试执行一个简单的操作来检测连接
                # 不直接访问私有属性，而是通过公共方法
                # 这里我们使用一个简单的配置来测试连接
                test_config = {"configurable": {"thread_id": "test-connection-check"}}
                # 尝试获取 checkpoint（即使不存在也会测试连接）
                await self._saver.get(test_config)
                return True
        except Exception as e:
            logger.warning(f"[AsyncPostgresSaverManager] Connection check failed: {e}")
            return False
        return False

    async def _close_saver(self):
        """安全关闭当前的 saver 连接"""
        if self._context_manager and not self._is_in_memory:
            try:
                await self._context_manager.__aexit__(None, None, None)
                logger.info("[AsyncPostgresSaverManager] Previous saver connection closed")
            except Exception as e:
                logger.warning(f"[AsyncPostgresSaverManager] Error closing previous saver: {e}")
            finally:
                self._saver = None
                self._context_manager = None

    async def get_saver(self):
        """
        在异步上下文中获取 saver 实例
        如果尚未初始化或连接已关闭，则创建新的连接
        """
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        # 检查现有连接是否仍然存活
        if self._saver is not None and not self._is_in_memory:
            is_alive = await self._is_connection_alive()
            if not is_alive:
                logger.error("[ALERT] 数据库连接已关闭，正在重新建立连接")
                logger.error("[ALERT] 这可能是由于 PostgreSQL 空闲超时或网络问题导致")
                logger.error("[ALERT] 建议检查 PostgreSQL 的 idle_in_transaction_session_timeout 配置")
                await self._close_saver()

        if self._saver is None:
            settings = get_settings()

            self._db_uri = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
            logger.info(f"[AsyncPostgresSaverManager] Initializing with database URL: {self._db_uri.replace(settings.POSTGRES_PASSWORD, '***')}")

            try:
                # 创建 AsyncPostgresSaver 实例（在上下文中）
                self._context_manager = AsyncPostgresSaver.from_conn_string(self._db_uri)
                self._saver = await self._context_manager.__aenter__()
                self._is_in_memory = False
                logger.info("[AsyncPostgresSaverManager] AsyncPostgresSaver initialized successfully")
            except Exception as e:
                logger.error(f"[AsyncPostgresSaverManager] Failed to initialize AsyncPostgresSaver: {e}")
                # 回退到 InMemorySaver
                logger.warning("[AsyncPostgresSaverManager] Falling back to InMemorySaver")
                self._saver = get_in_memory_saver()
                self._is_in_memory = True

        return self._saver
    
    async def close(self):
        """关闭 saver 连接"""
        if self._context_manager and not self._is_in_memory:
            try:
                await self._context_manager.__aexit__(None, None, None)
                logger.info("[AsyncPostgresSaverManager] AsyncPostgresSaver closed successfully")
            except Exception as e:
                logger.error(f"[AsyncPostgresSaverManager] Error closing AsyncPostgresSaver: {e}")
            finally:
                self._saver = None
                self._context_manager = None
    
    def is_in_memory(self) -> bool:
        """检查是否使用 InMemorySaver（回退模式）"""
        return self._is_in_memory


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
    注意：现在通过 AsyncPostgresSaverManager 管理，此方法主要用于兼容性
    """
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg import AsyncConnection
        
        settings = get_settings()
        
        # AsyncPostgresSaver.from_conn_string 需要 key=value 格式的连接字符串
        # 而不是 postgresql:// URL 格式
        conninfo = (
            f"host={settings.POSTGRES_HOST} "
            f"port={settings.POSTGRES_PORT} "
            f"dbname={settings.POSTGRES_DB} "
            f"user={settings.POSTGRES_USER} "
            f"password={settings.POSTGRES_PASSWORD}"
        )
        
        logger.info(f"[AsyncPostgresSaverManager] Setting up checkpoint for database: {settings.POSTGRES_DB}")
        
        # 创建数据库连接（autocommit=True 避免事务块问题）
        conn = await AsyncConnection.connect(conninfo, autocommit=True)
        
        try:
            # 创建 saver 实例
            saver = AsyncPostgresSaver(conn)
            
            # 确保表已创建
            await saver.setup()
            logger.info("[AsyncPostgresSaverManager] Checkpoint tables verified/created")
        finally:
            # 关闭连接
            await conn.close()
            
    except Exception as e:
        logger.error(f"[AsyncPostgresSaverManager] Failed to setup checkpoint tables: {e}")
        import traceback
        logger.error(f"[AsyncPostgresSaverManager] Traceback: {traceback.format_exc()}")
        # 不再抛出异常，让应用继续启动
        logger.warning("[AsyncPostgresSaverManager] Application will start without checkpoint persistence")


# 兼容性：保留旧的函数名，但返回管理器
async def get_async_postgres_saver():
    """
    兼容性函数，返回 AsyncPostgresSaverManager 实例
    注意：此函数现在返回管理器，需要通过 manager.get_saver() 获取实际的 saver
    """
    logger.warning("[Deprecated] get_async_postgres_saver() is deprecated, use get_saver_manager() instead")
    return get_saver_manager()
