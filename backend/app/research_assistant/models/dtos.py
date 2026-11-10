from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.research_assistant.models.enums import WorkflowStatus


class CreateResearchRequest(BaseModel):
    topic: str = Field(..., min_length=1, description="调研主题")
    description: str | None = Field(None, description="调研描述")
    scenario_id: str | None = Field(None, description="场景标识符")

    @field_validator("topic", mode="before")
    @classmethod
    def validate_topic(cls, v):
        if v is None or (isinstance(v, str) and v.strip() == ""):
            raise ValueError("Topic cannot be empty")
        return v.strip() if isinstance(v, str) else v


class TaskResponse(BaseModel):
    task_id: str = Field(..., description="任务ID")
    title: str = Field(..., description="任务标题")
    intent: str = Field(..., description="任务意图")
    query: str = Field(..., description="搜索查询")
    order: int = Field(..., description="任务顺序")
    status: str = Field(..., description="任务状态")
    summary: str | None = Field(None, description="任务摘要")
    sources_summary: str | None = Field(None, description="来源摘要")
    notices: str | None = Field(None, description="注意事项")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    started_at: datetime | None = Field(None, description="开始时间")
    completed_at: datetime | None = Field(None, description="完成时间")


class WorkflowResponse(BaseModel):
    workflow_id: str = Field(..., description="工作流ID")
    topic: str = Field(..., description="调研主题")
    scenario_id: str = Field(..., description="场景标识符")
    description: str | None = Field(None, description="调研描述")
    status: WorkflowStatus = Field(..., description="工作流状态")
    report_url: str | None = Field(None, description="报告URL")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    started_at: datetime | None = Field(None, description="开始时间")
    completed_at: datetime | None = Field(None, description="完成时间")
    tasks: list[TaskResponse] = Field(default_factory=list, description="任务列表")


class ResearchResponse(WorkflowResponse):
    pass
