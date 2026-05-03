"""
调研助手工作流状态定义

定义 LangGraph 工作流的状态结构
"""
from typing import TypedDict, List, Optional, Any, Dict
from datetime import datetime


class WorkflowState(TypedDict, total=False):
    """
    调研工作流状态

    用于在 LangGraph 工作流节点之间传递状态

    精简原则：仅保留路由必需字段，大字段迁移至 Store
    """
    workflow_id: str
    topic: str
    scenario_id: Optional[str]
    tasks: List[Dict[str, Any]]
    report_content: Optional[str]
    report_url: Optional[str]
    error: Optional[str]
    created_at: datetime
    updated_at: datetime
    workflow_status: Optional[str]
    task_summary: Optional[Dict[str, int]]
    sub_questions: Optional[List[str]]
    reflection_round: int
