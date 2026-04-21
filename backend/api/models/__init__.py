from pydantic import BaseModel, Field, validator
from typing import Optional, List
from app.research_assistant.models import (
    CreateResearchRequest,
    WorkflowResponse,
    TaskResponse,
    ResearchResponse
)


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
