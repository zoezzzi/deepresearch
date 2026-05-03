from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from uuid import UUID
from asyncio import Queue, create_task

from api.models import (
    CreateResearchWithScenarioRequest,
    CreateResearchRequest as ApiCreateResearchRequest,
    ResearchResponse,
    TaskResponse,
    ErrorResponse,
    ScenarioListResponse
)
from api.dependencies import get_scenario_registry, get_sse_manager_dep
from app.scenarios.registry import ScenarioRegistry
from app.config import get_app_settings
from harness.events.manager import SSEConnectionManager, SSEEvent
from harness.logger import logger

# 动态导入场景模型
from app.research_assistant.models.dtos import CreateResearchRequest as ResearchAssistantCreateRequest
from app.dev_survey.models.dtos import CreateResearchRequest as DevSurveyCreateRequest

router = APIRouter(prefix="/research", tags=["research"])

DEFAULT_SCENARIO_ID = "research_assistant_v1"


def get_default_scenario_id() -> str:
    """获取默认场景ID，从配置中读取第一个启用的场景"""
    settings = get_app_settings()
    scenarios = settings.enabled_scenarios_list
    if scenarios:
        return scenarios[0]
    return DEFAULT_SCENARIO_ID  # 兜底默认值


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


def convert_workflow_response_to_api(scenario_response) -> ResearchResponse:
    """将场景的响应对象转换为 API 的响应对象"""
    # 将任务列表转换为 API 格式
    task_responses = []
    if hasattr(scenario_response, 'tasks'):
        for task in scenario_response.tasks:
            status_value = task.status.value if hasattr(task.status, 'value') else str(task.status)
            task_response = TaskResponse(
                task_id=task.task_id,
                title=task.title,
                intent=task.intent,
                query=task.query,
                order=task.order,
                status=status_value,
                summary=task.summary,
                sources_summary=task.sources_summary,
                notices=task.notices,
                created_at=task.created_at,
                updated_at=task.updated_at,
                started_at=task.started_at,
                completed_at=task.completed_at
            )
            task_responses.append(task_response)
    
    # 转换工作流状态
    status_value = scenario_response.status.value if hasattr(scenario_response.status, 'value') else str(scenario_response.status)
    
    return ResearchResponse(
        workflow_id=scenario_response.workflow_id,
        topic=scenario_response.topic,
        scenario_id=scenario_response.scenario_id,
        description=scenario_response.description,
        status=status_value,
        report_url=scenario_response.report_url,
        created_at=scenario_response.created_at,
        updated_at=scenario_response.updated_at,
        started_at=scenario_response.started_at,
        completed_at=scenario_response.completed_at,
        tasks=task_responses
    )


@router.post(
    "",
    response_model=ResearchResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}
)
async def create_research(
    request: ApiCreateResearchRequest,
    scenario_id: str = Query(default_factory=get_default_scenario_id, description="场景标识符，默认为第一个启用的场景"),
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

        # 根据场景转换请求对象
        if scenario_id == "dev_survey":
            scenario_request = DevSurveyCreateRequest(
                topic=request.topic,
                description=request.description,
                scenario_id=scenario_id
            )
        else:
            scenario_request = ResearchAssistantCreateRequest(
                topic=request.topic,
                description=request.description,
                scenario_id=scenario_id
            )

        scenario_response = await executor.create_workflow(scenario_request)
        workflow_uuid = UUID(scenario_response.workflow_id)

        async def run_workflow():
            try:
                await executor.execute_workflow(workflow_uuid)
            except Exception as e:
                logger.error(f"异步执行工作流失败: {e}")
                import traceback
                traceback.print_exc()

        create_task(run_workflow())

        # 转换响应为 API 格式
        return convert_workflow_response_to_api(scenario_response)
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
    scenario_id: str = Query(default_factory=get_default_scenario_id, description="场景标识符"),
    registry: ScenarioRegistry = Depends(get_scenario_registry)
):

    
    try:
        # 先验证 UUID 格式
        try:
            workflow_uuid = UUID(workflow_id)
        except ValueError as uuid_error:
            logger.error(f"[get_workflow_status] UUID 格式错误: {uuid_error}, workflow_id={workflow_id}")
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error_code="INVALID_WORKFLOW_ID_FORMAT",
                    message=f"工作流 ID 格式无效: {workflow_id}"
                ).dict()
            )
        
        executor = registry.get(scenario_id)
        if not executor:
            logger.warning(f"[get_workflow_status] 场景不存在: {scenario_id}")
            raise HTTPException(status_code=404, detail="场景不存在")
        
        scenario_response = await executor.get_workflow_status(workflow_uuid)
        return convert_workflow_response_to_api(scenario_response)
        
    except HTTPException:
        raise
    except ValueError as e:
        # 可能是工作流不存在或其他 ValueError
        logger.error(f"[get_workflow_status] ValueError: {e}, workflow_id={workflow_id}")
        if "Workflow not found" in str(e) or "not found" in str(e).lower():
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error_code="WORKFLOW_NOT_FOUND",
                    message=f"工作流不存在: {workflow_id}"
                ).dict()
            )
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error_code="INTERNAL_ERROR",
                message="获取工作流状态失败",
                details=str(e)
            ).dict()
        )
    except Exception as e:
        logger.exception(f"[get_workflow_status] 异常: {e}")
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
    scenario_id: str = Query(default_factory=get_default_scenario_id, description="场景标识符"),
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
    scenario_id: str = Query(default_factory=get_default_scenario_id, description="场景标识符"),
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
