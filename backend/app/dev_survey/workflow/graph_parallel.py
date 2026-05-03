"""
开发者调研助手工作流图定义（优化版）

统一并行图结构，节点间数据传递使用 LangGraph Store

v3.0: 数据模型拆分 + Store 集成 + 移除串行模式
"""
from typing import Dict, Any, List, Optional
import asyncio
import time
import uuid
from langgraph.graph import StateGraph, END
from app.dev_survey.workflow.state import WorkflowState
from app.dev_survey.services import (
    ResearchPlanService,
    TaskExecutionService,
    ReportGenerationService,
    EvaluationService
)
from app.dev_survey.models.models import Task
from app.dev_survey.repositories import TaskRepository
from app.dev_survey.events import EventPublisher
from app.dev_survey.tasks import run_evaluation_task
from app.dev_survey.workflow.parallel_executor import ParallelTaskExecutor
from harness.storage.base import ObjectStorage
from harness.evaluation.orchestrator import EvaluationOrchestrator
from harness.logger import logger
from harness.config import get_harness_settings
from harness.observability.trace_service import TraceService
from harness.observability.trace_context import get_trace_context
from app.common.utils.time_utils import get_current_utc_time

settings = get_harness_settings()

_STORE_INTERMEDIATE = "intermediate"
_STORE_TTL = 3600


class ResearchWorkflowGraphParallel:
    """
    调研工作流图（优化版）

    统一并行图结构，节点间大对象通过 LangGraph Store 传递
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
        store=None,
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
        self.reflection_enabled = reflection_enabled and critic_agent is not None
        self._store = store

        self.parallel_executor = ParallelTaskExecutor(
            task_execution_service=task_execution_service,
            event_publisher=event_publisher,
            max_concurrent_tasks=max_concurrent_tasks,
            trace_service=trace_service
        )

        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
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
                "generate_report",
                self._should_reflect,
                {"reflect": "reflect", "end": END}
            )
            workflow.add_conditional_edges(
                "reflect",
                self._should_continue_reflection,
                {"execute": "execute", "generate_report": "generate_report", "end": END}
            )
        else:
            workflow.add_edge("generate_report", END)

        return workflow.compile()

    def _should_reflect(self, state: WorkflowState) -> str:
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
        logger.info(f"[WorkflowParallel] Triggering self-reflection (round 1/1)")
        return "reflect"

    def _should_continue_reflection(self, state: WorkflowState) -> str:
        supplementary_queries = state.get("supplementary_queries", [])
        if supplementary_queries:
            new_tasks = state.get("tasks", [])
            pending = [t for t in new_tasks if t.get("status") == "pending"]
            if pending:
                logger.info(f"[WorkflowParallel] Executing {len(pending)} supplementary tasks")
                return "execute"
        return "generate_report"

    async def _reflect_node(self, state: WorkflowState) -> Dict[str, Any]:
        logger.info(f"[WorkflowParallel] Starting self-reflection for workflow {state['workflow_id']}")
        reflection_round = state.get("reflection_round", 0) + 1
        report_content = state.get("report_content", "")
        topic = state["topic"]
        sub_questions = state.get("sub_questions", [])
        workflow_id = state["workflow_id"]

        if not report_content:
            logger.warning("[WorkflowParallel] No report content for reflection")
            return {
                "reflection_round": reflection_round,
                "updated_at": get_current_utc_time()
            }

        try:
            quality_report = await self._load_from_store(workflow_id, "quality_report")
            if quality_report is None:
                quality_report = await self.critic_agent.execute(
                    topic=topic,
                    report_content=report_content,
                    sub_questions=sub_questions,
                    tasks=state.get("tasks", [])
                )

            supplementary_queries = []
            if self.critic_agent.has_critical_gaps(quality_report):
                supplementary_queries = self.critic_agent.extract_queries(quality_report)

            if supplementary_queries:
                updated_tasks = await self._add_supplementary_tasks(state, supplementary_queries)
                return {
                    "tasks": updated_tasks,
                    "reflection_round": reflection_round,
                    "updated_at": get_current_utc_time()
                }

            return {
                "reflection_round": reflection_round,
                "updated_at": get_current_utc_time()
            }
        except Exception as e:
            logger.error(f"[WorkflowParallel] Reflection failed: {str(e)}")
            return {
                "reflection_round": reflection_round,
                "updated_at": get_current_utc_time()
            }

    async def _add_supplementary_tasks(
        self, state: WorkflowState, supplementary_queries: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        existing_tasks = state.get("tasks", [])
        max_order = max((t.get("order", 0) for t in existing_tasks), default=0)

        new_tasks = []
        for i, sq in enumerate(supplementary_queries):
            task_id = str(uuid.uuid4())
            order = max_order + 100 + i
            new_tasks.append({
                "task_id": task_id,
                "title": sq.get("title", "Supplementary Research"),
                "intent": sq.get("intent", ""),
                "query": sq.get("query", ""),
                "order": order,
                "depends_on": [],
                "status": "pending"
            })

            task_entity = Task(
                task_id=task_id,
                workflow_id=state["workflow_id"],
                title=sq.get("title", "Supplementary"),
                intent=sq.get("intent", ""),
                query=sq.get("query", ""),
                order=order,
                depends_on=[]
            )
            try:
                await self.task_repository.save(task_entity)
            except Exception as e:
                logger.error(f"[WorkflowParallel] Failed to save supplementary task {task_id}: {e}")

        logger.info(f"[WorkflowParallel] Added {len(new_tasks)} supplementary tasks")
        return existing_tasks + new_tasks

    def _calculate_optimal_concurrency(self, task_count: int) -> int:
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

    async def _execute_node(self, state: WorkflowState) -> Dict[str, Any]:
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
                "updated_at": get_current_utc_time()
            }

        await self._save_to_store(workflow_id, "execute_duration_ms", execute_duration_ms)
        await self._save_to_store(workflow_id, "task_results", result.get("task_results", []))

        await self._save_to_store(workflow_id, "retrieved_chunks", result.get("retrieved_chunks", []))
        await self._save_to_store(workflow_id, "retrieved_documents", result.get("retrieved_documents", []))
        await self._save_to_store(workflow_id, "accumulated_knowledge", result.get("accumulated_knowledge", []))

        logger.info(
            f"[WorkflowParallel] Execute phase completed: {execute_duration_ms}ms "
            f"({len(task_dicts)} tasks)"
        )

        return {
            "tasks": result["tasks"],
            "updated_at": get_current_utc_time()
        }

    async def _execute_tasks_parallel(self, state: WorkflowState, task_dicts: List[Dict[str, Any]], workflow_id: str) -> Dict[str, Any]:
        pending_dicts = [t for t in task_dicts if t.get("status") == "pending"]
        tasks = self._build_task_entities(pending_dicts, workflow_id)

        optimal_concurrency = self._calculate_optimal_concurrency(len(tasks))
        if optimal_concurrency != self.max_concurrent_tasks:
            logger.info(f"[WorkflowParallel] Adjusting concurrency from {self.max_concurrent_tasks} to {optimal_concurrency}")
            self.parallel_executor.max_concurrent_tasks = optimal_concurrency
            self.parallel_executor.semaphore = asyncio.Semaphore(optimal_concurrency)

        trace_context = get_trace_context()

        try:
            task_results = await self.parallel_executor.execute_tasks_parallel(tasks, trace_context=trace_context)
            return await self._process_execution_results(task_dicts, task_results, workflow_id)
        except Exception as e:
            logger.error(f"[WorkflowParallel] Parallel task execution failed: {str(e)}")
            await self.event_publisher.publish_error_event(
                workflow_id=workflow_id,
                message=f"Parallel execution failed: {str(e)}"
            )
            return {
                "error": str(e),
                "tasks": task_dicts,
                "updated_at": get_current_utc_time()
            }

    def _build_task_entities(self, task_dicts: List[Dict[str, Any]], workflow_id: str) -> List[Task]:
        return [
            Task(
                task_id=task_dict["task_id"],
                workflow_id=workflow_id,
                title=task_dict["title"],
                intent=task_dict["intent"],
                query=task_dict["query"],
                order=task_dict["order"]
            )
            for task_dict in task_dicts
        ]

    async def _process_execution_results(self, task_dicts: List[Dict[str, Any]], task_results: List[Dict[str, Any]], workflow_id: str) -> Dict[str, Any]:
        updated_tasks = task_dicts.copy()

        for result in task_results:
            for i, task_dict in enumerate(updated_tasks):
                if task_dict["task_id"] == result["task_id"]:
                    updated_tasks[i]["status"] = result["status"]
                    break

        retrieved_chunks = []
        retrieved_documents = []
        accumulated_knowledge = []
        for result in task_results:
            if result.get("sources_summary"):
                retrieved_chunks.append(result["sources_summary"])
                retrieved_documents.append({
                    "content": result["sources_summary"],
                    "title": result["title"],
                    "task_id": result["task_id"]
                })
            if result.get("status") == "completed" and result.get("summary"):
                key_finding = result["summary"][:150].strip()
                if key_finding:
                    accumulated_knowledge.append(f"[{result['title']}] {key_finding}")

        try:
            await self._update_tasks_batch(workflow_id, task_results)
        except Exception as db_error:
            logger.error(f"[WorkflowParallel] Failed to update tasks in database: {db_error}")

        logger.info(f"[WorkflowParallel] Task execution complete")

        return {
            "tasks": updated_tasks,
            "task_results": task_results,
            "retrieved_chunks": retrieved_chunks,
            "retrieved_documents": retrieved_documents,
            "accumulated_knowledge": accumulated_knowledge,
            "updated_at": get_current_utc_time()
        }

    async def _update_tasks_batch(self, workflow_id: str, task_results: List[Dict[str, Any]]):
        try:
            # 先从数据库加载所有需要更新的任务
            tasks_to_update = []
            for result in task_results:
                task = await self.task_repository.find_by_id(result["task_id"])
                if task:
                    # 设置 started_at（使用任务执行时记录的时间）
                    if result.get("started_at") and not task.started_at:
                        task.started_at = result["started_at"]
                        task.status = "running"  # 确保状态正确
                        task.updated_at = get_current_utc_time()
                    
                    # 处理完成/失败状态
                    if result["status"] == "completed":
                        task.complete(result["summary"], result["sources_summary"], result["notices"])
                    else:
                        task.fail(result.get("error", "Unknown error"))
                    
                    tasks_to_update.append(task)
            
            # 批量更新所有任务（一个事务）
            if tasks_to_update:
                await self.task_repository.update_batch(tasks_to_update)
                logger.info(f"[WorkflowParallel] Batch updated {len(tasks_to_update)} tasks in database")
        except Exception as e:
            logger.error(f"[WorkflowParallel] Batch update failed: {str(e)}")
            raise

    async def _plan_node(self, state: WorkflowState) -> Dict[str, Any]:
        logger.info(f"[WorkflowParallel] Executing plan node for workflow {state['workflow_id']}")

        try:
            workflow_id = state["workflow_id"]
            topic = state["topic"]
            description = ""  # description 从 DB 表读取，不入 checkpoint

            tasks = await self.research_plan_service.generate_tasks(
                workflow_id=workflow_id,
                topic=topic,
                description=description
            )

            task_dicts = [
                {
                    "task_id": task.task_id,
                    "title": task.title,
                    "intent": task.intent,
                    "query": task.query,
                    "order": task.order,
                    "depends_on": task.depends_on,
                    "status": "pending"
                }
                for task in tasks
            ]

            try:
                await self.task_repository.save_batch(tasks)
                logger.info(f"[WorkflowParallel] Saved {len(tasks)} tasks to database")
            except Exception as db_error:
                logger.error(f"[WorkflowParallel] Failed to save tasks to database: {db_error}")

            await self.event_publisher.publish_plan_event(
                workflow_id=state["workflow_id"],
                tasks=task_dicts
            )

            sub_questions = [task.title for task in tasks]

            logger.info(f"[WorkflowParallel] Plan generated with {len(task_dicts)} tasks")
            return {
                "tasks": task_dicts,
                "sub_questions": sub_questions,
                "updated_at": get_current_utc_time()
            }
        except Exception as e:
            logger.error(f"[WorkflowParallel] Plan node failed: {str(e)}")
            await self.event_publisher.publish_error_event(
                workflow_id=state["workflow_id"],
                message=str(e)
            )
            return {
                "error": str(e),
                "updated_at": get_current_utc_time()
            }

    async def _generate_report_node(self, state: WorkflowState) -> Dict[str, Any]:
        logger.info(f"[WorkflowParallel] Generating report for workflow {state['workflow_id']}")
        workflow_id = state["workflow_id"]

        tasks = state.get("tasks", [])
        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t.get("status") == "completed")
        failed_tasks = sum(1 for t in tasks if t.get("status") == "failed")

        logger.info(f"[WorkflowParallel] Task summary: {completed_tasks}/{total_tasks} completed, {failed_tasks} failed")

        task_summary = {
            "total": total_tasks,
            "completed": completed_tasks,
            "failed": failed_tasks
        }

        original_task_count = sum(1 for t in tasks if t.get("order", 0) < 100)
        completion_rate = completed_tasks / max(original_task_count, 1)

        if completion_rate <= 0.5:
            logger.warning(f"[WorkflowParallel] Completion rate {completion_rate:.1%} <= 50%")
            return {
                "report_content": None,
                "report_url": None,
                "workflow_status": "all_failed" if failed_tasks == total_tasks else "partial_failed",
                "task_summary": task_summary,
                "updated_at": get_current_utc_time()
            }

        task_results = await self._load_from_store(workflow_id, "task_results")
        retrieved_chunks = await self._load_from_store(workflow_id, "retrieved_chunks") or []
        retrieved_documents = await self._load_from_store(workflow_id, "retrieved_documents") or []

        if task_results is None:
            logger.info(f"[WorkflowParallel] Store miss for task_results, falling back to DB")
            task_results = await self._load_task_results_from_db(workflow_id)
            # _load_task_results_from_db 内部已 commit，事务已关闭
            # 后续 LLM 调用不会持有 DB 事务，防止 idle-in-transaction 超时

        sub_questions = state.get("sub_questions", [])

        report_generated = False
        report_content = None
        report_url = None
        report_error = None
        evaluation_id = None

        try:
            logger.info(f"[WorkflowParallel] Starting report generation")

            task_results_map = {
                result["task_id"]: result
                for result in (task_results or [])
            }

            task_entities = []
            for task_dict in state["tasks"]:
                task = Task(
                    task_id=task_dict["task_id"],
                    workflow_id=workflow_id,
                    title=task_dict["title"],
                    intent=task_dict["intent"],
                    query=task_dict["query"],
                    order=task_dict["order"]
                )
                if task_dict["task_id"] in task_results_map:
                    result = task_results_map[task_dict["task_id"]]
                    task.summary = result.get("summary")
                    task.sources_summary = result.get("sources_summary")
                    task.notices = result.get("notices")
                task_entities.append(task)

            report = await self.report_generation_service.generate_report(
                workflow_id=workflow_id,
                topic=state["topic"],
                tasks=task_entities
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
                    content_type="text/markdown"
                )
            except Exception as storage_error:
                logger.error(f"[WorkflowParallel] Failed to save report: {storage_error}")
                report_url = f"/reports/{state['workflow_id']}"

            await self.event_publisher.publish_result_event(
                workflow_id=state["workflow_id"],
                report_url=report_url
            )

            if report_generated:
                try:
                    scenario_id = state.get("scenario_id", "dev_survey_v1")
                    evaluation = await self.evaluation_service.create_evaluation(workflow_id, scenario_id)
                    evaluation_id = evaluation.evaluation_id
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
                            evaluation_orchestrator=self.evaluation_orchestrator
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
                            content_type="text/markdown"
                        )
                        await self.event_publisher.publish_result_event(
                            workflow_id=state["workflow_id"],
                            report_url=report_url
                        )
                    except Exception as storage_error:
                        logger.error(f"[WorkflowParallel] Failed to save minimal report: {storage_error}")
            except Exception as fallback_error:
                logger.error(f"[WorkflowParallel] Minimal report failed: {fallback_error}")
            await self.event_publisher.publish_error_event(
                workflow_id=state["workflow_id"],
                message=f"Report generation failed: {report_error}"
            )

        if report_generated:
            workflow_status = "all_success" if completed_tasks == original_task_count else "partial_failed"
        else:
            workflow_status = "report_failed" if completed_tasks == original_task_count else "partial_failed"

        quality_report = None
        if self.reflection_enabled and report_generated and report_content:
            try:
                quality_report = await self.critic_agent.execute(
                    topic=state["topic"],
                    report_content=report_content,
                    sub_questions=state.get("sub_questions", []),
                    tasks=state.get("tasks", [])
                )
                await self._save_to_store(workflow_id, "quality_report", quality_report)
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
            "updated_at": get_current_utc_time()
        }
        if report_error:
            result["error"] = report_error

        return result

    async def _generate_minimal_report(self, state: WorkflowState) -> str:
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

    async def _load_task_results_from_db(self, workflow_id: str) -> List[Dict[str, Any]]:
        try:
            tasks = await self.task_repository.find_by_workflow_id(workflow_id)
            results = []
            for task in tasks:
                status = task.status.value if hasattr(task.status, 'value') else str(task.status)
                results.append({
                    "task_id": task.task_id,
                    "title": task.title,
                    "status": status if status == "completed" else "failed" if status == "failed" else "pending",
                    "summary": task.summary,
                    "sources_summary": task.sources_summary,
                    "notices": task.notices,
                })
            logger.info(f"[WorkflowParallel] Loaded {len(results)} task results from DB")
            return results
        except Exception as e:
            logger.error(f"[WorkflowParallel] Failed to load task results from DB: {e}")
            return []

    async def _save_to_store(self, workflow_id: str, key: str, value: Any) -> None:
        if self._store is None:
            return
        try:
            await self._store.aput(
                (workflow_id, _STORE_INTERMEDIATE),
                key,
                value,
            )
        except Exception as e:
            logger.warning(f"[WorkflowParallel] Store save failed for {key}: {e}")

    async def _load_from_store(self, workflow_id: str, key: str) -> Optional[Any]:
        if self._store is None:
            return None
        try:
            item = await self._store.aget(
                (workflow_id, _STORE_INTERMEDIATE),
                key
            )
            if item is None:
                return None
            # LangGraph Store 返回 Item 对象，value 通过属性访问
            if hasattr(item, "value"):
                return item.value
            # 兼容 dict 格式（如果某些实现返回 dict）
            if isinstance(item, dict):
                return item.get("value")
            return item
        except Exception as e:
            logger.warning(f"[WorkflowParallel] Store load failed for {key}: {e}")
            return None

    async def cleanup_store(self, workflow_id: str) -> None:
        if self._store is None:
            return
        keys = ["task_results", "retrieved_chunks", "retrieved_documents",
                "accumulated_knowledge", "quality_report", "execute_duration_ms"]
        for key in keys:
            try:
                await self._store.adelete((workflow_id, _STORE_INTERMEDIATE), key)
            except Exception:
                pass

    @property
    def graph(self):
        return self._graph
