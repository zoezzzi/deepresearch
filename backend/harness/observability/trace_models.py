"""
Trace 数据模型定义

定义追踪链路相关的 Pydantic 模型
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkflowTraceCreate(BaseModel):
    trace_id: str
    workflow_id: str
    request_id: str | None = None
    scenario_id: str
    started_at: datetime
    status: str = "running"
    langsmith_run_id: str | None = None


class WorkflowTraceUpdate(BaseModel):
    completed_at: datetime | None = None
    duration_ms: int | None = None
    status: str | None = None
    langsmith_run_id: str | None = None
    langsmith_url: str | None = None
    execute_duration_ms: int | None = None


class TaskTraceCreate(BaseModel):
    trace_id: str
    workflow_id: str
    task_id: str
    span_id: str
    task_title: str
    task_order: int
    started_at: datetime
    status: str = "running"
    input_query: str | None = None
    input_intent: str | None = None
    langsmith_run_id: str | None = None
    retry_count: int = 0


class TaskTraceUpdate(BaseModel):
    completed_at: datetime | None = None
    duration_ms: int | None = None
    status: str | None = None
    output_summary: str | None = None
    output_sources: dict[str, Any] | None = None
    error_message: str | None = None
    langsmith_run_id: str | None = None


class TaskTraceResponse(BaseModel):
    task_id: str
    span_id: str
    task_title: str
    task_order: int
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    input_query: str | None = None
    input_intent: str | None = None
    output_summary: str | None = None
    output_sources: dict[str, Any] | None = None
    error_message: str | None = None
    langsmith_run_id: str | None = None


class PerformanceSummary(BaseModel):
    total_duration_ms: int | None = None
    avg_task_duration_ms: float | None = None
    max_task_duration_ms: int | None = None
    min_task_duration_ms: int | None = None
    parallel_speedup_ratio: float | None = None


class WorkflowTraceResponse(BaseModel):
    trace_id: str
    workflow_id: str
    scenario_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    langsmith_url: str | None = None
    langsmith_run_id: str | None = None
    tasks: list[TaskTraceResponse] = Field(default_factory=list)
    performance_summary: PerformanceSummary | None = None
