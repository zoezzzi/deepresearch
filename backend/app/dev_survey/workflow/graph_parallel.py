"""
开发者调研助手工作流图定义（优化版 v4.0）

统一并行图结构，节点间数据通过 Checkpoint (WorkflowState) 传递。
移除 Store 依赖，消除多存储层不一致风险。

v4.0: 移除 Store + DB 批量写入重试 + 衍生数据按需重算
"""

import asyncio
import time
import uuid
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from app.common.utils.time_utils import get_current_utc_time
from app.dev_survey.events import EventPublisher
from app.dev_survey.models.models import Task
from app.dev_survey.repositories import TaskRepository
from app.dev_survey.services import (
    EvaluationService,
    ReportGenerationService,
    ResearchPlanService,
    TaskExecutionService,
)
from app.dev_survey.tasks import run_evaluation_task
from app.dev_survey.workflow.parallel_executor import ParallelTaskExecutor
from app.dev_survey.workflow.state import WorkflowState
from harness.config import get_harness_settings
from harness.evaluation.orchestrator import EvaluationOrchestrator
from harness.logger import logger
from harness.observability.trace_context import get_trace_context
from harness.observability.trace_service import TraceService
from harness.storage.base import ObjectStorage

settings = get_harness_settings()


class ResearchWorkflowGraphParallel:
    """
    调研工作流图（优化版 v4.0）

    统一并行图结构，节点间数据通过 Checkpoint (WorkflowState) 传递。
    task_results 和 quality_report 从 Store 迁移至 WorkflowState。
    """

    def __init__(
        self,
        research_plan_service: ResearchPlanService,
        task_execution_service: TaskExecutionService,
        report_generation_service: ReportGenerationService,
        event_publisher: EventPublisher,
        task_repository: TaskRepository,
        object_storage: ObjectStorage,
        evaluation_service: EvaluationService,
        evaluation_orchestrator: EvaluationOrchestrator,
        trace_service: TraceService = None,
        max_concurrent_tasks: int = 3,
        critic_agent=None,
        reflection_enabled: bool = False,
        checkpointer: BaseCheckpointSaver = None,
    ):
        self.research_plan_service = research_plan_service
        self.task_execution_service = task_execution_service
        self.report_generation_service = report_generation_service
        self.event_publisher = event_publisher
        self.task_repository = task_repository
        self.object_storage = object_storage
        self.evaluation_service = evaluation_service
        self.evaluation_orchestrator = evaluation_orchestrator
        self.trace_service = trace_service
        self.max_concurrent_tasks = max_concurrent_tasks
        self.critic_agent = critic_agent
        # 缺少 critic 时强制关闭反思，避免条件边进入 reflect 节点后访问空对象
        self.reflection_enabled = reflection_enabled and critic_agent is not None
        self.checkpointer = checkpointer

        self.parallel_executor = ParallelTaskExecutor(
            task_execution_service=task_execution_service,
            event_publisher=event_publisher,
            max_concurrent_tasks=max_concurrent_tasks,
            trace_service=trace_service,
        )

        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Compile the LangGraph topology; reflection nodes are wired only when enabled."""
        workflow = StateGraph(WorkflowState)

        workflow.add_node("plan", self._plan_node)
        workflow.add_node("execute", self._execute_node)
        workflow.add_node("generate_report", self._generate_report_node)

        workflow.set_entry_point("plan")
        workflow.add_edge("plan", "execute")
        workflow.add_edge("execute", "generate_report")

        if self.reflection_enabled:
            workflow.add_node("reflect", self._reflect_node)
            workflow.add_conditional_edges(
                "generate_report", self._should_reflect, {"reflect": "reflect", "end": END}
            )
            workflow.add_conditional_edges(
                "reflect",
                self._should_continue_reflection,
                {"execute": "execute", "generate_report": "generate_report", "end": END},
            )
        else:
            workflow.add_edge("generate_report", END)

        return workflow.compile(checkpointer=self.checkpointer)

    def _should_reflect(self, state: WorkflowState) -> str:
        """Conditional edge after report generation; at most one reflection round is allowed."""
        if not self.reflection_enabled:
            return "end"
        quality_report = state.get("quality_report")
        if quality_report is None:
            return "end"
        reflection_round = state.get("reflection_round", 0)
        if reflection_round >= 1:
            return "end"
        if not self.critic_agent.needs_reflection(quality_report):
            logger.info(
                f"[WorkflowParallel] Report quality sufficient "
                f"(score={quality_report.get('overall_score')}), skipping reflection"
            )
            return "end"
        logger.info("[WorkflowParallel] Triggering self-reflection (round 1/1)")
        return "reflect"

    def _should_continue_reflection(self, state: WorkflowState) -> str:
        """Re-enter execute only when reflection produced pending supplementary tasks."""
        supplementary_queries = state.get("supplementary_queries", [])
        if supplementary_queries:
            new_tasks = state.get("tasks", [])
            pending = [t for t in new_tasks if t.get("status") == "pending"]
            if pending:
                logger.info(f"[WorkflowParallel] Executing {len(pending)} supplementary tasks")
                return "execute"
        return "end"

    async def _reflect_node(self, state: WorkflowState) -> dict[str, Any]:
        """Evaluate report quality and enqueue supplementary tasks for critical gaps."""
        logger.info(
            f"[WorkflowParallel] Starting self-reflection for workflow {state['workflow_id']}"
        )
        reflection_round = state.get("reflection_round", 0) + 1
        report_content = state.get("report_content", "")
        topic = state["topic"]
        sub_questions = state.get("sub_questions", [])

        if not report_content:
            # 没有报告可评估时仍递增轮次，防止条件边在同一次调用中反复触发反思
            logger.warning("[WorkflowParallel] No report content for reflection")
            return {"reflection_round": reflection_round, "updated_at": get_current_utc_time()}

        try:
            # 从 Checkpoint 状态读取 quality_report（原从 Store 加载）
            quality_report = state.get("quality_report")
            if quality_report is None:
                quality_report = await self.critic_agent.execute(
                    topic=topic,
                    report_content=report_content,
                    sub_questions=sub_questions,
                    tasks=state.get("tasks", []),
                )

            supplementary_queries = []
            if self.critic_agent.has_critical_gaps(quality_report):
                supplementary_queries = self.critic_agent.extract_queries(quality_report)

            if supplementary_queries:
                updated_tasks = await self._add_supplementary_tasks(state, supplementary_queries)
                return {
                    "tasks": updated_tasks,
                    "supplementary_queries": supplementary_queries,
                    "reflection_round": reflection_round,
                    "updated_at": get_current_utc_time(),
                }

            return {"reflection_round": reflection_round, "updated_at": get_current_utc_time()}
        except Exception as e:
            logger.error(f"[WorkflowParallel] Reflection failed: {str(e)}")
            return {"reflection_round": reflection_round, "updated_at": get_current_utc_time()}

    async def _add_supplementary_tasks(
        self, state: WorkflowState, supplementary_queries: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Persist reflection-derived tasks and append them to the state task list.

        Orders start at 100 so downstream code can distinguish supplementary tasks
        from the original plan; DB failures are logged and tolerated.
        """
        existing_tasks = state.get("tasks", [])
        max_order = max((t.get("order", 0) for t in existing_tasks), default=0)

        new_tasks = []
        for i, sq in enumerate(supplementary_queries):
            task_id = str(uuid.uuid4())
            order = max_order + 100 + i
            new_tasks.append(
                {
                    "task_id": task_id,
                    "title": sq.get("title", "Supplementary Research"),
                    "intent": sq.get("intent", ""),
                    "query": sq.get("query", ""),
                    "order": order,
                    "depends_on": [],
                    "status": "pending",
                }
            )

            task_entity = Task(
                task_id=task_id,
                workflow_id=state["workflow_id"],
                title=sq.get("title", "Supplementary"),
                intent=sq.get("intent", ""),
                query=sq.get("query", ""),
                order=order,
                depends_on=[],
            )
            try:
                await self.task_repository.save(task_entity)
            except Exception as e:
                logger.error(f"[WorkflowParallel] Failed to save supplementary task {task_id}: {e}")

        logger.info(f"[WorkflowParallel] Added {len(new_tasks)} supplementary tasks")
        return existing_tasks + new_tasks

    def _calculate_optimal_concurrency(self, task_count: int) -> int:
        """Return a concurrency cap sized to the batch, never above the configured maximum."""
        if task_count == 0:
            return 1
        if task_count <= 2:
            return task_count
        elif task_count <= 5:
            return min(self.max_concurrent_tasks, 3)
        elif task_count <= 10:
            return min(self.max_concurrent_tasks, 4)
        else:
            return min(self.max_concurrent_tasks, 5)

    async def _execute_node(self, state: WorkflowState) -> dict[str, Any]:
        """Run pending tasks in parallel and push their raw results into the checkpoint."""
        workflow_id = state["workflow_id"]
        task_dicts = state["tasks"]

        if not task_dicts:
            logger.warning("[WorkflowParallel] No tasks to execute")
            return {"updated_at": get_current_utc_time()}

        pending = [t for t in task_dicts if t.get("status") == "pending"]
        logger.info(f"[WorkflowParallel] Executing {len(pending)}/{len(task_dicts)} tasks")

        execute_start = time.time()

        result = await self._execute_tasks_parallel(state, task_dicts, workflow_id)

        execute_end = time.time()
        execute_duration_ms = int((execute_end - execute_start) * 1000)

        if result.get("error"):
            return {
                "tasks": result["tasks"],
                "error": result["error"],
                "updated_at": get_current_utc_time(),
            }

        # task_results 直接进入 Checkpoint（原写入 Store），衍生数据由 generate_report 节点按需重算
        logger.info(
            f"[WorkflowParallel] Execute phase completed: {execute_duration_ms}ms "
            f"({len(task_dicts)} tasks)"
        )

        return {
            "tasks": result["tasks"],
            "task_results": result["task_results"],
            "updated_at": get_current_utc_time(),
        }

    async def _execute_tasks_parallel(
        self, state: WorkflowState, task_dicts: list[dict[str, Any]], workflow_id: str
    ) -> dict[str, Any]:
        """Build task entities, tune concurrency, then delegate to the parallel executor."""
        pending_dicts = [t for t in task_dicts if t.get("status") == "pending"]
        tasks = self._build_task_entities(pending_dicts, workflow_id)

        optimal_concurrency = self._calculate_optimal_concurrency(len(tasks))
        if optimal_concurrency != self.max_concurrent_tasks:
            logger.info(
                f"[WorkflowParallel] Adjusting concurrency from {self.max_concurrent_tasks} to {optimal_concurrency}"
            )
            # 注意：executor 实例在同一个 graph 内共享，此处改写并发度会影响同一实例上的后续批次
            self.parallel_executor.max_concurrent_tasks = optimal_concurrency
            self.parallel_executor.semaphore = asyncio.Semaphore(optimal_concurrency)

        trace_context = get_trace_context()

        try:
            task_results = await self.parallel_executor.execute_tasks_parallel(
                tasks, trace_context=trace_context
            )
            return await self._process_execution_results(task_dicts, task_results, workflow_id)
        except Exception as e:
            logger.error(f"[WorkflowParallel] Parallel task execution failed: {str(e)}")
            await self.event_publisher.publish_error_event(
                workflow_id=workflow_id, message=f"Parallel execution failed: {str(e)}"
            )
            return {"error": str(e), "tasks": task_dicts, "updated_at": get_current_utc_time()}

    def _build_task_entities(
        self, task_dicts: list[dict[str, Any]], workflow_id: str
    ) -> list[Task]:
        """Rehydrate checkpoint task dicts into domain entities for the executor."""
        return [
            Task(
                task_id=task_dict["task_id"],
                workflow_id=workflow_id,
                title=task_dict["title"],
                intent=task_dict["intent"],
                query=task_dict["query"],
                order=task_dict["order"],
            )
            for task_dict in task_dicts
        ]

    async def _process_execution_results(
        self, task_dicts: list[dict[str, Any]], task_results: list[dict[str, Any]], workflow_id: str
    ) -> dict[str, Any]:
        """Merge per-task statuses, then persist them before the checkpoint is written."""
        updated_tasks = task_dicts.copy()

        for result in task_results:
            for i, task_dict in enumerate(updated_tasks):
                if task_dict["task_id"] == result["task_id"]:
                    updated_tasks[i]["status"] = result["status"]
                    break

        # DB 写入：同步重试 3 次，失败抛异常阻止 Checkpoint 写入
        await self._update_tasks_batch_with_retry(workflow_id, task_results)

        # 衍生数据不再预计算，由 generate_report 节点按需重算
        logger.info("[WorkflowParallel] Task execution complete")

        return {
            "tasks": updated_tasks,
            "task_results": task_results,
            "updated_at": get_current_utc_time(),
        }

    async def _update_tasks_batch_with_retry(
        self, workflow_id: str, task_results: list[dict[str, Any]]
    ) -> None:
        """DB 批量更新，带重试。

        3 次重试都失败则抛异常，阻止 Checkpoint 写入。
        使用 find_by_ids 批量加载替代逐个 find_by_id。
        """
        task_ids = [r["task_id"] for r in task_results]

        last_error = None
        for attempt in range(3):
            try:
                # ① 批量加载（1 次查询）
                tasks = await self.task_repository.find_by_ids(task_ids)
                task_map = {t.task_id: t for t in tasks}

                tasks_to_update = []
                for result in task_results:
                    task = task_map.get(result["task_id"])
                    if not task:
                        continue
                    # 设置 started_at
                    if result.get("started_at") and not task.started_at:
                        task.started_at = result["started_at"]
                        task.status = "running"
                        task.updated_at = get_current_utc_time()

                    if result["status"] == "completed":
                        task.complete(
                            result.get("summary", ""),
                            result.get("sources_summary", ""),
                            result.get("notices", ""),
                        )
                    else:
                        task.fail(result.get("error", "Unknown error"))

                    tasks_to_update.append(task)

                # ② 批量更新
                if tasks_to_update:
                    await self.task_repository.update_batch(tasks_to_update)
                    logger.info(
                        f"[WorkflowParallel] Batch updated {len(tasks_to_update)} tasks "
                        f"(attempt {attempt + 1})"
                    )
                return  # 成功

            except Exception as e:
                last_error = e
                if attempt < 2:
                    wait = 0.5 * (attempt + 1)  # 0.5s, 1.0s
                    logger.warning(
                        f"[WorkflowParallel] DB write attempt {attempt + 1}/3 failed: {e}, "
                        f"retrying in {wait}s..."
                    )
                    await asyncio.sleep(wait)

        # 3 次都失败 → 抛异常，阻止 Checkpoint 保存
        raise RuntimeError(
            f"[WorkflowParallel] DB write failed after 3 retries "
            f"for workflow {workflow_id}: {last_error}"
        )

    async def _plan_node(self, state: WorkflowState) -> dict[str, Any]:
        """Generate and persist the task plan, then publish it to SSE subscribers."""
        logger.info(f"[WorkflowParallel] Executing plan node for workflow {state['workflow_id']}")

        try:
            workflow_id = state["workflow_id"]
            topic = state["topic"]
            description = ""  # description 从 DB 表读取，不入 checkpoint

            tasks = await self.research_plan_service.generate_tasks(
                workflow_id=workflow_id, topic=topic, description=description
            )

            task_dicts = [
                {
                    "task_id": task.task_id,
                    "title": task.title,
                    "intent": task.intent,
                    "query": task.query,
                    "order": task.order,
                    "depends_on": task.depends_on,
                    "status": "pending",
                }
                for task in tasks
            ]

            try:
                await self.task_repository.save_batch(tasks)
                logger.info(f"[WorkflowParallel] Saved {len(tasks)} tasks to database")
            except Exception as db_error:
                logger.error(f"[WorkflowParallel] Failed to save tasks to database: {db_error}")

            await self.event_publisher.publish_plan_event(
                workflow_id=state["workflow_id"], tasks=task_dicts
            )

            sub_questions = [task.title for task in tasks]

            logger.info(f"[WorkflowParallel] Plan generated with {len(task_dicts)} tasks")
            return {
                "tasks": task_dicts,
                "sub_questions": sub_questions,
                "updated_at": get_current_utc_time(),
            }
        except Exception as e:
            logger.error(f"[WorkflowParallel] Plan node failed: {str(e)}")
            await self.event_publisher.publish_error_event(
                workflow_id=state["workflow_id"], message=str(e)
            )
            return {"error": str(e), "updated_at": get_current_utc_time()}

    async def _generate_report_node(self, state: WorkflowState) -> dict[str, Any]:
        """Render the final report, upload it, and fire-and-forget the evaluation task.

        When fewer than half of the original tasks completed, report generation is
        skipped and the workflow is marked accordingly. All task-derived inputs are
        recomputed here from the checkpoint, falling back to the database.
        """
        logger.info(f"[WorkflowParallel] Generating report for workflow {state['workflow_id']}")
        workflow_id = state["workflow_id"]

        tasks = state.get("tasks", [])
        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t.get("status") == "completed")
        failed_tasks = sum(1 for t in tasks if t.get("status") == "failed")

        logger.info(
            f"[WorkflowParallel] Task summary: {completed_tasks}/{total_tasks} completed, {failed_tasks} failed"
        )

        task_summary = {"total": total_tasks, "completed": completed_tasks, "failed": failed_tasks}

        original_task_count = sum(1 for t in tasks if t.get("order", 0) < 100)
        # 完成率只统计原始计划任务，reflection 补充任务（order >= 100）不应拉低分母
        completion_rate = completed_tasks / max(original_task_count, 1)

        if completion_rate <= 0.5:
            logger.warning(f"[WorkflowParallel] Completion rate {completion_rate:.1%} <= 50%")
            return {
                "report_content": None,
                "report_url": None,
                "workflow_status": "all_failed"
                if failed_tasks == total_tasks
                else "partial_failed",
                "task_summary": task_summary,
                "updated_at": get_current_utc_time(),
            }

        # ─── ① task_results：从 Checkpoint 获取，降级到 DB ───
        task_results = state.get("task_results", [])
        if not task_results:
            logger.info("[WorkflowParallel] Checkpoint miss for task_results, falling back to DB")
            task_results = await self._load_task_results_from_db(workflow_id)

        # ─── ② 衍生数据：按需重算 ───
        retrieved_chunks = [r["sources_summary"] for r in task_results if r.get("sources_summary")]
        retrieved_documents = [
            {"content": r["sources_summary"], "title": r["title"], "task_id": r["task_id"]}
            for r in task_results
            if r.get("sources_summary")
        ]

        sub_questions = state.get("sub_questions", [])

        report_generated = False
        report_content = None
        report_url = None
        report_error = None
        evaluation_id = None

        try:
            logger.info("[WorkflowParallel] Starting report generation")

            task_results_map = {result["task_id"]: result for result in (task_results or [])}

            task_entities = []
            for task_dict in state["tasks"]:
                task = Task(
                    task_id=task_dict["task_id"],
                    workflow_id=workflow_id,
                    title=task_dict["title"],
                    intent=task_dict["intent"],
                    query=task_dict["query"],
                    order=task_dict["order"],
                )
                if task_dict["task_id"] in task_results_map:
                    result = task_results_map[task_dict["task_id"]]
                    task.summary = result.get("summary")
                    task.sources_summary = result.get("sources_summary")
                    task.notices = result.get("notices")
                task_entities.append(task)

            report = await self.report_generation_service.generate_report(
                workflow_id=workflow_id, topic=state["topic"], tasks=task_entities
            )
            report_content = report.content
            report_generated = True
            logger.info(f"[WorkflowParallel] Report generated: {len(report_content)} chars")

            try:
                report_content_bytes = report.content.encode("utf-8")
                report_filename = f"{state['workflow_id']}.md"
                report_url = await self.object_storage.upload_object(
                    bucket_name="reports",
                    object_name=report_filename,
                    data=report_content_bytes,
                    content_type="text/markdown",
                )
            except Exception as storage_error:
                logger.error(f"[WorkflowParallel] Failed to save report: {storage_error}")
                report_url = f"/reports/{state['workflow_id']}"

            await self.event_publisher.publish_result_event(
                workflow_id=state["workflow_id"], report_url=report_url
            )

            if report_generated:
                try:
                    scenario_id = state.get("scenario_id", "dev_survey_v1")
                    evaluation = await self.evaluation_service.create_evaluation(
                        workflow_id, scenario_id
                    )
                    evaluation_id = evaluation.evaluation_id
                    # 评测以游离任务执行：不阻塞工作流收尾，也不参与 Checkpoint 状态
                    asyncio.create_task(
                        run_evaluation_task(
                            evaluation_id=evaluation_id,
                            workflow_id=workflow_id,
                            report=report_content,
                            contexts=retrieved_chunks,
                            question=state["topic"],
                            sub_questions=sub_questions,
                            checklist_items=sub_questions,
                            retrieved_documents=retrieved_documents,
                            citations=[],
                            evaluation_service=self.evaluation_service,
                            evaluation_orchestrator=self.evaluation_orchestrator,
                        )
                    )
                except Exception as eval_error:
                    logger.error(f"[WorkflowParallel] Failed to trigger evaluation: {eval_error}")

        except Exception as e:
            report_error = str(e)
            logger.error(f"[WorkflowParallel] Report generation failed: {report_error}")
            try:
                minimal_report = await self._generate_minimal_report(state)
                if minimal_report:
                    report_content = minimal_report
                    report_generated = True
                    try:
                        report_content_bytes = report_content.encode("utf-8")
                        report_filename = f"{state['workflow_id']}.md"
                        report_url = await self.object_storage.upload_object(
                            bucket_name="reports",
                            object_name=report_filename,
                            data=report_content_bytes,
                            content_type="text/markdown",
                        )
                        await self.event_publisher.publish_result_event(
                            workflow_id=state["workflow_id"], report_url=report_url
                        )
                    except Exception as storage_error:
                        logger.error(
                            f"[WorkflowParallel] Failed to save minimal report: {storage_error}"
                        )
            except Exception as fallback_error:
                logger.error(f"[WorkflowParallel] Minimal report failed: {fallback_error}")
            await self.event_publisher.publish_error_event(
                workflow_id=state["workflow_id"],
                message=f"Report generation failed: {report_error}",
            )

        if report_generated:
            workflow_status = (
                "all_success" if completed_tasks == original_task_count else "partial_failed"
            )
        else:
            workflow_status = (
                "report_failed" if completed_tasks == original_task_count else "partial_failed"
            )

        quality_report = None
        if self.reflection_enabled and report_generated and report_content:
            try:
                quality_report = await self.critic_agent.execute(
                    topic=state["topic"],
                    report_content=report_content,
                    sub_questions=state.get("sub_questions", []),
                    tasks=state.get("tasks", []),
                )
                # quality_report 写入 Checkpoint state（原写入 Store）
                logger.info(
                    f"[WorkflowParallel] Critic evaluation: score={quality_report.get('overall_score')}, "
                    f"gaps={len(quality_report.get('gaps', []))}"
                )
            except Exception as critic_error:
                logger.error(f"[WorkflowParallel] Critic evaluation failed: {critic_error}")

        result = {
            "report_content": report_content,
            "report_url": report_url,
            "workflow_status": workflow_status,
            "task_summary": task_summary,
            "updated_at": get_current_utc_time(),
        }
        if report_error:
            result["error"] = report_error
        if quality_report:
            result["quality_report"] = quality_report

        return result

    async def _generate_minimal_report(self, state: WorkflowState) -> str:
        """Build a degraded Markdown report listing only completed tasks."""
        try:
            topic = state["topic"]
            tasks = state.get("tasks", [])
            report_parts = [f"# {topic}", "", "## Task Summary", ""]
            for task in tasks:
                if task.get("status") == "completed":
                    report_parts.append(f"### {task.get('title', 'Untitled')}")
                    report_parts.append("")
            report_parts.append("---")
            report_parts.append("*Note: Minimal report due to generation failure.*")
            return "\n".join(report_parts)
        except Exception as e:
            logger.error(f"[WorkflowParallel] Minimal report failed: {e}")
            return ""

    async def _load_task_results_from_db(self, workflow_id: str) -> list[dict[str, Any]]:
        """Rebuild task results from persisted tasks when the checkpoint has none."""
        try:
            tasks = await self.task_repository.find_by_workflow_id(workflow_id)
            results = []
            for task in tasks:
                status = task.status.value if hasattr(task.status, "value") else str(task.status)
                results.append(
                    {
                        "task_id": task.task_id,
                        "title": task.title,
                        "status": status
                        if status == "completed"
                        else "failed"
                        if status == "failed"
                        else "pending",
                        "summary": task.summary,
                        "sources_summary": task.sources_summary,
                        "notices": task.notices,
                    }
                )
            logger.info(f"[WorkflowParallel] Loaded {len(results)} task results from DB")
            return results
        except Exception as e:
            logger.error(f"[WorkflowParallel] Failed to load task results from DB: {e}")
            return []

    @property
    def graph(self):
        """Compiled LangGraph instance used by the service to invoke the workflow."""
        return self._graph
