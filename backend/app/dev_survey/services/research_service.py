import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Union, Dict, Any
from uuid import UUID
from fastapi import HTTPException

from app.dev_survey.models.dtos import (
    CreateResearchRequest,
    WorkflowResponse,
    TaskResponse,
    ResearchResponse
)
from app.dev_survey.models.models import Workflow
from app.dev_survey.models.enums import WorkflowStatus
from app.dev_survey.events import get_event_publisher
from app.dev_survey.services import (
    ResearchPlanService,
    TaskExecutionService,
    ReportGenerationService,
    EvaluationService
)
from app.dev_survey.repositories import WorkflowRepository, TaskRepository
from app.dev_survey.agents import PlanAgent, SearchAgent, SummarizerAgent, GenerateAgent
from app.dev_survey.agents.critic_agent import CriticAgent
from harness.llm.factory import get_llm_client, remove_llm_client
from harness.source_routing.sources.factory import get_search_source
from harness.storage.local_storage import LocalObjectStorage
from harness.evaluation.orchestrator import EvaluationOrchestrator
from harness.config import get_harness_settings
from harness.logger import logger
from harness.observability.trace_service import get_trace_service, TraceService
from app.common.utils.time_utils import get_current_utc_time
from harness.workflow.saver import CheckpointConnectionError
from langgraph.store.memory import InMemoryStore

settings = get_harness_settings()


def _default_store():
    try:
        from langgraph.store.postgres import AsyncPostgresStore
        store = AsyncPostgresStore.from_conn_string(conn_string=settings.DATABASE_URL)
        logger.info("Using AsyncPostgresStore for workflow intermediate data")
        return store
    except Exception as e:
        logger.warning(f"AsyncPostgresStore unavailable, falling back to InMemoryStore: {e}")
        return InMemoryStore()


class ResearchService:
    """
    调研服务

    采用延迟初始化策略：__init__ 只保存参数，重型组件（Agents、Graph）在首次使用时才创建。
    这样简单的查询操作（如 get_workflow_status）不会触发任何重型初始化。

    每个懒加载 @property 包含三重防护：
    1. try/except — 工厂函数抛出异常时立即 Fail-Fast
    2. if instance is None — 工厂返回 None 时立即 Fail-Fast
    3. 仅当 instance is not None 时才缓存 — 防止污染缓存导致循环重试
    """

    def __init__(
        self,
        workflow_repository: WorkflowRepository,
        task_repository: TaskRepository,
        evaluation_service: EvaluationService,
        evaluation_orchestrator: EvaluationOrchestrator,
        report_url_prefix: str = "/dev-research/reports",
        plan_agent_factory: callable = None,
        search_agent_factory: callable = None,
        summarizer_agent_factory: callable = None,
        generate_agent_factory: callable = None,
        critic_agent_factory: callable = None,
        event_publisher_factory: callable = None,
        object_storage_factory: callable = None,
        trace_service_factory: callable = None,
        store_factory: callable = None,
    ):
        self.workflow_repository = workflow_repository
        self.task_repository = task_repository
        self.evaluation_service = evaluation_service
        self.evaluation_orchestrator = evaluation_orchestrator
        self.report_url_prefix = report_url_prefix

        self._plan_agent_factory = plan_agent_factory or (lambda: PlanAgent(get_llm_client()))
        self._search_agent_factory = search_agent_factory or (lambda: SearchAgent())
        self._summarizer_agent_factory = summarizer_agent_factory or (lambda: SummarizerAgent(get_llm_client()))
        self._generate_agent_factory = generate_agent_factory or (lambda: GenerateAgent(get_llm_client()))
        self._critic_agent_factory = critic_agent_factory or (lambda: CriticAgent(get_llm_client()))
        self._event_publisher_factory = event_publisher_factory or (lambda: get_event_publisher())
        self._object_storage_factory = object_storage_factory or (lambda: LocalObjectStorage(url_prefix=report_url_prefix))
        self._trace_service_factory = trace_service_factory or (lambda: get_trace_service())
        self._store_factory = store_factory or (lambda: _default_store())

        self._plan_agent = None
        self._search_agent = None
        self._summarizer_agent = None
        self._generate_agent = None
        self._critic_agent = None
        self._event_publisher = None
        self._object_storage = None
        self._trace_service = None
        self._store = None
        self._research_plan_service = None
        self._task_execution_service = None
        self._report_generation_service = None
        self._workflow_graph = None
        self._saver_manager = None

    # --- 懒加载属性（均含三重防护） ---

    @property
    def plan_agent(self) -> PlanAgent:
        if self._plan_agent is None:
            try:
                instance = self._plan_agent_factory()
            except Exception as e:
                logger.error(f"[ResearchService] Failed to create PlanAgent: {e}", exc_info=True)
                raise RuntimeError(f"Failed to initialize PlanAgent via factory. Underlying error: {e}") from e
            if instance is None:
                raise RuntimeError("PlanAgent factory returned None. This indicates a programming error.")
            self._plan_agent = instance
        return self._plan_agent

    @property
    def search_agent(self) -> SearchAgent:
        if self._search_agent is None:
            try:
                instance = self._search_agent_factory()
            except Exception as e:
                logger.error(f"[ResearchService] Failed to create SearchAgent: {e}", exc_info=True)
                raise RuntimeError(f"Failed to initialize SearchAgent via factory. Underlying error: {e}") from e
            if instance is None:
                raise RuntimeError("SearchAgent factory returned None. This indicates a programming error.")
            self._search_agent = instance
        return self._search_agent

    @property
    def summarizer_agent(self) -> SummarizerAgent:
        if self._summarizer_agent is None:
            try:
                instance = self._summarizer_agent_factory()
            except Exception as e:
                logger.error(f"[ResearchService] Failed to create SummarizerAgent: {e}", exc_info=True)
                raise RuntimeError(f"Failed to initialize SummarizerAgent via factory. Underlying error: {e}") from e
            if instance is None:
                raise RuntimeError("SummarizerAgent factory returned None. This indicates a programming error.")
            self._summarizer_agent = instance
        return self._summarizer_agent

    @property
    def generate_agent(self) -> GenerateAgent:
        if self._generate_agent is None:
            try:
                instance = self._generate_agent_factory()
            except Exception as e:
                logger.error(f"[ResearchService] Failed to create GenerateAgent: {e}", exc_info=True)
                raise RuntimeError(f"Failed to initialize GenerateAgent via factory. Underlying error: {e}") from e
            if instance is None:
                raise RuntimeError("GenerateAgent factory returned None. This indicates a programming error.")
            self._generate_agent = instance
        return self._generate_agent

    @property
    def critic_agent(self) -> CriticAgent:
        if self._critic_agent is None:
            try:
                instance = self._critic_agent_factory()
            except Exception as e:
                logger.error(f"[ResearchService] Failed to create CriticAgent: {e}", exc_info=True)
                raise RuntimeError(f"Failed to initialize CriticAgent via factory. Underlying error: {e}") from e
            if instance is None:
                raise RuntimeError("CriticAgent factory returned None. This indicates a programming error.")
            self._critic_agent = instance
        return self._critic_agent

    @property
    def event_publisher(self):
        if self._event_publisher is None:
            try:
                instance = self._event_publisher_factory()
            except Exception as e:
                logger.error(f"[ResearchService] Failed to create EventPublisher: {e}", exc_info=True)
                raise RuntimeError(f"Failed to initialize EventPublisher via factory. Underlying error: {e}") from e
            if instance is None:
                raise RuntimeError("EventPublisher factory returned None. This indicates a programming error.")
            self._event_publisher = instance
        return self._event_publisher

    @property
    def object_storage(self):
        if self._object_storage is None:
            try:
                instance = self._object_storage_factory()
            except Exception as e:
                logger.error(f"[ResearchService] Failed to create ObjectStorage: {e}", exc_info=True)
                raise RuntimeError(f"Failed to initialize ObjectStorage via factory. Underlying error: {e}") from e
            if instance is None:
                raise RuntimeError("ObjectStorage factory returned None. This indicates a programming error.")
            self._object_storage = instance
        return self._object_storage

    @property
    def trace_service(self) -> TraceService:
        if self._trace_service is None:
            try:
                instance = self._trace_service_factory()
            except Exception as e:
                logger.error(f"[ResearchService] Failed to create TraceService: {e}", exc_info=True)
                raise RuntimeError(f"Failed to initialize TraceService via factory. Underlying error: {e}") from e
            if instance is None:
                raise RuntimeError("TraceService factory returned None. This indicates a programming error.")
            self._trace_service = instance
        return self._trace_service

    @property
    def store(self):
        if self._store is None:
            try:
                instance = self._store_factory()
            except Exception as e:
                logger.error(f"[ResearchService] Failed to create Store: {e}", exc_info=True)
                raise RuntimeError(f"Failed to initialize Store via factory. Underlying error: {e}") from e
            if instance is None:
                raise RuntimeError("Store factory returned None. This indicates a programming error.")
            self._store = instance
        return self._store

    @property
    def research_plan_service(self) -> ResearchPlanService:
        if self._research_plan_service is None:
            self._research_plan_service = ResearchPlanService(self.plan_agent)
        return self._research_plan_service

    @property
    def task_execution_service(self) -> TaskExecutionService:
        if self._task_execution_service is None:
            self._task_execution_service = TaskExecutionService(self.search_agent, self.summarizer_agent)
        return self._task_execution_service

    @property
    def report_generation_service(self) -> ReportGenerationService:
        if self._report_generation_service is None:
            self._report_generation_service = ReportGenerationService(self.generate_agent)
        return self._report_generation_service

    @property
    def workflow_graph(self):
        if self._workflow_graph is None:
            from app.dev_survey.workflow import ResearchWorkflowGraphParallel
            self._workflow_graph = ResearchWorkflowGraphParallel(
                research_plan_service=self.research_plan_service,
                task_execution_service=self.task_execution_service,
                report_generation_service=self.report_generation_service,
                event_publisher=self.event_publisher,
                task_repository=self.task_repository,
                object_storage=self.object_storage,
                evaluation_service=self.evaluation_service,
                evaluation_orchestrator=self.evaluation_orchestrator,
                trace_service=self.trace_service,
                critic_agent=self.critic_agent,
                reflection_enabled=settings.ENABLE_REFLECTION,
                store=self.store,
            )
        return self._workflow_graph

    @property
    def saver_manager(self):
        if self._saver_manager is None:
            from harness.workflow import get_saver_manager
            self._saver_manager = get_saver_manager()
            logger.info("Using AsyncPostgresSaverManager for workflow state persistence")
        return self._saver_manager

    async def cleanup(self):
        self._plan_agent = None
        self._search_agent = None
        self._summarizer_agent = None
        self._generate_agent = None
        self._critic_agent = None
        self._event_publisher = None
        self._object_storage = None
        self._trace_service = None
        self._store = None
        self._research_plan_service = None
        self._task_execution_service = None
        self._report_generation_service = None
        self._workflow_graph = None
        self._saver_manager = None
        await remove_llm_client()
        logger.info("[ResearchService] Service cleaned up, LLM client cache removed")

    # --- 业务方法 ---

    async def create_research_workflow(self, request: CreateResearchRequest) -> WorkflowResponse:
        logger.info(f"[ResearchService] Creating research workflow for topic: {request.topic}")

        workflow_id = str(uuid.uuid4())
        trace_id = await self.trace_service.start_workflow_trace(
            workflow_id=workflow_id,
            scenario_id=request.scenario_id or "dev_survey",
            topic=request.topic,
            description=request.description,
        )

        workflow = Workflow(
            workflow_id=workflow_id,
            topic=request.topic,
            scenario_id=request.scenario_id or "dev_survey",
            description=request.description,
            status=WorkflowStatus.PENDING.value
        )

        try:
            await self.workflow_repository.save(workflow)
        except Exception as db_error:
            logger.error(f"[ResearchService] Failed to save workflow to database: {db_error}, but continuing with in-memory workflow")

        logger.info(f"[ResearchService] Workflow created: {workflow_id}, trace_id: {trace_id}")
        return self._to_workflow_response(workflow)

    async def execute_research_workflow(self, workflow_id: Union[str, UUID]) -> None:
        workflow_id_str = str(workflow_id)

        try:
            restored_trace_id = await self.trace_service.restore_trace_context(workflow_id_str)
            if restored_trace_id:
                logger.info(f"[ResearchService] Restored trace context: {restored_trace_id}")
        except Exception as ctx_error:
            logger.warning(f"[ResearchService] Failed to restore trace context: {ctx_error}")

        logger.info(f"[ResearchService] Executing research workflow: {workflow_id_str}")

        workflow = await self.workflow_repository.find_by_id(workflow_id_str)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id_str}")

        workflow.start()
        try:
            await self.workflow_repository.update(workflow)
        except Exception as db_error:
            logger.error(f"[ResearchService] Failed to update workflow to database: {db_error}, but continuing with execution")

        from app.dev_survey.workflow import WorkflowState
        initial_state: WorkflowState = {
            "workflow_id": workflow_id_str,
            "topic": workflow.topic,
            "scenario_id": workflow.scenario_id,
            "tasks": [],
            "report_content": None,
            "report_url": None,
            "error": None,
            "created_at": workflow.created_at,
            "updated_at": get_current_utc_time(),
        }

        config = {
            "configurable": {
                "thread_id": workflow_id_str
            }
        }

        try:
            checkpointer = await self.saver_manager.get_saver(thread_id=workflow_id_str)

            await self.workflow_graph.graph.ainvoke(
                initial_state,
                config=config,
                checkpointer=checkpointer
            )

            final_state = await self._get_final_state(config, workflow, workflow_id_str)
            logger.info(f"[ResearchService] Final state: {final_state}")

            await self._update_workflow_state(workflow, final_state, workflow_id_str)
            await self._force_update_workflow_to_database(workflow)

            workflow_status = workflow.status.value if hasattr(workflow.status, 'value') else str(workflow.status)

            item = await self.workflow_graph._load_from_store(workflow_id_str, "execute_duration_ms")
            execute_duration_ms = item if item else None

            await self.trace_service.complete_workflow_trace(
                workflow_id=workflow_id_str,
                status=workflow_status,
                report_url=workflow.report_url,
                execute_duration_ms=execute_duration_ms,
            )

            await self.workflow_graph.cleanup_store(workflow_id_str)

            logger.info(f"[ResearchService] Workflow execution completed: {workflow_id}")
        except CheckpointConnectionError as e:
            logger.error(
                f"[ResearchService] Checkpoint connection failed | "
                f"workflow_id={workflow_id_str} | "
                f"error={e.message} | "
                f"retries={e.retry_count}",
                exc_info=True
            )
            workflow.mark_all_failed()
            try:
                await self.workflow_repository.update(workflow)
            except Exception as db_error:
                logger.error(f"[ResearchService] Failed to update workflow in database after checkpoint error: {db_error}")
            await self.event_publisher.publish_error_event(
                workflow_id=workflow_id,
                message="工作流状态存储不可用，请稍后重试"
            )
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "CHECKPOINT_CONNECTION_ERROR",
                    "message": "无法访问工作流状态存储，请稍后重试",
                    "workflow_id": workflow_id_str
                }
            ) from e
        except Exception as e:
            logger.error(f"[ResearchService] Workflow execution failed: {str(e)}")
            workflow.mark_all_failed()
            try:
                await self.workflow_repository.update(workflow)
            except Exception as db_error:
                logger.error(f"[ResearchService] Failed to update workflow in database after failure: {db_error}")
            await self.event_publisher.publish_error_event(
                workflow_id=workflow_id,
                message=str(e)
            )
            raise

    async def _get_final_state(self, config, workflow, workflow_id_str) -> Optional[Dict[str, Any]]:
        max_retries = 2
        for retry in range(max_retries):
            try:
                checkpointer = await self.saver_manager.get_saver()

                from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
                if isinstance(checkpointer, AsyncPostgresSaver):
                    checkpoint_tuple = await checkpointer.aget_tuple(config)
                    if checkpoint_tuple and checkpoint_tuple.checkpoint:
                        final_state = checkpoint_tuple.checkpoint.get("channel_values", {})
                        if final_state:
                            logger.info(f"[ResearchService] Got final state from AsyncPostgresSaver checkpoint (retry={retry})")
                            return final_state
                else:
                    final_state = checkpointer.get(config)
                    if final_state:
                        logger.info(f"[ResearchService] Got final state from InMemorySaver checkpoint (retry={retry})")
                        return final_state

                break
            except Exception as e:
                if retry < max_retries - 1:
                    logger.warning(f"[ResearchService] Failed to get state from checkpoint (retry={retry}): {e}, retrying...")
                    if hasattr(self.saver_manager, '_close_saver'):
                        await self.saver_manager._close_saver()
                else:
                    logger.warning(f"[ResearchService] Failed to get state from checkpoint after {max_retries} retries: {e}")

        logger.warning(f"[ResearchService] No state from checkpoint, calculating from database")
        return await self._calculate_state_from_database(workflow_id_str)

    async def _calculate_state_from_database(self, workflow_id_str: str) -> Optional[Dict[str, Any]]:
        try:
            tasks = await self.task_repository.find_by_workflow_id(workflow_id_str)
            completed_count = sum(1 for task in tasks if (task.status.value if hasattr(task.status, 'value') else task.status) == "completed")
            failed_count = sum(1 for task in tasks if (task.status.value if hasattr(task.status, 'value') else task.status) == "failed")
            total_count = len(tasks)

            logger.info(f"[ResearchService] Tasks: {completed_count}/{total_count} completed, {failed_count} failed from database")

            report_url = None
            try:
                report_url = await self.object_storage.get_report_url_by_workflow_id(workflow_id_str)
                if report_url:
                    logger.info(f"[ResearchService] Found report URL from storage: {report_url}")
            except Exception as storage_error:
                logger.warning(f"[ResearchService] Failed to get report URL from storage: {storage_error}")

            workflow_status = None
            has_report = report_url is not None

            task_summary = {
                "total": total_count,
                "completed": completed_count,
                "failed": failed_count
            }

            if total_count == 0 or failed_count == total_count:
                workflow_status = "all_failed"
            elif has_report:
                if completed_count == total_count:
                    workflow_status = "all_success"
                else:
                    workflow_status = "partial_failed"
            else:
                if completed_count == total_count:
                    workflow_status = "report_failed"
                else:
                    workflow_status = "partial_failed"

            logger.info(f"[ResearchService] Calculated workflow_status: {workflow_status}")

            state = {
                "workflow_status": workflow_status,
                "task_summary": task_summary,
                "report_url": report_url,
                "error": None,
                "tasks": tasks
            }

            return state
        except Exception as e:
            logger.error(f"[ResearchService] Failed to calculate state from database: {e}")
            return None

    async def _update_workflow_state(self, workflow: Workflow, final_state: Optional[Dict[str, Any]], workflow_id_str: str):
        if final_state:
            workflow_status = final_state.get("workflow_status")
            task_summary = final_state.get("task_summary", {})
            report_url = final_state.get("report_url")
            error = final_state.get("error")

            logger.info(f"[ResearchService] Workflow status from state: {workflow_status}")
            logger.info(f"[ResearchService] Task summary: {task_summary}")
            logger.info(f"[ResearchService] Report URL: {report_url}")
            logger.info(f"[ResearchService] Error: {error}")

            if workflow_status:
                if workflow_status == "all_success":
                    workflow.mark_all_success(report_url)
                    logger.info(f"[ResearchService] Workflow {workflow_id_str} marked as ALL_SUCCESS")

                elif workflow_status == "partial_failed":
                    workflow.mark_partial_failed(report_url)
                    logger.info(f"[ResearchService] Workflow {workflow_id_str} marked as PARTIAL_FAILED")

                elif workflow_status == "all_failed":
                    workflow.mark_all_failed()
                    logger.info(f"[ResearchService] Workflow {workflow_id_str} marked as ALL_FAILED")

                elif workflow_status == "report_failed":
                    workflow.mark_report_failed()
                    logger.info(f"[ResearchService] Workflow {workflow_id_str} marked as REPORT_FAILED")

                else:
                    logger.warning(f"[ResearchService] Unknown workflow status: {workflow_status}, using fallback logic")
                    self._update_workflow_fallback(workflow, final_state, workflow_id_str)
            else:
                logger.warning("[ResearchService] No workflow_status in final state, using fallback logic")
                self._update_workflow_fallback(workflow, final_state, workflow_id_str)
        else:
            logger.warning("[ResearchService] No final state available, checking database tasks")
            await self._update_workflow_from_database(workflow, workflow_id_str)

    def _update_workflow_fallback(self, workflow: Workflow, final_state: Dict[str, Any], workflow_id_str: str):
        report_url = final_state.get("report_url")
        error = final_state.get("error")

        if report_url:
            workflow.mark_all_success(report_url)
        elif error:
            workflow.mark_all_failed()
        else:
            tasks = final_state.get("tasks", [])
            completed_count = 0
            failed_count = 0
            total_count = len(tasks)

            for t in tasks:
                if hasattr(t, 'status'):
                    status_value = t.status.value if hasattr(t.status, 'value') else str(t.status)
                elif isinstance(t, dict):
                    status_value = t.get("status", "")
                else:
                    continue

                if status_value == "completed":
                    completed_count += 1
                elif status_value == "failed":
                    failed_count += 1

            if completed_count > 0 and completed_count == total_count:
                workflow.mark_all_success(f"/reports/{workflow_id_str}")
            elif failed_count > 0 and completed_count == 0:
                workflow.mark_all_failed()
            elif completed_count > 0 and failed_count > 0:
                workflow.mark_partial_failed(f"/reports/{workflow_id_str}")
            elif total_count == 0:
                workflow.mark_all_failed()
            else:
                logger.warning(f"[ResearchService] Workflow still in progress")

    async def _force_update_workflow_to_database(self, workflow: Workflow):
        try:
            await self.workflow_repository.update(workflow)
            logger.info(f"[ResearchService] Workflow force updated - status: {workflow.status}, completed_at: {workflow.completed_at}")
        except Exception as db_error:
            logger.error(f"[ResearchService] Failed to force update workflow in database: {db_error}")

    async def get_workflow_status(self, workflow_id: Union[str, UUID]) -> ResearchResponse:
        """获取工作流状态 — 纯查询操作，不触发任何重型组件初始化"""
        workflow_id_str = str(workflow_id)

        workflow = await self.workflow_repository.find_by_id(workflow_id_str)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id_str}")

        return self._to_research_response(workflow)

    async def _update_workflow_from_database(self, workflow: Workflow, workflow_id_str: str) -> None:
        try:
            db_workflow = await self.workflow_repository.find_by_id(workflow_id_str)
            if not db_workflow:
                logger.warning(f"[ResearchService] Workflow not found in database: {workflow_id_str}")
                return

            status_value = db_workflow.status.value if hasattr(db_workflow.status, 'value') else db_workflow.status

            if status_value == "completed":
                logger.info(f"[ResearchService] Workflow already completed in database")
                workflow.status = db_workflow.status
                workflow.report_url = db_workflow.report_url
                workflow.completed_at = db_workflow.completed_at
            elif status_value == "failed":
                logger.info(f"[ResearchService] Workflow already failed in database")
                workflow.status = db_workflow.status
            else:
                logger.warning(f"[ResearchService] Workflow status in database is still '{status_value}', checking tasks for completion")
                tasks = await self.task_repository.find_by_workflow_id(workflow_id_str)
                completed_count = sum(1 for task in tasks if (task.status.value if hasattr(task.status, 'value') else task.status) == "completed")
                total_count = len(tasks)

                logger.info(f"[ResearchService] Tasks: {completed_count}/{total_count} completed")

                if completed_count > 0 and completed_count == total_count:
                    workflow.mark_all_success(f"/reports/{workflow_id_str}")
                    logger.info(f"[ResearchService] Workflow marked as completed based on task completion")
                elif completed_count == 0 and total_count == 0:
                    workflow.mark_all_failed()
                    logger.warning(f"[ResearchService] No tasks found, marking workflow as failed")
                else:
                    logger.warning(f"[ResearchService] Workflow still in progress: {completed_count}/{total_count} tasks completed")

            await self.workflow_repository.update(workflow)
            logger.info(f"[ResearchService] Workflow updated from database - status: {workflow.status}")
        except Exception as e:
            logger.error(f"[ResearchService] Failed to update workflow from database: {e}")

    def _to_workflow_response(self, workflow: Workflow) -> WorkflowResponse:
        task_responses = [
            self._to_task_response(task)
            for task in workflow.tasks
        ]

        # 确保状态字段转换为字符串
        status_value = workflow.status.value if hasattr(workflow.status, 'value') else str(workflow.status)

        return WorkflowResponse(
            workflow_id=workflow.workflow_id,
            topic=workflow.topic,
            scenario_id=workflow.scenario_id,
            description=workflow.description,
            status=status_value,
            report_url=workflow.report_url,
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
            started_at=workflow.started_at,
            completed_at=workflow.completed_at,
            tasks=task_responses
        )

    def _to_research_response(self, workflow: Workflow) -> ResearchResponse:
        # 确保状态字段转换为字符串
        status_value = workflow.status.value if hasattr(workflow.status, 'value') else str(workflow.status)

        return ResearchResponse(
            workflow_id=workflow.workflow_id,
            topic=workflow.topic,
            scenario_id=workflow.scenario_id,
            description=workflow.description,
            status=status_value,
            report_url=workflow.report_url,
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
            started_at=workflow.started_at,
            completed_at=workflow.completed_at,
            tasks=[self._to_task_response(task) for task in workflow.tasks]
        )

    def _to_task_response(self, task) -> TaskResponse:
        return TaskResponse(
            task_id=task.task_id,
            title=task.title,
            intent=task.intent,
            query=task.query,
            order=task.order,
            status=task.status.value if hasattr(task.status, 'value') else task.status,
            summary=task.summary,
            sources_summary=task.sources_summary,
            notices=task.notices,
            created_at=task.created_at,
            updated_at=task.updated_at,
            started_at=task.started_at,
            completed_at=task.completed_at
        )

    def get_report_file_path(self, report_id: str) -> Optional[Path]:
        reports_path = Path(settings.REPORT_STORAGE_PATH)
        file_path = reports_path / report_id

        safe_file_path = file_path.resolve()
        if not safe_file_path.is_relative_to(reports_path.resolve()):
            logger.warning(f"Invalid report ID, potential path traversal attack: {report_id}")
            return None

        if not safe_file_path.exists():
            logger.warning(f"Report not found: {report_id}")
            return None

        logger.info(f"Report file path resolved: {safe_file_path}")
        return safe_file_path

    async def get_report_content(self, workflow_id: Union[str, UUID]) -> Optional[str]:
        """获取报告内容 — 只需要 object_storage，首次访问时才会初始化"""
        workflow_id_str = str(workflow_id)
        logger.info(f"[ResearchService] Getting report content for workflow: {workflow_id_str}")

        workflow = await self.workflow_repository.find_by_id(workflow_id_str)

        if not workflow or not workflow.report_url:
            logger.warning(f"[ResearchService] Workflow or report_url not found: {workflow_id_str}")
            return None

        try:
            report_id = workflow.report_url.split("/")[-1]

            logger.info(f"[ResearchService] Reading report file: {report_id}")
            content = await self.object_storage.read_file(report_id)
            return content
        except Exception as e:
            logger.error(f"[ResearchService] Failed to read report content: {e}")
            return None
