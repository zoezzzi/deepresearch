from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from uuid import UUID
from asyncio import Queue, create_task

from api.models import (
    CreateResearchWithScenarioRequest,
    CreateResearchRequest,
    ResearchResponse,
    ErrorResponse,
    ScenarioListResponse
)
from api.dependencies import get_scenario_registry, get_sse_manager_dep
from app.scenarios.registry import ScenarioRegistry
from harness.events.manager import SSEConnectionManager, SSEEvent
from harness.logger import logger

router = APIRouter(prefix="/research", tags=["research"])
DEFAULT_SCENARIO_ID = "research_assistant_v1"


@router.get(
    "/scenarios",
    response_model=ScenarioListResponse,
    responses={500: {"model": ErrorResponse}}
)
async def list_scenarios(
    registry: ScenarioRegistry = Depends(get_scenario_registry)
):
    try:
        scenarios = registry.list_all()
        return {"scenarios": scenarios}
    except Exception as e:
        logger.exception(f"获取场景列表失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error_code="INTERNAL_ERROR",
                message="获取场景列表失败",
                details=str(e)
            ).dict()
        )


@router.post(
    "",
    response_model=ResearchResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}
)
async def create_research(
    request: CreateResearchRequest,
    scenario_id: str = Query(DEFAULT_SCENARIO_ID, description="场景标识符，默认为研究助手"),
    registry: ScenarioRegistry = Depends(get_scenario_registry),
    sse_manager: SSEConnectionManager = Depends(get_sse_manager_dep)
):
    try:
        logger.info(f"收到创建调研请求: scenario_id={scenario_id}, topic={request.topic}")
        
        executor = registry.get(scenario_id)
        if not executor:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error_code="SCENARIO_NOT_FOUND",
                    message=f"场景 {scenario_id} 不存在"
                ).dict()
            )
        
        request.scenario_id = scenario_id
        workflow_response = await executor.create_workflow(request)
        workflow_uuid = UUID(workflow_response.workflow_id)

        async def run_workflow():
            try:
                await executor.execute_workflow(workflow_uuid)
            except Exception as e:
                logger.error(f"异步执行工作流失败: {e}")
                import traceback
                traceback.print_exc()

        create_task(run_workflow())

        return workflow_response
    except HTTPException:
        raise
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
    scenario_id: str = Query(DEFAULT_SCENARIO_ID, description="场景标识符"),
    registry: ScenarioRegistry = Depends(get_scenario_registry)
):
    try:
        logger.info(f"获取工作流状态: workflow_id={workflow_id}, scenario_id={scenario_id}")
        
        executor = registry.get(scenario_id)
        if not executor:
            raise HTTPException(status_code=404, detail="场景不存在")
        
        workflow_uuid = UUID(workflow_id)
        response = await executor.get_workflow_status(workflow_uuid)
        return response
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error_code="INVALID_WORKFLOW_ID",
                message="无效的工作流 ID"
            ).dict()
        )
    except HTTPException:
        raise
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
    scenario_id: str = Query(DEFAULT_SCENARIO_ID, description="场景标识符"),
    registry: ScenarioRegistry = Depends(get_scenario_registry)
):
    try:
        logger.info(f"Downloading report: {report_id}")
        
        executor = registry.get(scenario_id)
        if not executor:
            raise HTTPException(status_code=404, detail="场景不存在")
        
        file_path = executor.get_report_file_path(report_id)
        
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


@router.get("/{workflow_id}/report-content")
async def get_report_content(
    workflow_id: str,
    scenario_id: str = Query(DEFAULT_SCENARIO_ID, description="场景标识符"),
    registry: ScenarioRegistry = Depends(get_scenario_registry)
):
    try:
        logger.info(f"获取报告内容: workflow_id={workflow_id}, scenario_id={scenario_id}")
        
        executor = registry.get(scenario_id)
        if not executor:
            raise HTTPException(status_code=404, detail="场景不存在")
        
        workflow_uuid = UUID(workflow_id)
        
        content = await executor.get_report_content(workflow_uuid)
        
        if content is None:
            raise HTTPException(status_code=404, detail="Report not found")
        
        return {"content": content}
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error_code="INVALID_WORKFLOW_ID",
                message="无效的工作流 ID"
            ).dict()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取报告内容失败: {e}")
        raise HTTPException(status_code=500, detail="Failed to get report content")
