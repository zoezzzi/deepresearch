"""
Trace 上下文管理

使用 contextvars 实现线程安全的 trace 上下文传递
"""
import contextvars
from typing import Optional, Dict, Any
from uuid import uuid4


trace_id_var = contextvars.ContextVar('trace_id', default=None)
workflow_id_var = contextvars.ContextVar('workflow_id', default=None)
span_id_var = contextvars.ContextVar('span_id', default=None)
langsmith_run_id_var = contextvars.ContextVar('langsmith_run_id', default=None)


def set_trace_context(
    trace_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    span_id: Optional[str] = None,
    langsmith_run_id: Optional[str] = None
) -> Dict[str, Any]:
    tokens = {}

    if trace_id:
        tokens['trace_id'] = trace_id_var.set(trace_id)
    if workflow_id:
        tokens['workflow_id'] = workflow_id_var.set(workflow_id)
    if span_id:
        tokens['span_id'] = span_id_var.set(span_id)
    if langsmith_run_id:
        tokens['langsmith_run_id'] = langsmith_run_id_var.set(langsmith_run_id)

    return tokens


def clear_trace_context(tokens: Dict[str, Any]) -> None:
    for name, token in tokens.items():
        if name == 'trace_id':
            trace_id_var.reset(token)
        elif name == 'workflow_id':
            workflow_id_var.reset(token)
        elif name == 'span_id':
            span_id_var.reset(token)
        elif name == 'langsmith_run_id':
            langsmith_run_id_var.reset(token)


def get_trace_context() -> Dict[str, Optional[str]]:
    return {
        'trace_id': trace_id_var.get(),
        'workflow_id': workflow_id_var.get(),
        'span_id': span_id_var.get(),
        'langsmith_run_id': langsmith_run_id_var.get(),
    }


def generate_trace_id() -> str:
    return f"trace_{uuid4().hex[:16]}"


def generate_span_id() -> str:
    return f"span_{uuid4().hex[:16]}"


def get_current_langsmith_run_id() -> Optional[str]:
    """获取当前的 LangSmith 运行 ID"""
    return langsmith_run_id_var.get()


def set_current_langsmith_run_id(run_id: Optional[str]) -> None:
    """设置当前的 LangSmith 运行 ID"""
    langsmith_run_id_var.set(run_id)
