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


class ScenarioMetadata(BaseModel):
    scenario_id: str = Field(..., description="场景唯一标识符")
    name: str = Field(..., description="场景名称")
    description: str = Field(..., description="场景描述")
    version: str = Field(..., description="场景版本")
    author: Optional[str] = Field(None, description="场景作者")


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
