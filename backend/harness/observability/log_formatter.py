"""
结构化日志格式化器

在日志中注入 trace 上下文信息
"""

from harness.observability.trace_context import trace_id_var


def get_trace_format() -> str:
    return (
        "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
        "trace_id={extra[trace_id]} | "
        "{name}:{function}:{line} - {message}"
    )


def trace_context_filter(record):
    record["extra"]["trace_id"] = trace_id_var.get() or "-"
    return True
