from contextlib import contextmanager

from app.scenarios.registry import ScenarioRegistry
from harness.db.session import get_db as _get_db
from harness.db.session import get_db_session as _get_db_session
from harness.events.manager import SSEConnectionManager  # noqa: F401  兼容旧导入路径


@contextmanager
def get_db_session():
    """统一使用 session.py 中的实现，避免重复定义"""
    with _get_db_session() as db:
        yield db


def get_db():
    """统一使用 session.py 中的实现，避免重复定义"""
    yield from _get_db()


def get_scenario_registry() -> ScenarioRegistry:
    """Expose the scenario registry class itself (classmethod-based) as a DI dependency."""
    return ScenarioRegistry


def get_sse_manager_dep():
    """Resolve the SSE manager lazily to avoid importing app-level code at module load."""
    from app.service_factory import get_sse_manager

    return get_sse_manager()
