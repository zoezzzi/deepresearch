"""
调研助手工作流状态定义

定义 LangGraph 工作流的状态结构
"""

from datetime import datetime
from typing import Any, TypedDict


# total=False：节点只返回增量字段，未返回的键沿用上一次 checkpoint 中的值
class WorkflowState(TypedDict, total=False):
    """
    调研工作流状态

    用于在 LangGraph 工作流节点之间传递状态

    设计原则：Checkpoint 是唯一提交点，所有节点间数据通过 state 传递。
    task_results 和 quality_report 从 Store 迁移至 Checkpoint：
    - task_results：执行节点产出的原始结果（含 summary, sources_summary）
    - quality_report：报告生成节点产出的质量评估，供 reflect 节点消费
    """

    workflow_id: str
    topic: str
    scenario_id: str | None
    tasks: list[dict[str, Any]]
    task_results: list[dict[str, Any]]  # 原始执行结果（原 Store）
    quality_report: dict[str, Any] | None  # 质量评估报告（原 Store）
    report_content: str | None
    report_url: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime
    workflow_status: str | None
    task_summary: dict[str, int] | None
    sub_questions: list[str] | None
    reflection_round: int
