from pydantic import BaseModel, Field, validator
from typing import Optional
from core.models import (
    CreateResearchRequest,
    WorkflowResponse,
    TaskResponse,
    ResearchResponse
)


class ErrorResponse(BaseModel):
    error_code: str = Field(..., description="错误代码")
    message: str = Field(..., description="错误消息")
    details: Optional[str] = Field(None, description="错误详情")


__all__ = [
    "CreateResearchRequest",
    "WorkflowResponse",
    "TaskResponse",
    "ResearchResponse",
    "ErrorResponse"
]
