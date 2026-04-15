from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from domain.value_objects.workflow_status import WorkflowStatus


class TaskResponse(BaseModel):
    task_id: str = Field(..., description="任务ID")
    title: str = Field(..., description="任务标题")
    intent: str = Field(..., description="任务意图")
    query: str = Field(..., description="搜索查询")
    order: int = Field(..., description="任务顺序")
    status: str = Field(..., description="任务状态")
    summary: Optional[str] = Field(None, description="任务摘要")
    sources_summary: Optional[str] = Field(None, description="来源摘要")
    notices: Optional[str] = Field(None, description="注意事项")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")


class WorkflowResponse(BaseModel):
    workflow_id: str = Field(..., description="工作流ID")
    topic: str = Field(..., description="调研主题")
    description: Optional[str] = Field(None, description="调研描述")
    status: WorkflowStatus = Field(..., description="工作流状态 (all_success/partial_failed/all_failed/report_failed)")
    report_url: Optional[str] = Field(None, description="报告URL")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    tasks: List[TaskResponse] = Field(default_factory=list, description="任务列表")


class ResearchResponse(WorkflowResponse):
    pass
