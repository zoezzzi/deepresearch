import os
import asyncio
from typing import Optional, AsyncGenerator, Dict, Any, Callable
from contextlib import asynccontextmanager
from functools import wraps

os.environ['PGCLIENTENCODING'] = 'UTF8'
os.environ['LANG'] = 'en_US.UTF-8'

from psycopg import AsyncConnection, OperationalError
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row

from common.logger import logger
from common.config import get_settings


def with_retry(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
    """
    重试装饰器，使用指数退避策略
    
    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟时间（秒）
        max_delay: 最大延迟时间（秒）
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except OperationalError as e:
                    last_exception = e
                    if attempt < max_retries:
                        # 计算指数退避延迟
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(
                            f"[DatabasePool] Operation failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"[DatabasePool] Operation failed after {max_retries + 1} attempts: {e}")
                        raise
                except Exception as e:
                    # 非 OperationalError 直接抛出
                    raise
            
            raise last_exception
        
        return wrapper
    return decorator


class DatabasePool:
    """
    PostgreSQL 异步连接池管理器
    
    使用 psycopg3 的 AsyncConnectionPool 实现连接池化管理，
    提供连接复用、自动重连、健康检查、连接探活、重试机制等功能。
    """

    def __init__(self):
        self._pool: Optional[AsyncConnectionPool] = None
        self._config: Optional[Dict[str, Any]] = None
        self._initialized = False

    def _build_conninfo(self) -> str:
        """构建 PostgreSQL 连接字符串"""
        settings = get_settings()
        return (
            f"host={settings.POSTGRES_HOST} "
            f"port={settings.POSTGRES_PORT} "
            f"dbname={settings.POSTGRES_DB} "
            f"user={settings.POSTGRES_USER} "
            f"password={settings.POSTGRES_PASSWORD}"
        )

    def _get_pool_config(self) -> Dict[str, Any]:
        """获取连接池配置参数"""
        settings = get_settings()
        return {
            "min_size": getattr(settings, 'DB_POOL_MIN_SIZE', 5),
            "max_size": getattr(settings, 'DB_POOL_MAX_SIZE', 20),
            "timeout": getattr(settings, 'DB_POOL_TIMEOUT', 30),
            "max_idle": getattr(settings, 'DB_POOL_MAX_IDLE', 300),
            "max_lifetime": getattr(settings, 'DB_POOL_MAX_LIFETIME', 3600),
            "check": AsyncConnectionPool.check_connection,
            "kwargs": {
                "row_factory": dict_row,
                "autocommit": False,
            }
        }

    async def initialize(self) -> None:
        """
        初始化连接池
        
        创建 AsyncConnectionPool 实例并等待其就绪。
        如果连接池已初始化，则跳过。
        """
        if self._initialized and self._pool is not None:
            logger.debug("[DatabasePool] Pool already initialized, skipping")
            return

        try:
            conninfo = self._build_conninfo()
            config = self._get_pool_config()
            
            logger.info(f"[DatabasePool] Initializing connection pool "
                       f"(min_size={config['min_size']}, max_size={config['max_size']})")

            self._pool = AsyncConnectionPool(
                conninfo=conninfo,
                **config
            )
            
            # 等待连接池就绪
            await self._pool.wait()
            self._initialized = True
            
            logger.info("[DatabasePool] Connection pool initialized successfully")
            
        except Exception as e:
            logger.error(f"[DatabasePool] Failed to initialize pool: {e}")
            self._pool = None
            self._initialized = False
            raise

    async def close(self) -> None:
        """
        关闭连接池
        
        优雅地关闭连接池，等待所有连接归还后关闭。
        """
        if self._pool is None:
            return

        try:
            logger.info("[DatabasePool] Closing connection pool")
            await self._pool.close()
            logger.info("[DatabasePool] Connection pool closed successfully")
        except Exception as e:
            logger.error(f"[DatabasePool] Error closing pool: {e}")
        finally:
            self._pool = None
            self._initialized = False

    async def _validate_connection(self, conn: AsyncConnection) -> bool:
        """
        验证连接是否可用（连接探活）
        
        在执行关键操作前执行 SELECT 1 验证连接状态。
        
        Args:
            conn: 数据库连接对象
            
        Returns:
            True 如果连接可用，False 否则
        """
        try:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
                result = await cur.fetchone()
                return result is not None and result.get('?column?') == 1
        except Exception as e:
            logger.warning(f"[DatabasePool] Connection validation failed: {e}")
            return False

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[AsyncConnection, None]:
        """
        获取数据库连接的上下文管理器
        
        使用示例:
            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT * FROM table")
                    results = await cur.fetchall()
        
        Yields:
            AsyncConnection: 数据库连接对象
            
        Raises:
            RuntimeError: 连接池未初始化
            Exception: 获取连接失败
        """
        if not self._initialized or self._pool is None:
            raise RuntimeError("[DatabasePool] Pool not initialized. Call initialize() first.")

        async with self._pool.connection() as conn:
            try:
                # 连接探活：验证连接是否可用
                if not await self._validate_connection(conn):
                    raise OperationalError("Connection validation failed")
                
                yield conn
            except Exception as e:
                logger.error(f"[DatabasePool] Error during connection usage: {e}")
                raise

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncConnection, None]:
        """
        获取带事务的数据库连接上下文管理器
        
        自动处理事务提交和回滚。
        
        使用示例:
            async with pool.transaction() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("INSERT INTO table VALUES (%s)", (value,))
                # 自动提交
        
        Yields:
            AsyncConnection: 数据库连接对象（在事务中）
        """
        async with self.connection() as conn:
            async with conn.transaction():
                try:
                    yield conn
                except Exception as e:
                    logger.error(f"[DatabasePool] Transaction error, rolling back: {e}")
                    raise

    @with_retry(max_retries=3, base_delay=1.0, max_delay=30.0)
    async def execute(self, query: str, params: Optional[tuple] = None) -> None:
        """
        执行 SQL 语句（不返回结果）
        
        带有重试机制，捕获 OperationalError 后使用指数退避重试。
        
        Args:
            query: SQL 查询语句
            params: 查询参数
        """
        async with self.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)

    @with_retry(max_retries=3, base_delay=1.0, max_delay=30.0)
    async def fetchone(self, query: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        """
        执行查询并返回单行结果
        
        带有重试机制，捕获 OperationalError 后使用指数退避重试。
        
        Args:
            query: SQL 查询语句
            params: 查询参数
            
        Returns:
            单行结果字典，如果没有结果则返回 None
        """
        async with self.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                return await cur.fetchone()

    @with_retry(max_retries=3, base_delay=1.0, max_delay=30.0)
    async def fetchall(self, query: str, params: Optional[tuple] = None) -> list:
        """
        执行查询并返回所有结果
        
        带有重试机制，捕获 OperationalError 后使用指数退避重试。
        
        Args:
            query: SQL 查询语句
            params: 查询参数
            
        Returns:
            结果列表
        """
        async with self.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                return await cur.fetchall()

    def get_stats(self) -> Dict[str, Any]:
        """
        获取连接池统计信息
        
        Returns:
            包含连接池状态的字典
        """
        if self._pool is None:
            return {"status": "not_initialized"}

        return {
            "status": "initialized" if self._initialized else "initializing",
            "size": self._pool.size,
            "max_size": self._pool.max_size,
            "min_size": self._pool.min_size,
            "available": self._pool.get_free_connections(),
            "waiting": len(getattr(self._pool, '_waiting', [])),
        }

    async def health_check(self) -> bool:
        """
        检查连接池健康状态
        
        Returns:
            True 如果连接池健康，False 否则
        """
        if not self._initialized or self._pool is None:
            return False

        try:
            async with self.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                    result = await cur.fetchone()
                    return result is not None and result.get('?column?') == 1
        except Exception as e:
            logger.warning(f"[DatabasePool] Health check failed: {e}")
            return False


# 全局连接池实例
_pool_instance: Optional[DatabasePool] = None


async def init_connection_pool() -> DatabasePool:
    """
    初始化全局连接池
    
    Returns:
        DatabasePool 实例
    """
    global _pool_instance
    if _pool_instance is None:
        _pool_instance = DatabasePool()
    
    await _pool_instance.initialize()
    return _pool_instance


async def close_connection_pool() -> None:
    """关闭全局连接池"""
    global _pool_instance
    if _pool_instance is not None:
        await _pool_instance.close()
        _pool_instance = None


def get_connection_pool() -> DatabasePool:
    """
    获取全局连接池实例
    
    Returns:
        DatabasePool 实例
        
    Raises:
        RuntimeError: 如果连接池未初始化
    """
    global _pool_instance
    if _pool_instance is None:
        raise RuntimeError(
            "[DatabasePool] Pool not initialized. "
            "Call init_connection_pool() first."
        )
    return _pool_instance


async def get_pool_stats() -> Dict[str, Any]:
    """获取连接池统计信息"""
    pool = get_connection_pool()
    return pool.get_stats()


async def check_pool_health() -> bool:
    """检查连接池健康状态"""
    try:
        pool = get_connection_pool()
        return await pool.health_check()
    except Exception:
        return False
