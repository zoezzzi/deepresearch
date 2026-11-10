"""Trace query API: return the full execution trace of a workflow by id."""

from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from api.models import ErrorResponse
from harness.logger import logger
from harness.observability.trace_service import get_trace_service

router = APIRouter(prefix="/research", tags=["trace"])


def _error(status_code: int, error_code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=ErrorResponse(error_code=error_code, message=message).model_dump(),
    )


@router.get("/{workflow_id}/trace")
async def get_workflow_trace(workflow_id: str):
    """Fetch the persisted trace tree for a workflow.

    Returns 404 when the workflow has never been traced, which is a normal case
    for workflows that failed before the trace was created.
    """
    try:
        UUID(str(workflow_id))
    except (ValueError, AttributeError, TypeError):
        logger.warning(f"[TraceAPI] 非法的 workflow_id: {workflow_id}")
        raise _error(400, "INVALID_WORKFLOW_ID", "工作流 ID 格式无效")

    try:
        trace_service = get_trace_service()
        trace = await trace_service.repository.get_trace_by_workflow_id(workflow_id)

        if not trace:
            raise _error(404, "TRACE_NOT_FOUND", "该工作流暂无追踪记录")

        return JSONResponse(content=trace.model_dump(mode="json"))
    except HTTPException:
        raise
    except Exception as e:
        # 不把内部异常文本回传给客户端，仅记录日志
        logger.exception(f"获取工作流追踪信息失败: workflow_id={workflow_id}, error={e}")
        raise _error(500, "INTERNAL_ERROR", "获取工作流追踪信息失败")
