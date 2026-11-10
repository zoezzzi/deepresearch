"""
调研助手工作流状态定义

定义 LangGraph 工作流的状态结构
"""

from datetime import datetime
from typing import Any, TypedDict


class WorkflowState(TypedDict, total=False):
    """State passed between LangGraph nodes of the research workflow.

    ``total=False`` because nodes return only the fields they update; keys they
    omit keep the values from the previous checkpoint.
    """

    workflow_id: str
    topic: str
    description: str | None
    scenario_id: str | None
    tasks: list[dict[str, Any]]
    current_task_index: int
    task_results: list[dict[str, Any]]
    report_content: str | None
    report_url: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime
    workflow_status: str | None
    task_summary: dict[str, int] | None
    retrieved_chunks: list[str] | None
    sub_questions: list[str] | None
    citations: list[str] | None
