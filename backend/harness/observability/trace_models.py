"""
Trace 数据模型定义

定义追踪链路相关的 Pydantic 模型
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class WorkflowTraceCreate(BaseModel):
    trace_id: str
    workflow_id: str
    request_id: Optional[str] = None
    scenario_id: str
    started_at: datetime
    status: str = "running"
    langsmith_run_id: Optional[str] = None


class WorkflowTraceUpdate(BaseModel):
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    status: Optional[str] = None
    langsmith_run_id: Optional[str] = None
    langsmith_url: Optional[str] = None
    execute_duration_ms: Optional[int] = None


class TaskTraceCreate(BaseModel):
    trace_id: str
    workflow_id: str
    task_id: str
    span_id: str
    task_title: str
    task_order: int
    started_at: datetime
    status: str = "running"
    input_query: Optional[str] = None
    input_intent: Optional[str] = None
    langsmith_run_id: Optional[str] = None
    retry_count: int = 0


class TaskTraceUpdate(BaseModel):
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    status: Optional[str] = None
    output_summary: Optional[str] = None
    output_sources: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    langsmith_run_id: Optional[str] = None


class TaskTraceResponse(BaseModel):
    task_id: str
    span_id: str
    task_title: str
    task_order: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    input_query: Optional[str] = None
    input_intent: Optional[str] = None
    output_summary: Optional[str] = None
    output_sources: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    langsmith_run_id: Optional[str] = None


class PerformanceSummary(BaseModel):
    total_duration_ms: Optional[int] = None
    avg_task_duration_ms: Optional[float] = None
    max_task_duration_ms: Optional[int] = None
    min_task_duration_ms: Optional[int] = None
    parallel_speedup_ratio: Optional[float] = None


class WorkflowTraceResponse(BaseModel):
    trace_id: str
    workflow_id: str
    scenario_id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    langsmith_url: Optional[str] = None
    langsmith_run_id: Optional[str] = None
    tasks: List[TaskTraceResponse] = Field(default_factory=list)
    performance_summary: Optional[PerformanceSummary] = None
