import os
import time
import functools
from typing import Callable, TypeVar, Any, Generator, Optional

# Set environment variables to fix UnicodeDecodeError on Windows
os.environ['PGCLIENTENCODING'] = 'UTF8'
os.environ['LANG'] = 'en_US.UTF-8'

from sqlalchemy import create_engine, exc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from harness.logger import logger
from harness.config import get_harness_settings

settings = get_harness_settings()

engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=15,
    max_overflow=30,
    pool_timeout=30,
    pool_recycle=1800,
    connect_args={
        "connect_timeout": 10,
        "options": (
            "-c idle_in_transaction_session_timeout=300000 "
            "-c statement_timeout=300000 "
            "-c idle_session_timeout=600000"
        )
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

T = TypeVar('T')


def with_db_retry(max_attempts: int = 3, retry_delay: float = 1.0) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """数据库操作重试装饰器 - 处理连接断开等临时错误"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except (exc.OperationalError, exc.DBAPIError) as e:
                    last_exception = e
                    is_disconnect = (
                        isinstance(e, exc.OperationalError) or
                        (hasattr(e, 'connection_invalidated') and e.connection_invalidated)
                    )
                    
                    if not is_disconnect:
                        raise
                    
                    if attempt < max_attempts - 1:
                        wait_time = retry_delay * (2 ** attempt)  # 指数退避
                        logger.warning(f"Database connection error, retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_attempts}): {e}")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Database connection failed after {max_attempts} attempts: {e}")
                        raise
            
            # 理论不会到达这里，但为了类型安全
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry loop exit")
        return wrapper
    return decorator


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """统一的数据库 Session 上下文管理器"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Database error: {e}")
        try:
            db.rollback()
        except Exception:
            logger.warning("Rollback failed, session may be invalid")
        raise
    finally:
        try:
            db.close()
        except Exception:
            pass


def get_db():
    """FastAPI 兼容的数据库依赖函数 - 统一入口"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Database error: {e}")
        try:
            db.rollback()
        except Exception:
            logger.warning("Rollback failed, session may be invalid")
        raise
    finally:
        try:
            db.close()
        except Exception:
            pass


def init_db() -> None:
    from . import models
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized (PostgreSQL)")
