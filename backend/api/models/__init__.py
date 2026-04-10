from pydantic import BaseModel, Field
from typing import Optional
from application.dtos.create_research_request import CreateResearchRequest
from application.dtos.research_responses import (
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
