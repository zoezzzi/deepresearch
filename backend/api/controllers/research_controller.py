"""Research HTTP API: scenario listing, workflow creation/query, SSE stream, report download.

Error contract: every failure branch raises an HTTPException carrying an
``ErrorResponse``, which the global handlers in ``api.errors`` render as
``{error_code, message, details}``.
"""

import asyncio
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse

from api.dependencies import get_scenario_registry, get_sse_manager_dep
from api.models import CreateResearchRequest as ApiCreateResearchRequest
from api.models import (
    ErrorResponse,
    ResearchResponse,
    ScenarioListResponse,
    TaskResponse,
)
from app.config import get_app_settings
from app.dev_survey.models.dtos import CreateResearchRequest as DevSurveyCreateRequest

# 动态导入场景模型
from app.research_assistant.models.dtos import (
    CreateResearchRequest as ResearchAssistantCreateRequest,
)
from app.scenarios.registry import ScenarioRegistry
from harness.events.manager import SSEConnectionManager, SSEEvent
from harness.logger import logger

router = APIRouter(prefix="/research", tags=["research"])

DEFAULT_SCENARIO_ID = "research_assistant_v1"

# 后台任务必须持有引用，否则可能被 GC 回收导致工作流中断
_BACKGROUND_TASKS: set = set()

# 报告文件名允许的最大长度，避免异常长的路径参数
_MAX_REPORT_ID_LENGTH = 128

_SCENARIO_NOT_FOUND_MESSAGE = "场景不存在"
_INTERNAL_ERROR_MESSAGE = "服务器内部错误，请稍后重试"


def get_default_scenario_id() -> str:
    """Return the first enabled scenario id from the app configuration."""
    settings = get_app_settings()
    scenarios = settings.enabled_scenarios_list
    if scenarios:
        return scenarios[0]
    return DEFAULT_SCENARIO_ID  # 兜底默认值


def _error(
    status_code: int,
    error_code: str,
    message: str,
    details: str | None = None,
) -> HTTPException:
    """Build a uniform error response; callers use it as ``raise _error(...)``."""
    return HTTPException(
        status_code=status_code,
        detail=ErrorResponse(error_code=error_code, message=message, details=details).model_dump(),
    )


def _parse_workflow_uuid(workflow_id: str) -> UUID:
    """Parse a path segment into a UUID, mapping malformed input to 400 (not 500)."""
    try:
        return UUID(str(workflow_id))
    except (ValueError, AttributeError, TypeError):
        logger.warning(f"[ResearchAPI] 非法的 workflow_id: {workflow_id}")
        raise _error(
            400,
            "INVALID_WORKFLOW_ID",
            "工作流 ID 格式无效",
            f"收到: {workflow_id}",
        )


def _validate_report_id(report_id: str) -> str:
    """Validate a report file name, rejecting separators and traversal segments."""
    if (
        not report_id
        or len(report_id) > _MAX_REPORT_ID_LENGTH
        or "/" in report_id
        or "\\" in report_id
        or ".." in report_id
        or report_id.strip() != report_id
    ):
        logger.warning(f"[ResearchAPI] 非法的 report_id: {report_id!r}")
        raise _error(400, "INVALID_REPORT_ID", "报告 ID 无效")
    return report_id


def _enum_value(value) -> str:
    """Normalize scenario-layer enum values to plain strings for the API schema."""
    return value.value if hasattr(value, "value") else str(value)


def convert_workflow_response_to_api(scenario_response) -> ResearchResponse:
    """Convert a scenario response object into the API response schema.

    Scenarios are plugin-provided, so missing fields are a contract violation:
    return 502 here instead of letting a Pydantic validation error surface as 500.
    """
    if scenario_response is None:
        raise _error(502, "INVALID_SCENARIO_RESPONSE", "场景未返回工作流数据")

    required_fields = ("workflow_id", "topic", "scenario_id", "status", "created_at", "updated_at")
    missing_fields = [
        name for name in required_fields if getattr(scenario_response, name, None) is None
    ]
    if missing_fields:
        logger.error(f"[ResearchAPI] 场景响应缺少字段: {missing_fields}")
        raise _error(
            502,
            "INVALID_SCENARIO_RESPONSE",
            "场景返回的数据不完整",
            "缺少字段: " + ", ".join(missing_fields),
        )

    task_responses = []
    for task in getattr(scenario_response, "tasks", None) or []:
        if getattr(task, "task_id", None) is None:
            # 单个任务缺少 ID 时跳过，避免整份快照不可用
            logger.warning("[ResearchAPI] 跳过缺少 task_id 的任务")
            continue
        try:
            task_responses.append(
                TaskResponse(
                    task_id=str(task.task_id),
                    title=getattr(task, "title", ""),
                    intent=getattr(task, "intent", ""),
                    query=getattr(task, "query", ""),
                    order=getattr(task, "order", 0) or 0,
                    status=_enum_value(getattr(task, "status", "pending")),
                    summary=getattr(task, "summary", None),
                    sources_summary=getattr(task, "sources_summary", None),
                    notices=getattr(task, "notices", None),
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                    started_at=getattr(task, "started_at", None),
                    completed_at=getattr(task, "completed_at", None),
                )
            )
        except Exception as e:
            logger.error(f"[ResearchAPI] 任务数据转换失败: task_id={task.task_id}, {e}")
            raise _error(
                502,
                "INVALID_SCENARIO_RESPONSE",
                "场景返回的任务数据无效",
                f"task_id={task.task_id}",
            )

    return ResearchResponse(
        workflow_id=str(scenario_response.workflow_id),
        topic=scenario_response.topic,
        scenario_id=scenario_response.scenario_id,
        description=getattr(scenario_response, "description", None),
        status=_enum_value(scenario_response.status),
        report_url=getattr(scenario_response, "report_url", None),
        created_at=scenario_response.created_at,
        updated_at=scenario_response.updated_at,
        started_at=getattr(scenario_response, "started_at", None),
        completed_at=getattr(scenario_response, "completed_at", None),
        tasks=task_responses,
    )


def _discard_background_task(task) -> None:
    """Done-callback: release the strong reference and log unhandled exceptions."""
    _BACKGROUND_TASKS.discard(task)
    if task.cancelled():
        logger.warning("[ResearchAPI] 后台工作流任务被取消")
        return
    error = task.exception()
    if error is not None:
        logger.error(f"[ResearchAPI] 后台工作流任务异常退出: {error}")


def _track_background_task(task) -> None:
    """Keep a strong reference so the event loop cannot garbage-collect the task."""
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_discard_background_task)


@router.get(
    "/scenarios", response_model=ScenarioListResponse, responses={500: {"model": ErrorResponse}}
)
async def list_scenarios(registry: ScenarioRegistry = Depends(get_scenario_registry)):
    """Return metadata of all registered scenarios for the frontend selector."""
    try:
        scenarios = registry.list_all()
        return {"scenarios": scenarios}
    except Exception as e:
        logger.exception(f"获取场景列表失败: {e}")
        raise _error(500, "INTERNAL_ERROR", "获取场景列表失败")


@router.post(
    "",
    response_model=ResearchResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def create_research(
    request: ApiCreateResearchRequest,
    scenario_id: str = Query(
        default_factory=get_default_scenario_id, description="场景标识符，默认为第一个启用的场景"
    ),
    registry: ScenarioRegistry = Depends(get_scenario_registry),
    sse_manager: SSEConnectionManager = Depends(get_sse_manager_dep),
):
    """Create a workflow for the requested scenario and start it in the background.

    Returns immediately with the initial workflow snapshot; clients follow progress
    through the SSE stream or the status endpoint.
    """
    try:
        logger.info(f"收到创建调研请求: scenario_id={scenario_id}, topic={request.topic}")

        executor = registry.get(scenario_id)
        if not executor:
            logger.warning(f"[create_research] 场景不存在: {scenario_id}")
            raise _error(404, "SCENARIO_NOT_FOUND", f"场景 {scenario_id} 不存在")

        # 根据场景转换请求对象
        if scenario_id == "dev_survey":
            scenario_request = DevSurveyCreateRequest(
                topic=request.topic, description=request.description, scenario_id=scenario_id
            )
        else:
            scenario_request = ResearchAssistantCreateRequest(
                topic=request.topic, description=request.description, scenario_id=scenario_id
            )

        scenario_response = await executor.create_workflow(scenario_request)
        if scenario_response is None:
            raise _error(502, "INVALID_SCENARIO_RESPONSE", "场景未返回工作流数据")

        try:
            workflow_uuid = UUID(str(scenario_response.workflow_id))
        except (ValueError, AttributeError, TypeError):
            logger.error(
                f"[ResearchAPI] 场景返回的 workflow_id 非法: {scenario_response.workflow_id}"
            )
            raise _error(502, "INVALID_SCENARIO_RESPONSE", "场景返回的工作流 ID 无效")

        workflow_id_str = str(workflow_uuid)

        async def run_workflow():
            try:
                await executor.execute_workflow(workflow_uuid)
            except asyncio.CancelledError:
                logger.warning(f"[ResearchAPI] 工作流执行被取消: {workflow_id_str}")
                raise
            except Exception as e:
                logger.exception(f"[ResearchAPI] 异步执行工作流失败: {workflow_id_str}, {e}")
                # 后台失败没有 HTTP 响应可返回，补发一条 error 事件让前端结束等待
                try:
                    await sse_manager.send_event(
                        workflow_id=workflow_id_str,
                        event_type="error",
                        data={
                            "workflow_id": workflow_id_str,
                            "message": "工作流执行失败，请稍后重试",
                        },
                    )
                except Exception:
                    logger.exception(f"[ResearchAPI] 发送工作流错误事件失败: {workflow_id_str}")

        # 后台执行，不阻塞 HTTP 响应；任务引用由模块级集合持有
        _track_background_task(asyncio.create_task(run_workflow()))

        # 转换响应为 API 格式
        return convert_workflow_response_to_api(scenario_response)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"创建调研失败: {e}")
        raise _error(500, "INTERNAL_ERROR", "创建调研失败")


@router.get(
    "/{workflow_id}",
    response_model=ResearchResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def get_workflow_status(
    workflow_id: str,
    scenario_id: str = Query(default_factory=get_default_scenario_id, description="场景标识符"),
    registry: ScenarioRegistry = Depends(get_scenario_registry),
):
    """Return the latest workflow snapshot for the given scenario."""
    # 先验证 UUID 格式，避免把非法输入当成存储层异常
    workflow_uuid = _parse_workflow_uuid(workflow_id)

    try:
        executor = registry.get(scenario_id)
        if not executor:
            logger.warning(f"[get_workflow_status] 场景不存在: {scenario_id}")
            raise _error(404, "SCENARIO_NOT_FOUND", f"场景 {scenario_id} 不存在")

        scenario_response = await executor.get_workflow_status(workflow_uuid)
        return convert_workflow_response_to_api(scenario_response)

    except HTTPException:
        raise
    except ValueError as e:
        # 场景层未找到工作流时通常抛 ValueError，统一转换为 404
        logger.warning(f"[get_workflow_status] ValueError: {e}, workflow_id={workflow_id}")
        if "not found" in str(e).lower() or "不存在" in str(e):
            raise _error(404, "WORKFLOW_NOT_FOUND", "工作流不存在或已被删除")
        raise _error(500, "INTERNAL_ERROR", "获取工作流状态失败")
    except Exception as e:
        logger.exception(f"[get_workflow_status] 异常: {e}")
        raise _error(500, "INTERNAL_ERROR", "获取工作流状态失败")


@router.get("/{workflow_id}/stream")
async def stream_workflow_events(
    workflow_id: str, sse_manager: SSEConnectionManager = Depends(get_sse_manager_dep)
):
    """Stream workflow events as Server-Sent Events.

    Each subscriber owns a dedicated queue with a bounded size; slow clients
    drop their oldest events instead of growing memory without limit.
    """
    stream_key = str(_parse_workflow_uuid(workflow_id))

    async def event_generator():
        queue: asyncio.Queue[SSEEvent] = asyncio.Queue(maxsize=1000)
        await sse_manager.connect(stream_key, queue)
        try:
            # 首帧注释用于尽快建立连接，同时避免代理缓冲
            yield ": connected\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:  # noqa: UP041 保持原代码不变，仅注释任务范围内不改动
                    # 空闲超过 15 秒发送心跳，防止中间代理断开长连接
                    yield ": ping\n\n"
                    continue
                yield event.to_sse_format()
        except asyncio.CancelledError:
            # 客户端主动断开，属于正常生命周期
            logger.info(f"[ResearchAPI] SSE 客户端断开: {stream_key}")
            raise
        except Exception as e:
            logger.exception(f"[ResearchAPI] SSE 推送异常: {stream_key}, {e}")
            try:
                yield SSEEvent(
                    event_type="error",
                    data={"workflow_id": stream_key, "message": "实时连接异常，请刷新页面重试"},
                    workflow_id=stream_key,
                ).to_sse_format()
            except Exception:
                logger.error(f"[ResearchAPI] 发送 SSE 异常事件失败: {stream_key}")
        finally:
            await sse_manager.disconnect(stream_key, queue)

    logger.info(f"客户端连接 SSE 流: {stream_key}")
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/reports/{report_id}")
async def download_report(
    report_id: str,
    scenario_id: str = Query(default_factory=get_default_scenario_id, description="场景标识符"),
    registry: ScenarioRegistry = Depends(get_scenario_registry),
):
    """Download a generated report file by its report id."""
    safe_report_id = _validate_report_id(report_id)

    try:
        logger.info(f"Downloading report: {safe_report_id}")

        executor = registry.get(scenario_id)
        if not executor:
            raise _error(404, "SCENARIO_NOT_FOUND", f"场景 {scenario_id} 不存在")

        file_path = executor.get_report_file_path(safe_report_id)

        if file_path is None:
            raise _error(404, "REPORT_NOT_FOUND", "报告不存在或尚未生成")

        resolved_path = Path(file_path)
        if not resolved_path.is_file():
            logger.warning(f"[ResearchAPI] 报告文件不存在: {resolved_path}")
            raise _error(404, "REPORT_NOT_FOUND", "报告不存在或尚未生成")

        return FileResponse(
            path=resolved_path,
            filename=safe_report_id,
            media_type="text/markdown",
            headers={"Cache-Control": "max-age=3600"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error downloading report: {e}")
        raise _error(500, "INTERNAL_ERROR", "报告下载失败")


@router.get("/{workflow_id}/report-content")
async def get_report_content(
    workflow_id: str,
    scenario_id: str = Query(default_factory=get_default_scenario_id, description="场景标识符"),
    registry: ScenarioRegistry = Depends(get_scenario_registry),
):
    """Return the markdown body of the workflow's report, if it exists."""
    workflow_uuid = _parse_workflow_uuid(workflow_id)

    try:
        logger.info(f"获取报告内容: workflow_id={workflow_id}, scenario_id={scenario_id}")

        executor = registry.get(scenario_id)
        if not executor:
            raise _error(404, "SCENARIO_NOT_FOUND", f"场景 {scenario_id} 不存在")

        content = await executor.get_report_content(workflow_uuid)

        if content is None:
            raise _error(404, "REPORT_NOT_FOUND", "报告尚未生成")

        return {"content": content}
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"[get_report_content] ValueError: {e}, workflow_id={workflow_id}")
        raise _error(400, "INVALID_WORKFLOW_ID", "无效的工作流 ID")
    except Exception as e:
        logger.exception(f"获取报告内容失败: {e}")
        raise _error(500, "INTERNAL_ERROR", "获取报告内容失败")
