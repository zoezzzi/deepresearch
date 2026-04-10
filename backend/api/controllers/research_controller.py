
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from uuid import UUID
from asyncio import Queue, create_task

from api.models import (
    CreateResearchRequest,
    ResearchResponse,
    ErrorResponse
)
from api.dependencies import get_research_application_service_dep, get_sse_manager_dep
from application import ResearchApplicationService
from infrastructure.sse.manager import SSEConnectionManager, SSEEvent
from infrastructure.logger import logger

router = APIRouter(prefix="/research", tags=["research"])


@router.post(
    "",
    response_model=ResearchResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}
)
async def create_research(
    request: CreateResearchRequest,
    application_service: ResearchApplicationService = Depends(get_research_application_service_dep)
):
    try:
        logger.info(f"收到创建调研请求: {request.topic}")
        workflow_response = await application_service.create_research_workflow(request)
        workflow_uuid = UUID(workflow_response.workflow_id)

        async def run_workflow():
            try:
                await application_service.execute_research_workflow(workflow_uuid)
            except Exception as e:
                logger.error(f"异步执行工作流失败: {e}")
                import traceback
                traceback.print_exc()

        create_task(run_workflow())

        return workflow_response
    except Exception as e:
        logger.exception(f"创建调研失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error_code="INTERNAL_ERROR",
                message="创建调研失败",
                details=str(e)
            ).dict()
        )


@router.get(
    "/{workflow_id}",
    response_model=ResearchResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}
)
async def get_workflow_status(
    workflow_id: str,
    application_service: ResearchApplicationService = Depends(get_research_application_service_dep)
):
    try:
        logger.info(f"获取工作流状态: {workflow_id}")
        workflow_uuid = UUID(workflow_id)
        response = await application_service.get_workflow_status(workflow_uuid)
        return response
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error_code="INVALID_WORKFLOW_ID",
                message="无效的工作流 ID"
            ).dict()
        )
    except Exception as e:
        logger.exception(f"获取工作流状态失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error_code="INTERNAL_ERROR",
                message="获取工作流状态失败",
                details=str(e)
            ).dict()
        )


@router.get("/{workflow_id}/stream")
async def stream_workflow_events(
    workflow_id: str,
    sse_manager: SSEConnectionManager = Depends(get_sse_manager_dep)
):
    async def event_generator():
        queue: Queue[SSEEvent] = Queue()
        await sse_manager.connect(workflow_id, queue)
        try:
            while True:
                event = await queue.get()
                yield event.to_sse_format()
        finally:
            await sse_manager.disconnect(workflow_id, queue)
    
    try:
        logger.info(f"客户端连接 SSE 流: {workflow_id}")
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    except Exception as e:
        logger.exception(f"SSE 连接失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error_code="INTERNAL_ERROR",
                message="SSE 连接失败",
                details=str(e)
            ).dict()
        )


@router.get("/reports/{report_id}")
async def download_report(
    report_id: str,
    application_service: ResearchApplicationService = Depends(get_research_application_service_dep)
):
    try:
        logger.info(f"Downloading report: {report_id}")
        
        file_path = application_service.get_report_file_path(report_id)
        
        if file_path is None:
            raise HTTPException(status_code=404, detail="Report not found")
        
        return FileResponse(
            path=file_path,
            filename=report_id,
            media_type="text/markdown",
            headers={"Cache-Control": "max-age=3600"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading report: {e}")
        raise HTTPException(status_code=500, detail="Failed to download report")

