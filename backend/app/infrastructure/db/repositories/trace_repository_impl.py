"""
Trace 仓储实现

基于 SQLAlchemy 的追踪数据持久化实现
每个方法内部管理自己的 Session（通过 get_db_session 上下文管理器）
"""

import time

from sqlalchemy.orm import Session

from app.infrastructure.db.models import WorkflowTaskTraceModel, WorkflowTraceModel
from harness.db.session import get_db_session
from harness.logger import logger
from harness.observability.trace_models import (
    PerformanceSummary,
    TaskTraceCreate,
    TaskTraceResponse,
    TaskTraceUpdate,
    WorkflowTraceCreate,
    WorkflowTraceResponse,
    WorkflowTraceUpdate,
)
from harness.observability.trace_repository import TraceRepository


def _calculate_duration_ms(started_at, completed_at):
    """计算持续时间（毫秒）"""
    if not started_at or not completed_at:
        return None
    delta = completed_at - started_at
    return int(delta.total_seconds() * 1000)


def _retry_with_backoff(operation_name: str, func, max_attempts: int = 3):
    """
    带指数退避的重试执行器

    异常传播策略：重试耗尽后抛出原始异常到调用方
    """
    last_error = None
    for attempt in range(max_attempts):
        try:
            func()
            return
        except Exception as e:
            last_error = e
            if attempt < max_attempts - 1:
                wait_time = 1.0 * (2**attempt)
                logger.warning(
                    f"[TraceRepository] {operation_name} failed (attempt {attempt + 1}/{max_attempts}), "
                    f"retrying in {wait_time:.1f}s: {e}"
                )
                time.sleep(wait_time)
            else:
                logger.error(
                    f"[TraceRepository] {operation_name} failed after {max_attempts} attempts: {e}"
                )

    raise last_error


class TraceRepositoryImpl(TraceRepository):
    """
    Trace 持久化仓储实现

    设计说明：
    - 不持有 db_session 实例，每个方法内部通过 get_db_session() 获取独立 Session
    - 这样确保即使某个 Session 因连接中断而失效，不影响其他操作
    - 与主业务 Repository 不同，Trace 写入是"尽力而为"，失败时重试并传播异常
    """

    async def create_workflow_trace(self, trace: WorkflowTraceCreate) -> None:
        def _create(db: Session):
            model = WorkflowTraceModel(
                trace_id=trace.trace_id,
                workflow_id=trace.workflow_id,
                request_id=trace.request_id,
                scenario_id=trace.scenario_id,
                started_at=trace.started_at,
                status=trace.status,
                langsmith_run_id=trace.langsmith_run_id,
            )
            db.add(model)

        _retry_with_backoff(
            "create_workflow_trace",
            lambda: _create_with_session(_create),
        )
        logger.info(f"[TraceRepository] Created workflow trace: {trace.trace_id}")

    async def update_workflow_trace(self, workflow_id: str, update: WorkflowTraceUpdate) -> None:
        def _update(db: Session):
            model = (
                db.query(WorkflowTraceModel)
                .filter(WorkflowTraceModel.workflow_id == workflow_id)
                .first()
            )
            if model:
                if update.completed_at is not None:
                    model.completed_at = update.completed_at
                    if model.started_at:
                        duration_ms = _calculate_duration_ms(model.started_at, model.completed_at)
                        model.duration_ms = duration_ms
                elif update.duration_ms is not None:
                    model.duration_ms = update.duration_ms
                if update.status is not None:
                    model.status = update.status
                if update.langsmith_run_id is not None:
                    model.langsmith_run_id = update.langsmith_run_id
                if update.langsmith_url is not None:
                    model.langsmith_url = update.langsmith_url
                if update.execute_duration_ms is not None:
                    model.execute_duration_ms = update.execute_duration_ms
                return True
            return False

        found = False

        def _do_update():
            nonlocal found
            with get_db_session() as db:
                found = _update(db)

        _retry_with_backoff("update_workflow_trace", _do_update)

        if found:
            logger.info(f"[TraceRepository] Updated workflow trace: {workflow_id}")
        else:
            logger.warning(f"[TraceRepository] Workflow trace not found for update: {workflow_id}")

    async def create_task_trace(self, trace: TaskTraceCreate) -> None:
        def _create(db: Session):
            model = WorkflowTaskTraceModel(
                trace_id=trace.trace_id,
                workflow_id=trace.workflow_id,
                task_id=trace.task_id,
                span_id=trace.span_id,
                task_title=trace.task_title,
                task_order=trace.task_order,
                started_at=trace.started_at,
                status=trace.status,
                input_query=trace.input_query,
                input_intent=trace.input_intent,
                langsmith_run_id=trace.langsmith_run_id,
                retry_count=trace.retry_count,
            )
            db.add(model)

        _retry_with_backoff(
            "create_task_trace",
            lambda: _create_with_session(_create),
        )
        logger.info(f"[TraceRepository] Created task trace: {trace.span_id}")

    async def update_task_trace(self, span_id: str, update: TaskTraceUpdate) -> None:
        def _update(db: Session):
            model = (
                db.query(WorkflowTaskTraceModel)
                .filter(WorkflowTaskTraceModel.span_id == span_id)
                .first()
            )
            if model:
                if update.completed_at is not None:
                    model.completed_at = update.completed_at
                    if model.started_at:
                        duration_ms = _calculate_duration_ms(model.started_at, model.completed_at)
                        model.duration_ms = duration_ms
                elif update.duration_ms is not None:
                    model.duration_ms = update.duration_ms
                if update.status is not None:
                    model.status = update.status
                if update.output_summary is not None:
                    model.output_summary = update.output_summary
                if update.output_sources is not None:
                    model.output_sources = update.output_sources
                if update.error_message is not None:
                    model.error_message = update.error_message
                if update.langsmith_run_id is not None:
                    model.langsmith_run_id = update.langsmith_run_id
                return True
            return False

        found = False

        def _do_update():
            nonlocal found
            with get_db_session() as db:
                found = _update(db)

        _retry_with_backoff("update_task_trace", _do_update)

        if found:
            logger.info(f"[TraceRepository] Updated task trace: {span_id}")
        else:
            logger.warning(f"[TraceRepository] Task trace not found for update: {span_id}")

    async def get_trace_by_workflow_id(self, workflow_id: str) -> WorkflowTraceResponse | None:
        def _query(db: Session) -> WorkflowTraceResponse | None:
            trace_model = (
                db.query(WorkflowTraceModel)
                .filter(WorkflowTraceModel.workflow_id == workflow_id)
                .first()
            )

            if not trace_model:
                return None

            task_models = (
                db.query(WorkflowTaskTraceModel)
                .filter(WorkflowTaskTraceModel.workflow_id == workflow_id)
                .order_by(WorkflowTaskTraceModel.task_order)
                .all()
            )

            task_responses = []
            for t in task_models:
                task_langsmith_run_id = t.langsmith_run_id
                if not task_langsmith_run_id:
                    # 如果历史数据中没有 langsmith_run_id，就使用 span_id 作为默认值
                    task_langsmith_run_id = t.span_id
                task_responses.append(
                    TaskTraceResponse(
                        task_id=t.task_id,
                        span_id=t.span_id,
                        task_title=t.task_title,
                        task_order=t.task_order,
                        status=t.status,
                        started_at=t.started_at,
                        completed_at=t.completed_at,
                        duration_ms=t.duration_ms,
                        input_query=t.input_query,
                        input_intent=t.input_intent,
                        output_summary=t.output_summary,
                        output_sources=t.output_sources,
                        error_message=t.error_message,
                        langsmith_run_id=task_langsmith_run_id,
                    )
                )

            performance_summary = self._calculate_performance_summary(
                task_responses, trace_model.duration_ms, trace_model.execute_duration_ms
            )

            # 如果 workflow 的 langsmith_run_id 为空，就用 trace_id 作为默认值
            workflow_langsmith_run_id = trace_model.langsmith_run_id
            if not workflow_langsmith_run_id:
                workflow_langsmith_run_id = trace_model.trace_id

            return WorkflowTraceResponse(
                trace_id=trace_model.trace_id,
                workflow_id=trace_model.workflow_id,
                scenario_id=trace_model.scenario_id,
                status=trace_model.status,
                started_at=trace_model.started_at,
                completed_at=trace_model.completed_at,
                duration_ms=trace_model.duration_ms,
                langsmith_url=trace_model.langsmith_url,
                langsmith_run_id=workflow_langsmith_run_id,
                tasks=task_responses,
                performance_summary=performance_summary,
            )

        try:
            with get_db_session() as db:
                return _query(db)
        except Exception as e:
            logger.error(f"[TraceRepository] Failed to get trace by workflow_id: {e}")
            return None

    async def get_task_traces_by_workflow_id(self, workflow_id: str) -> list[TaskTraceResponse]:
        def _query(db: Session) -> list[TaskTraceResponse]:
            task_models = (
                db.query(WorkflowTaskTraceModel)
                .filter(WorkflowTaskTraceModel.workflow_id == workflow_id)
                .order_by(WorkflowTaskTraceModel.task_order)
                .all()
            )

            return [
                TaskTraceResponse(
                    task_id=t.task_id,
                    span_id=t.span_id,
                    task_title=t.task_title,
                    task_order=t.task_order,
                    status=t.status,
                    started_at=t.started_at,
                    completed_at=t.completed_at,
                    duration_ms=t.duration_ms,
                    input_query=t.input_query,
                    input_intent=t.input_intent,
                    output_summary=t.output_summary,
                    output_sources=t.output_sources,
                    error_message=t.error_message,
                    langsmith_run_id=t.langsmith_run_id,
                )
                for t in task_models
            ]

        try:
            with get_db_session() as db:
                return _query(db)
        except Exception as e:
            logger.error(f"[TraceRepository] Failed to get task traces: {e}")
            return []

    def _calculate_performance_summary(
        self,
        task_responses: list[TaskTraceResponse],
        total_duration_ms: int | None,
        execute_duration_ms: int | None = None,
    ) -> PerformanceSummary | None:
        completed_tasks = [
            t for t in task_responses if t.duration_ms is not None and t.status == "completed"
        ]

        if not completed_tasks:
            logger.warning(
                "[TraceRepository] No completed tasks for performance summary, returning default summary"
            )
            # 返回默认值，确保字段不为空
            return PerformanceSummary(
                total_duration_ms=total_duration_ms,
                avg_task_duration_ms=0.0,
                max_task_duration_ms=0,
                min_task_duration_ms=0,
                parallel_speedup_ratio=1.0,
            )

        durations = [t.duration_ms for t in completed_tasks]
        avg_duration = sum(durations) / len(durations)
        max_duration = max(durations)
        min_duration = min(durations)

        sequential_total = sum(durations)

        speedup_ratio = 1.0
        # 改进计算条件：只要有 execute_duration_ms 就尝试计算，即使只有1个任务
        if execute_duration_ms and execute_duration_ms > 0:
            if sequential_total > 0:
                speedup_ratio = round(sequential_total / execute_duration_ms, 2)
            else:
                # 如果串行总时间为0，默认设为1
                speedup_ratio = 1.0
        elif len(completed_tasks) >= 1:
            # 如果没有 execute_duration_ms，但有任务完成时间，就用任务最大时间作为基准
            estimated_parallel_time = max_duration
            if estimated_parallel_time > 0:
                speedup_ratio = round(sequential_total / estimated_parallel_time, 2)
            else:
                speedup_ratio = 1.0

        logger.info(
            f"[TraceRepository] Performance summary calculated: speedup_ratio={speedup_ratio}, "
            f"tasks={len(completed_tasks)}, sequential={sequential_total}ms, "
            f"execute={execute_duration_ms}ms"
        )

        return PerformanceSummary(
            total_duration_ms=total_duration_ms,
            avg_task_duration_ms=round(avg_duration, 2),
            max_task_duration_ms=max_duration,
            min_task_duration_ms=min_duration,
            parallel_speedup_ratio=speedup_ratio,
        )


def _create_with_session(create_fn):
    """辅助函数：在 get_db_session 上下文中执行创建操作"""
    with get_db_session() as db:
        create_fn(db)
