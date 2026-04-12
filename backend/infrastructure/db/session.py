import os

# Set environment variables to fix UnicodeDecodeError on Windows
os.environ['PGCLIENTENCODING'] = 'UTF8'
os.environ['LANG'] = 'en_US.UTF-8'

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator
from common.logger import logger
from common.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600,
    connect_args={
        "connect_timeout": 10,
        "options": "-c idle_in_transaction_session_timeout=60000"
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def get_db():
    """FastAPI 兼容的数据库依赖函数"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    from . import models
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized (PostgreSQL)")
