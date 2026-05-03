from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from harness.observability.trace_service import get_trace_service
from harness.logger import logger

router = APIRouter(prefix="/research", tags=["trace"])


@router.get("/{workflow_id}/trace")
async def get_workflow_trace(workflow_id: str):
    try:
        trace_service = get_trace_service()
        trace = await trace_service.repository.get_trace_by_workflow_id(workflow_id)

        if not trace:
            raise HTTPException(
                status_code=404,
                detail=f"Trace not found for workflow: {workflow_id}"
            )

        return JSONResponse(content=trace.model_dump(mode="json"))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取工作流追踪信息失败: workflow_id={workflow_id}, error={e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取工作流追踪信息失败: {str(e)}"
        )
