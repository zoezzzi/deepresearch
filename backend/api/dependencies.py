from fastapi import Depends
from sqlalchemy.orm import Session
from contextlib import contextmanager

from infrastructure.db.session import SessionLocal
from core import (
    get_sse_manager,
    create_research_service,
    ResearchService
)
from infrastructure.sse.manager import SSEConnectionManager


@contextmanager
def get_db_session():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db():
    """FastAPI 兼容的数据库依赖函数"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_research_application_service_dep(
    db: Session = Depends(get_db)
):
    return create_research_service(db)


def get_sse_manager_dep():
    return get_sse_manager()
