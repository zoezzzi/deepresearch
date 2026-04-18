from fastapi import Depends
from sqlalchemy.orm import Session
from contextlib import contextmanager

from app.infrastructure.db.session import SessionLocal
from app.scenarios.registry import ScenarioRegistry
from harness.events.manager import SSEConnectionManager


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
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_scenario_registry() -> ScenarioRegistry:
    return ScenarioRegistry


def get_sse_manager_dep():
    from app.service_factory import get_sse_manager
    return get_sse_manager()
