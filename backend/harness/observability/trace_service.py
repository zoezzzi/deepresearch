"""
Trace 服务

提供追踪业务的统一服务接口，支持异步写入、容错处理
"""

from datetime import UTC, datetime
from typing import Any

from harness.logger import logger
from harness.observability.trace_context import (
    generate_span_id,
    generate_trace_id,
    get_current_langsmith_run_id,
    set_current_langsmith_run_id,
    set_trace_context,
)
from harness.observability.trace_models import (
    TaskTraceCreate,
    TaskTraceUpdate,
    WorkflowTraceCreate,
    WorkflowTraceUpdate,
)
from harness.observability.trace_repository import TraceRepository


def _calculate_duration_ms(started_at: datetime, completed_at: datetime) -> int:
    """计算持续时间（毫秒）"""
    delta = completed_at - started_at
    return int(delta.total_seconds() * 1000)


class TraceService:
    """Persist workflow/task execution traces for later inspection.

    Trace records are written through a ``TraceRepository`` abstraction so the
    harness layer stays independent from the database implementation. Failures
    in tracing are propagated to callers; no silent swallowing happens here.
    """

    def __init__(self, repository: TraceRepository):
        self.repository = repository

    async def start_workflow_trace(
        self,
        workflow_id: str,
        scenario_id: str,
        trace_id: str | None = None,
        request_id: str | None = None,
        topic: str | None = None,
        description: str | None = None,
    ) -> str:
        """Create the root trace for a workflow and bind it to the current context.

        Returns the effective trace id (generated when not supplied).
        """
        if not trace_id:
            trace_id = generate_trace_id()

        set_trace_context(trace_id=trace_id, workflow_id=workflow_id)

        # 获取当前 LangSmith 运行 ID，如果没有就用一个默认值
        langsmith_run_id = get_current_langsmith_run_id()
        if not langsmith_run_id:
            # 如果没有 LangSmith 运行 ID，就用 trace_id 作为替代
            langsmith_run_id = trace_id
            set_current_langsmith_run_id(langsmith_run_id)
            logger.info(
                f"[TraceService] Using trace_id as default langsmith_run_id: {langsmith_run_id}"
            )

        trace = WorkflowTraceCreate(
            trace_id=trace_id,
            workflow_id=workflow_id,
            request_id=request_id,
            scenario_id=scenario_id,
            started_at=datetime.now(UTC),
            status="running",
            langsmith_run_id=langsmith_run_id,
        )

        await self.repository.create_workflow_trace(trace)

        logger.info(
            f"[TraceService] Started workflow trace: {trace_id} for workflow: {workflow_id}"
        )
        return trace_id

    async def complete_workflow_trace(
        self,
        workflow_id: str,
        status: str,
        langsmith_url: str | None = None,
        report_url: str | None = None,
        execute_duration_ms: int | None = None,
    ) -> None:
        """Mark the workflow trace as finished with the given status.

        ``duration_ms`` is left to the repository so it can compute it from the
        stored ``started_at`` in the database's own clock.
        """
        now = datetime.now(UTC)

        # 获取当前 LangSmith 运行 ID（可能在执行过程中更新）
        langsmith_run_id = get_current_langsmith_run_id()

        update = WorkflowTraceUpdate(
            completed_at=now,
            duration_ms=None,  # 让 repository 自动计算
            status=status,
            langsmith_url=langsmith_url,
            langsmith_run_id=langsmith_run_id,
            execute_duration_ms=execute_duration_ms,
        )

        await self.repository.update_workflow_trace(workflow_id, update)

        logger.info(f"[TraceService] Completed workflow trace: {workflow_id} with status: {status}")

    async def start_task_trace(
        self,
        workflow_id: str,
        task_id: str,
        task_title: str,
        task_order: int,
        trace_id: str | None = None,
        span_id: str | None = None,
        input_query: str | None = None,
        input_intent: str | None = None,
    ) -> str:
        """Create a child span for a task and make it the current span.

        Returns the span id used for later completion/failure updates.
        """
        if not trace_id:
            from harness.observability.trace_context import trace_id_var

            trace_id = trace_id_var.get() or generate_trace_id()

        if not span_id:
            span_id = generate_span_id()

        # 获取当前 LangSmith 运行 ID，如果没有就用一个默认值
        langsmith_run_id = get_current_langsmith_run_id()
        if not langsmith_run_id:
            # 如果没有 LangSmith 运行 ID，就用 span_id 作为替代
            langsmith_run_id = span_id
            set_current_langsmith_run_id(langsmith_run_id)
            logger.info(
                f"[TraceService] Using span_id as default langsmith_run_id: {langsmith_run_id}"
            )

        trace = TaskTraceCreate(
            trace_id=trace_id,
            workflow_id=workflow_id,
            task_id=task_id,
            span_id=span_id,
            task_title=task_title,
            task_order=task_order,
            started_at=datetime.now(UTC),
            status="running",
            input_query=input_query,
            input_intent=input_intent,
            langsmith_run_id=langsmith_run_id,
        )

        await self.repository.create_task_trace(trace)

        set_trace_context(span_id=span_id)

        logger.info(f"[TraceService] Started task trace: {span_id} for task: {task_title}")
        return span_id

    async def complete_task_trace(
        self,
        span_id: str,
        output_summary: str | None = None,
        output_sources: dict[str, Any] | None = None,
        langsmith_run_id: str | None = None,
    ) -> None:
        """Close a task span as succeeded, recording output summary and sources."""
        now = datetime.now(UTC)

        # 如果没有传入 langsmith_run_id，从上下文获取
        if not langsmith_run_id:
            langsmith_run_id = get_current_langsmith_run_id()

        update = TaskTraceUpdate(
            completed_at=now,
            status="completed",
            output_summary=output_summary,
            output_sources=output_sources,
            langsmith_run_id=langsmith_run_id,
        )

        await self.repository.update_task_trace(span_id, update)

        logger.info(f"[TraceService] Completed task trace: {span_id}")

    async def fail_task_trace(
        self,
        span_id: str,
        error_message: str,
        langsmith_run_id: str | None = None,
    ) -> None:
        """Close a task span as failed and store the error message."""
        now = datetime.now(UTC)

        if not langsmith_run_id:
            langsmith_run_id = get_current_langsmith_run_id()

        update = TaskTraceUpdate(
            completed_at=now,
            status="failed",
            error_message=error_message,
            langsmith_run_id=langsmith_run_id,
        )

        await self.repository.update_task_trace(span_id, update)

        logger.info(f"[TraceService] Failed task trace: {span_id}")

    async def restore_trace_context(self, workflow_id: str) -> str | None:
        """Restore the trace context from the database for the current request.

        Intended for background tasks that have no originating request context
        but must keep writing into the same trace; returns None when the
        workflow has no recorded trace.
        """
        trace = await self.repository.get_trace_by_workflow_id(workflow_id)
        if not trace:
            return None

        set_trace_context(
            trace_id=trace.trace_id,
            workflow_id=trace.workflow_id,
        )
        return trace.trace_id

    async def update_workflow_langsmith_info(
        self,
        workflow_id: str,
        langsmith_run_id: str,
        langsmith_url: str | None = None,
    ) -> None:
        """Patch the workflow trace with LangSmith run id/link once known."""
        update = WorkflowTraceUpdate(
            langsmith_run_id=langsmith_run_id,
            langsmith_url=langsmith_url,
        )

        await self.repository.update_workflow_trace(workflow_id, update)


def get_trace_service(repository: TraceRepository | None = None) -> TraceService:
    """获取 TraceService 实例。

    注意：harness 层不直接依赖 app 层。调用方（app/service_factory）
    必须传入已经实例化的 TraceRepository，或者使用 app 层提供的工厂函数。
    """
    if repository is None:
        raise ValueError(
            "TraceRepository must be provided. "
            "Use app.service_factory.create_trace_service() or pass a repository instance."
        )
    return TraceService(repository)
