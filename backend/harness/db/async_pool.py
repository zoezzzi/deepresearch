import asyncio
import os
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any

os.environ["PGCLIENTENCODING"] = "UTF8"
os.environ["LANG"] = "en_US.UTF-8"

from psycopg import AsyncConnection, OperationalError
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from harness.config import get_harness_settings
from harness.logger import logger


def with_retry(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
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
                        delay = min(base_delay * (2**attempt), max_delay)
                        logger.warning(
                            f"[DatabasePool] Operation failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"[DatabasePool] Operation failed after {max_retries + 1} attempts: {e}"
                        )
                        raise
                except Exception:
                    raise

            raise last_exception

        return wrapper

    return decorator


class DatabasePool:
    def __init__(self):
        self._pool: AsyncConnectionPool | None = None
        self._config: dict[str, Any] | None = None
        self._initialized = False

    def _build_conninfo(self) -> str:
        settings = get_harness_settings()
        return (
            f"host={settings.POSTGRES_HOST} "
            f"port={settings.POSTGRES_PORT} "
            f"dbname={settings.POSTGRES_DB} "
            f"user={settings.POSTGRES_USER} "
            f"password={settings.POSTGRES_PASSWORD}"
        )

    def _get_pool_config(self) -> dict[str, Any]:
        settings = get_harness_settings()
        return {
            "min_size": getattr(settings, "DB_POOL_MIN_SIZE", 5),
            "max_size": getattr(settings, "DB_POOL_MAX_SIZE", 20),
            "timeout": getattr(settings, "DB_POOL_TIMEOUT", 30),
            "max_idle": getattr(settings, "DB_POOL_MAX_IDLE", 300),
            "max_lifetime": getattr(settings, "DB_POOL_MAX_LIFETIME", 3600),
            "check": AsyncConnectionPool.check_connection,
            "kwargs": {
                "row_factory": dict_row,
                "autocommit": False,
            },
        }

    async def initialize(self) -> None:
        if self._initialized and self._pool is not None:
            logger.debug("[DatabasePool] Pool already initialized, skipping")
            return

        try:
            conninfo = self._build_conninfo()
            config = self._get_pool_config()

            logger.info(
                f"[DatabasePool] Initializing connection pool "
                f"(min_size={config['min_size']}, max_size={config['max_size']})"
            )

            self._pool = AsyncConnectionPool(conninfo=conninfo, **config)

            await self._pool.wait()
            self._initialized = True

            logger.info("[DatabasePool] Connection pool initialized successfully")

        except Exception as e:
            logger.error(f"[DatabasePool] Failed to initialize pool: {e}")
            self._pool = None
            self._initialized = False
            raise

    async def close(self) -> None:
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
        try:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
                result = await cur.fetchone()
                return result is not None and result.get("?column?") == 1
        except Exception as e:
            logger.warning(f"[DatabasePool] Connection validation failed: {e}")
            return False

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[AsyncConnection, None]:
        if not self._initialized or self._pool is None:
            raise RuntimeError("[DatabasePool] Pool not initialized. Call initialize() first.")

        async with self._pool.connection() as conn:
            try:
                if not await self._validate_connection(conn):
                    raise OperationalError("Connection validation failed")

                yield conn
            except Exception as e:
                logger.error(f"[DatabasePool] Error during connection usage: {e}")
                raise

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncConnection, None]:
        async with self.connection() as conn, conn.transaction():
            try:
                yield conn
            except Exception as e:
                logger.error(f"[DatabasePool] Transaction error, rolling back: {e}")
                raise

    @with_retry(max_retries=3, base_delay=1.0, max_delay=30.0)
    async def execute(self, query: str, params: tuple | None = None) -> None:
        async with self.connection() as conn, conn.cursor() as cur:
            await cur.execute(query, params)

    @with_retry(max_retries=3, base_delay=1.0, max_delay=30.0)
    async def fetchone(self, query: str, params: tuple | None = None) -> dict[str, Any] | None:
        async with self.connection() as conn, conn.cursor() as cur:
            await cur.execute(query, params)
            return await cur.fetchone()

    @with_retry(max_retries=3, base_delay=1.0, max_delay=30.0)
    async def fetchall(self, query: str, params: tuple | None = None) -> list:
        async with self.connection() as conn, conn.cursor() as cur:
            await cur.execute(query, params)
            return await cur.fetchall()

    def get_stats(self) -> dict[str, Any]:
        if self._pool is None:
            return {"status": "not_initialized"}

        stats = self._pool.get_stats()
        return {
            "status": "initialized" if self._initialized else "initializing",
            "size": stats.get("pool_size", 0),
            "max_size": stats.get("pool_max", 0),
            "min_size": stats.get("pool_min", 0),
            "available": stats.get("pool_available", 0),
            "waiting": stats.get("requests_waiting", 0),
        }

    async def health_check(self) -> bool:
        if not self._initialized or self._pool is None:
            return False

        try:
            async with self.connection() as conn, conn.cursor() as cur:
                await cur.execute("SELECT 1")
                result = await cur.fetchone()
                return result is not None and result.get("?column?") == 1
        except Exception as e:
            logger.warning(f"[DatabasePool] Health check failed: {e}")
            return False


_pool_instance: DatabasePool | None = None


async def init_connection_pool() -> DatabasePool:
    global _pool_instance
    if _pool_instance is None:
        _pool_instance = DatabasePool()

    await _pool_instance.initialize()
    return _pool_instance


async def close_connection_pool() -> None:
    global _pool_instance
    if _pool_instance is not None:
        await _pool_instance.close()
        _pool_instance = None


def get_connection_pool() -> DatabasePool:
    global _pool_instance
    if _pool_instance is None:
        raise RuntimeError(
            "[DatabasePool] Pool not initialized. Call init_connection_pool() first."
        )
    return _pool_instance


async def get_pool_stats() -> dict[str, Any]:
    pool = get_connection_pool()
    return pool.get_stats()


async def check_pool_health() -> bool:
    try:
        pool = get_connection_pool()
        return await pool.health_check()
    except Exception:
        return False
