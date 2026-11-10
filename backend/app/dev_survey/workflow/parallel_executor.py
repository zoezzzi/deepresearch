"""
并行任务执行器

支持任务并行执行，提高工作流效率
"""

import asyncio
from typing import Any

from app.dev_survey.events.event_publisher import EventPublisher
from app.dev_survey.models.models import Task
from app.dev_survey.services.task_execution_service import TaskExecutionService
from harness.logger import logger
from harness.observability.trace_context import set_trace_context
from harness.observability.trace_service import TraceService


class ParallelTaskExecutor:
    """
    并行任务执行器

    管理多个任务的并行执行，控制并发度，处理错误
    trace 失败时不影响任务正常执行
    """

    def __init__(
        self,
        task_execution_service: TaskExecutionService,
        event_publisher: EventPublisher,
        max_concurrent_tasks: int = 3,
        trace_service: TraceService | None = None,
    ):
        self.task_execution_service = task_execution_service
        self.event_publisher = event_publisher
        self.max_concurrent_tasks = max_concurrent_tasks
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self.trace_service = trace_service
        logger.info(
            f"[ParallelExecutor] Initialized with max_concurrent_tasks={max_concurrent_tasks}"
        )

    async def execute_single_task(
        self, task: Task, trace_context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Run one task under the shared semaphore and never raise to the caller.

        Business failures are converted into a result dict with status "failed";
        tracing is best-effort so an observability outage cannot fail the task.
        """
        async with self.semaphore:
            logger.info(f"[ParallelExecutor] Executing task: {task.title}")

            if trace_context:
                set_trace_context(
                    trace_id=trace_context.get("trace_id"),
                    workflow_id=trace_context.get("workflow_id"),
                    span_id=trace_context.get("span_id"),
                    langsmith_run_id=trace_context.get("langsmith_run_id"),
                )

            # 任务开始前立刻在内存中记录 started_at（暂时不写入数据库）
            # 真正落库由 graph 层的批量更新完成，避免并发任务逐条写库
            if not task.started_at:
                task.start()

            span_id = await self._start_task_trace_safe(task)

            try:
                await self.event_publisher.publish_task_start_event(
                    workflow_id=task.workflow_id, task_id=task.task_id, task_title=task.title
                )

                summary, sources_summary, notices = await self.task_execution_service.execute_task(
                    task
                )

                task_result = {
                    "task_id": task.task_id,
                    "title": task.title,
                    "status": "completed",
                    "summary": summary,
                    "sources_summary": sources_summary,
                    "notices": notices,
                    "started_at": task.started_at,
                }

                if span_id:
                    await self._complete_task_trace_safe(span_id, summary, sources_summary)

                await self.event_publisher.publish_task_complete_event(
                    workflow_id=task.workflow_id,
                    task_id=task.task_id,
                    task_title=task.title,
                    summary=summary,
                    sources_summary=sources_summary,
                    notices=notices,
                )

                logger.info(f"[ParallelExecutor] Task completed: {task.title}")
                return task_result

            except Exception as e:
                logger.error(f"[ParallelExecutor] Task failed: {task.title}, error: {str(e)}")

                task_result = {
                    "task_id": task.task_id,
                    "title": task.title,
                    "status": "failed",
                    "error": str(e),
                    "summary": None,
                    "sources_summary": None,
                    "notices": None,
                    "started_at": task.started_at,
                }

                if span_id:
                    await self._fail_task_trace_safe(span_id, str(e))

                await self.event_publisher.publish_error_event(
                    workflow_id=task.workflow_id, message=f"Task {task.title} failed: {str(e)}"
                )

                return task_result

    async def _start_task_trace_safe(self, task: Task) -> str | None:
        """安全地启动 task trace，失败时不阻断任务执行"""
        if not self.trace_service:
            return None
        try:
            span_id = await self.trace_service.start_task_trace(
                workflow_id=task.workflow_id,
                task_id=task.task_id,
                task_title=task.title,
                task_order=task.order,
                input_query=task.query,
                input_intent=task.intent,
            )
            return span_id
        except Exception as e:
            logger.error(f"[ParallelExecutor] Failed to start task trace for {task.title}: {e}")
            return None

    async def _complete_task_trace_safe(
        self, span_id: str, summary: str, sources_summary: str | None
    ) -> None:
        """安全地完成 task trace，失败时仅记录日志"""
        if not self.trace_service:
            return
        try:
            await self.trace_service.complete_task_trace(
                span_id=span_id,
                output_summary=summary,
                output_sources={"sources_summary": sources_summary} if sources_summary else None,
            )
        except Exception as e:
            logger.error(f"[ParallelExecutor] Failed to complete task trace {span_id}: {e}")

    async def _fail_task_trace_safe(self, span_id: str, error_message: str) -> None:
        """安全地标记 task trace 失败，失败时仅记录日志"""
        if not self.trace_service:
            return
        try:
            await self.trace_service.fail_task_trace(
                span_id=span_id,
                error_message=error_message,
            )
        except Exception as e:
            logger.error(f"[ParallelExecutor] Failed to record task trace failure {span_id}: {e}")

    async def execute_tasks_parallel(
        self, tasks: list[Task], trace_context: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        并行执行多个任务

        Args:
            tasks: 任务列表
            trace_context: 可选的 trace 上下文信息

        Returns:
            任务结果列表
        """
        logger.info(f"[ParallelExecutor] Starting parallel execution of {len(tasks)} tasks")

        tasks_coroutines = [
            self.execute_single_task(task, trace_context=trace_context) for task in tasks
        ]

        # 单任务异常已在 execute_single_task 内部收敛为结果字典，因此这里不需要收集异常
        results = await asyncio.gather(*tasks_coroutines, return_exceptions=False)

        completed_count = sum(1 for r in results if r.get("status") == "completed")
        failed_count = sum(1 for r in results if r.get("status") == "failed")

        logger.info(
            f"[ParallelExecutor] Parallel execution complete: {completed_count} completed, {failed_count} failed"
        )

        return results

    async def execute_tasks_parallel_with_timeout(
        self, tasks: list[Task], total_timeout: float | None = None
    ) -> list[dict[str, Any]]:
        """
        带超时的并行任务执行

        Args:
            tasks: 任务列表
            total_timeout: 总超时时间（秒）

        Returns:
            任务结果列表
        """
        if total_timeout:
            try:
                return await asyncio.wait_for(
                    self.execute_tasks_parallel(tasks), timeout=total_timeout
                )
            except TimeoutError:
                # 整批超时与单任务失败语义不同，向上抛出交由调用方决定是否降级
                logger.error(
                    f"[ParallelExecutor] Parallel execution timed out after {total_timeout} seconds"
                )
                raise
        else:
            return await self.execute_tasks_parallel(tasks)
