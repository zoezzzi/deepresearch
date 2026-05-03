from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


class CreateResearchRequest(BaseModel):
    topic: str = Field(..., min_length=1, description="调研主题")
    description: Optional[str] = Field(None, description="调研描述")
    scenario_id: Optional[str] = Field(None, description="场景标识符")

    @field_validator('topic', mode='before')
    @classmethod
    def validate_topic(cls, v):
        if v is None or (isinstance(v, str) and v.strip() == ''):
            raise ValueError('Topic cannot be empty')
        return v.strip() if isinstance(v, str) else v


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
    scenario_id: str = Field(..., description="场景标识符")
    description: Optional[str] = Field(None, description="调研描述")
    status: str = Field(..., description="工作流状态")
    report_url: Optional[str] = Field(None, description="报告URL")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    tasks: List[TaskResponse] = Field(default_factory=list, description="任务列表")


class ResearchResponse(WorkflowResponse):
    pass


class ErrorResponse(BaseModel):
    error_code: str = Field(..., description="错误代码")
    message: str = Field(..., description="错误消息")
    details: Optional[str] = Field(None, description="错误详情")


class ScenarioUIConfig(BaseModel):
    navbar_title: Optional[str] = Field(None, description="导航栏标题")
    form_title: Optional[str] = Field(None, description="表单标题")
    topic_label: Optional[str] = Field(None, description="主题标签")
    topic_placeholder: Optional[str] = Field(None, description="主题输入占位符")


class ScenarioMetadata(BaseModel):
    scenario_id: str = Field(..., description="场景唯一标识符")
    name: str = Field(..., description="场景名称")
    description: str = Field(..., description="场景描述")
    version: str = Field(..., description="场景版本")
    author: Optional[str] = Field(None, description="场景作者")
    ui_config: Optional[ScenarioUIConfig] = Field(None, description="UI 配置")


class ScenarioListResponse(BaseModel):
    scenarios: List[ScenarioMetadata] = Field(..., description="场景列表")


class CreateResearchWithScenarioRequest(CreateResearchRequest):
    scenario_id: str = Field(..., description="场景标识符")


__all__ = [
    "CreateResearchRequest",
    "CreateResearchWithScenarioRequest",
    "WorkflowResponse",
    "TaskResponse",
    "ResearchResponse",
    "ErrorResponse",
    "ScenarioMetadata",
    "ScenarioListResponse"
]
