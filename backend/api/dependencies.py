from fastapi import Depends
from sqlalchemy.orm import Session
from contextlib import contextmanager

from app.infrastructure.db.session import get_db_session as _get_db_session, get_db as _get_db
from app.scenarios.registry import ScenarioRegistry
from harness.events.manager import SSEConnectionManager


@contextmanager
def get_db_session():
    """统一使用 session.py 中的实现，避免重复定义"""
    with _get_db_session() as db:
        yield db


def get_db():
    """统一使用 session.py 中的实现，避免重复定义"""
    yield from _get_db()


def get_scenario_registry() -> ScenarioRegistry:
    return ScenarioRegistry


def get_sse_manager_dep():
    from app.service_factory import get_sse_manager
    return get_sse_manager()
