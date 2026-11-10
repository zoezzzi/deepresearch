"""
Trace 上下文管理

使用 contextvars 实现线程安全的 trace 上下文传递
"""

import contextvars
from typing import Any
from uuid import uuid4

trace_id_var = contextvars.ContextVar("trace_id", default=None)
workflow_id_var = contextvars.ContextVar("workflow_id", default=None)
span_id_var = contextvars.ContextVar("span_id", default=None)
langsmith_run_id_var = contextvars.ContextVar("langsmith_run_id", default=None)


def set_trace_context(
    trace_id: str | None = None,
    workflow_id: str | None = None,
    span_id: str | None = None,
    langsmith_run_id: str | None = None,
) -> dict[str, Any]:
    """Set any subset of trace context variables and return the reset tokens.

    The returned tokens must be passed to ``clear_trace_context`` in the same
    logical scope to avoid leaking context into unrelated tasks.
    """
    tokens = {}

    if trace_id:
        tokens["trace_id"] = trace_id_var.set(trace_id)
    if workflow_id:
        tokens["workflow_id"] = workflow_id_var.set(workflow_id)
    if span_id:
        tokens["span_id"] = span_id_var.set(span_id)
    if langsmith_run_id:
        tokens["langsmith_run_id"] = langsmith_run_id_var.set(langsmith_run_id)

    return tokens


def clear_trace_context(tokens: dict[str, Any]) -> None:
    """Restore the context values captured by ``set_trace_context``."""
    for name, token in tokens.items():
        if name == "trace_id":
            trace_id_var.reset(token)
        elif name == "workflow_id":
            workflow_id_var.reset(token)
        elif name == "span_id":
            span_id_var.reset(token)
        elif name == "langsmith_run_id":
            langsmith_run_id_var.reset(token)


def get_trace_context() -> dict[str, str | None]:
    """Snapshot the current trace context (None for unset values)."""
    return {
        "trace_id": trace_id_var.get(),
        "workflow_id": workflow_id_var.get(),
        "span_id": span_id_var.get(),
        "langsmith_run_id": langsmith_run_id_var.get(),
    }


def generate_trace_id() -> str:
    """Generate a short, log-friendly trace identifier."""
    return f"trace_{uuid4().hex[:16]}"


def generate_span_id() -> str:
    """Generate a short, log-friendly span identifier."""
    return f"span_{uuid4().hex[:16]}"


def get_current_langsmith_run_id() -> str | None:
    """获取当前的 LangSmith 运行 ID"""
    return langsmith_run_id_var.get()


def set_current_langsmith_run_id(run_id: str | None) -> None:
    """设置当前的 LangSmith 运行 ID"""
    langsmith_run_id_var.set(run_id)
