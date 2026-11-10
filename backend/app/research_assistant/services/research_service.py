import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import HTTPException

from app.common.utils.time_utils import get_current_utc_time
from app.research_assistant.agents import GenerateAgent, PlanAgent, SearchAgent, SummarizerAgent
from app.research_assistant.events import get_event_publisher
from app.research_assistant.models.dtos import (
    CreateResearchRequest,
    ResearchResponse,
    TaskResponse,
    WorkflowResponse,
)
from app.research_assistant.models.enums import WorkflowStatus
from app.research_assistant.models.models import Workflow
from app.research_assistant.repositories import TaskRepository, WorkflowRepository
from app.research_assistant.services.evaluation_service import EvaluationService
from app.research_assistant.services.report_generation_service import ReportGenerationService
from app.research_assistant.services.research_plan_service import ResearchPlanService
from app.research_assistant.services.task_execution_service import TaskExecutionService
from harness.config import get_harness_settings
from harness.evaluation.orchestrator import EvaluationOrchestrator
from harness.llm.factory import get_llm_client, remove_llm_client
from harness.logger import logger
from harness.source_routing.sources.factory import get_search_source
from harness.storage.local_storage import LocalObjectStorage
from harness.workflow.saver import CheckpointConnectionError

settings = get_harness_settings()


class ResearchService:
    def __init__(
        self,
        workflow_repository: WorkflowRepository,
        task_repository: TaskRepository,
        evaluation_service: EvaluationService,
        evaluation_orchestrator: EvaluationOrchestrator,
        report_url_prefix: str = "/research/reports",
    ):
        self.workflow_repository = workflow_repository
        self.task_repository = task_repository

        llm_client = get_llm_client()
        search_source = get_search_source()

        plan_agent = PlanAgent(llm_client)
        search_agent = SearchAgent(search_source)
        summarizer_agent = SummarizerAgent(llm_client)
        generate_agent = GenerateAgent(llm_client)

        self.research_plan_service = ResearchPlanService(plan_agent)
        self.task_execution_service = TaskExecutionService(search_agent, summarizer_agent)
        self.report_generation_service = ReportGenerationService(generate_agent)
        self.evaluation_service = evaluation_service
        self.evaluation_orchestrator = evaluation_orchestrator

        self.event_publisher = get_event_publisher()
        self.object_storage = LocalObjectStorage(url_prefix=report_url_prefix)

        from harness.workflow import get_saver_manager

        self.saver_manager = get_saver_manager()
        self._workflow_graph = None
        logger.info("Using AsyncPostgresSaverManager for workflow state persistence")

    def _get_workflow_graph(self, checkpointer=None):
        """构造工作流图，执行时传入 checkpointer 以保证 Checkpoint 持久化。"""
        if self._workflow_graph is None:
            from app.research_assistant.workflow import ResearchWorkflowGraph

            self._workflow_graph = ResearchWorkflowGraph(
                research_plan_service=self.research_plan_service,
                task_execution_service=self.task_execution_service,
                report_generation_service=self.report_generation_service,
                event_publisher=self.event_publisher,
                task_repository=self.task_repository,
                object_storage=self.object_storage,
                evaluation_service=self.evaluation_service,
                evaluation_orchestrator=self.evaluation_orchestrator,
                checkpointer=checkpointer,
            )
        return self._workflow_graph

    async def cleanup(self):
        await remove_llm_client()
        logger.info("[ResearchService] LLM client cache removed")

    async def create_research_workflow(self, request: CreateResearchRequest) -> WorkflowResponse:
        logger.info(f"[ResearchService] Creating research workflow for topic: {request.topic}")

        workflow_id = str(uuid.uuid4())
        workflow = Workflow(
            workflow_id=workflow_id,
            topic=request.topic,
            scenario_id=request.scenario_id or "research_assistant_v1",
            description=request.description,
            status=WorkflowStatus.PENDING,
        )

        try:
            await self.workflow_repository.save(workflow)
        except Exception as db_error:
            logger.error(
                f"[ResearchService] Failed to save workflow to database: {db_error}, but continuing with in-memory workflow"
            )

        logger.info(f"[ResearchService] Workflow created: {workflow_id}")
        return self._to_workflow_response(workflow)

    async def execute_research_workflow(self, workflow_id: str | UUID) -> None:
        workflow_id_str = str(workflow_id)
        logger.info(f"[ResearchService] Executing research workflow: {workflow_id_str}")

        workflow = await self.workflow_repository.find_by_id(workflow_id_str)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id_str}")

        workflow.start()
        try:
            await self.workflow_repository.update(workflow)
        except Exception as db_error:
            logger.error(
                f"[ResearchService] Failed to update workflow to database: {db_error}, but continuing with execution"
            )

        from app.research_assistant.workflow import WorkflowState

        initial_state: WorkflowState = {
            "workflow_id": workflow_id_str,
            "topic": workflow.topic,
            "description": workflow.description,
            "scenario_id": workflow.scenario_id,
            "tasks": [],
            "current_task_index": 0,
            "task_results": [],
            "report_content": None,
            "report_url": None,
            "error": None,
            "created_at": workflow.created_at,
            "updated_at": get_current_utc_time(),
        }

        config = {"configurable": {"thread_id": workflow_id_str}}

        try:
            checkpointer = await self.saver_manager.get_saver(thread_id=workflow_id_str)
            graph = self._get_workflow_graph(checkpointer=checkpointer)

            await graph.graph.ainvoke(initial_state, config=config)

            final_state = await self._get_final_state(config, workflow, workflow_id_str)
            # 仅打印关键字段，避免日志输出完整 task_results
            _log_keys = {
                k: v
                for k, v in (final_state or {}).items()
                if k in ("workflow_status", "task_summary", "report_url", "error")
            }
            logger.info(f"[ResearchService] Final state summary: {_log_keys}")

            await self._update_workflow_state(workflow, final_state, workflow_id_str)
            await self._force_update_workflow_to_database(workflow)

            logger.info(f"[ResearchService] Workflow execution completed: {workflow_id}")
        except CheckpointConnectionError as e:
            logger.error(
                f"[ResearchService] Checkpoint connection failed | "
                f"workflow_id={workflow_id_str} | "
                f"error={e.message} | "
                f"retries={e.retry_count}",
                exc_info=True,
            )
            workflow.mark_all_failed()
            try:
                await self.workflow_repository.update(workflow)
            except Exception as db_error:
                logger.error(
                    f"[ResearchService] Failed to update workflow in database after checkpoint error: {db_error}"
                )
            await self.event_publisher.publish_error_event(
                workflow_id=workflow_id, message="工作流状态存储不可用，请稍后重试"
            )
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "CHECKPOINT_CONNECTION_ERROR",
                    "message": "无法访问工作流状态存储，请稍后重试",
                    "workflow_id": workflow_id_str,
                },
            ) from e
        except Exception as e:
            logger.error(f"[ResearchService] Workflow execution failed: {str(e)}")
            workflow.mark_all_failed()
            try:
                await self.workflow_repository.update(workflow)
            except Exception as db_error:
                logger.error(
                    f"[ResearchService] Failed to update workflow in database after failure: {db_error}"
                )
            await self.event_publisher.publish_error_event(workflow_id=workflow_id, message=str(e))
            raise

    async def _get_final_state(self, config, workflow, workflow_id_str) -> dict[str, Any] | None:
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
                            logger.info(
                                f"[ResearchService] Got final state from AsyncPostgresSaver checkpoint (retry={retry})"
                            )
                            return final_state
                else:
                    final_state = checkpointer.get(config)
                    if final_state:
                        logger.info(
                            f"[ResearchService] Got final state from InMemorySaver checkpoint (retry={retry})"
                        )
                        return final_state

                break
            except Exception as e:
                if retry < max_retries - 1:
                    logger.warning(
                        f"[ResearchService] Failed to get state from checkpoint (retry={retry}): {e}, retrying..."
                    )
                    if hasattr(self.saver_manager, "_close_saver"):
                        await self.saver_manager._close_saver()
                else:
                    logger.warning(
                        f"[ResearchService] Failed to get state from checkpoint after {max_retries} retries: {e}"
                    )

        logger.warning("[ResearchService] No state from checkpoint, calculating from database")
        return await self._calculate_state_from_database(workflow_id_str)

    async def _calculate_state_from_database(self, workflow_id_str: str) -> dict[str, Any] | None:
        try:
            tasks = await self.task_repository.find_by_workflow_id(workflow_id_str)
            completed_count = sum(
                1
                for task in tasks
                if (task.status.value if hasattr(task.status, "value") else task.status)
                == "completed"
            )
            failed_count = sum(
                1
                for task in tasks
                if (task.status.value if hasattr(task.status, "value") else task.status) == "failed"
            )
            total_count = len(tasks)

            logger.info(
                f"[ResearchService] Tasks: {completed_count}/{total_count} completed, {failed_count} failed from database"
            )

            report_url = None
            try:
                report_url = await self.object_storage.get_report_url_by_workflow_id(
                    workflow_id_str
                )
                if report_url:
                    logger.info(f"[ResearchService] Found report URL from storage: {report_url}")
            except Exception as storage_error:
                logger.warning(
                    f"[ResearchService] Failed to get report URL from storage: {storage_error}"
                )

            workflow_status = None
            has_report = report_url is not None

            task_summary = {
                "total": total_count,
                "completed": completed_count,
                "failed": failed_count,
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
                "tasks": tasks,
            }

            return state
        except Exception as e:
            logger.error(f"[ResearchService] Failed to calculate state from database: {e}")
            return None

    async def _update_workflow_state(
        self, workflow: Workflow, final_state: dict[str, Any] | None, workflow_id_str: str
    ):
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
                    logger.info(
                        f"[ResearchService] Workflow {workflow_id_str} marked as ALL_SUCCESS"
                    )

                elif workflow_status == "partial_failed":
                    workflow.mark_partial_failed(report_url)
                    logger.info(
                        f"[ResearchService] Workflow {workflow_id_str} marked as PARTIAL_FAILED"
                    )

                elif workflow_status == "all_failed":
                    workflow.mark_all_failed()
                    logger.info(
                        f"[ResearchService] Workflow {workflow_id_str} marked as ALL_FAILED"
                    )

                elif workflow_status == "report_failed":
                    workflow.mark_report_failed()
                    logger.info(
                        f"[ResearchService] Workflow {workflow_id_str} marked as REPORT_FAILED"
                    )

                else:
                    logger.warning(
                        f"[ResearchService] Unknown workflow status: {workflow_status}, using fallback logic"
                    )
                    self._update_workflow_fallback(workflow, final_state, workflow_id_str)
            else:
                logger.warning(
                    "[ResearchService] No workflow_status in final state, using fallback logic"
                )
                self._update_workflow_fallback(workflow, final_state, workflow_id_str)
        else:
            logger.warning("[ResearchService] No final state available, checking database tasks")
            await self._update_workflow_from_database(workflow, workflow_id_str)

    def _update_workflow_fallback(
        self, workflow: Workflow, final_state: dict[str, Any], workflow_id_str: str
    ):
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
                if hasattr(t, "status"):
                    status_value = t.status.value if hasattr(t.status, "value") else str(t.status)
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
                logger.warning("[ResearchService] Workflow still in progress")

    async def _force_update_workflow_to_database(self, workflow: Workflow):
        try:
            await self.workflow_repository.update(workflow)
            logger.info(
                f"[ResearchService] Workflow force updated - status: {workflow.status}, completed_at: {workflow.completed_at}"
            )
        except Exception as db_error:
            logger.error(
                f"[ResearchService] Failed to force update workflow in database: {db_error}"
            )

    async def get_workflow_status(self, workflow_id: str | UUID) -> ResearchResponse:
        workflow_id_str = str(workflow_id)

        workflow = await self.workflow_repository.find_by_id(workflow_id_str)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id_str}")

        return self._to_research_response(workflow)

    async def _update_workflow_from_database(
        self, workflow: Workflow, workflow_id_str: str
    ) -> None:
        try:
            db_workflow = await self.workflow_repository.find_by_id(workflow_id_str)
            if not db_workflow:
                logger.warning(
                    f"[ResearchService] Workflow not found in database: {workflow_id_str}"
                )
                return

            status_value = (
                db_workflow.status.value
                if hasattr(db_workflow.status, "value")
                else db_workflow.status
            )

            if status_value == "completed":
                logger.info("[ResearchService] Workflow already completed in database")
                workflow.status = db_workflow.status
                workflow.report_url = db_workflow.report_url
                workflow.completed_at = db_workflow.completed_at
            elif status_value == "failed":
                logger.info("[ResearchService] Workflow already failed in database")
                workflow.status = db_workflow.status
            else:
                logger.warning(
                    f"[ResearchService] Workflow status in database is still '{status_value}', checking tasks for completion"
                )
                tasks = await self.task_repository.find_by_workflow_id(workflow_id_str)
                completed_count = sum(
                    1
                    for task in tasks
                    if (task.status.value if hasattr(task.status, "value") else task.status)
                    == "completed"
                )
                total_count = len(tasks)

                logger.info(f"[ResearchService] Tasks: {completed_count}/{total_count} completed")

                if completed_count > 0 and completed_count == total_count:
                    workflow.mark_all_success(f"/reports/{workflow_id_str}")
                    logger.info(
                        "[ResearchService] Workflow marked as completed based on task completion"
                    )
                elif completed_count == 0 and total_count == 0:
                    workflow.mark_all_failed()
                    logger.warning("[ResearchService] No tasks found, marking workflow as failed")
                else:
                    logger.warning(
                        f"[ResearchService] Workflow still in progress: {completed_count}/{total_count} tasks completed"
                    )

            await self.workflow_repository.update(workflow)
            logger.info(
                f"[ResearchService] Workflow updated from database - status: {workflow.status}"
            )
        except Exception as e:
            logger.error(f"[ResearchService] Failed to update workflow from database: {e}")

    def _to_workflow_response(self, workflow: Workflow) -> WorkflowResponse:
        task_responses = [self._to_task_response(task) for task in workflow.tasks]

        return WorkflowResponse(
            workflow_id=workflow.workflow_id,
            topic=workflow.topic,
            scenario_id=workflow.scenario_id,
            description=workflow.description,
            status=workflow.status,
            report_url=workflow.report_url,
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
            started_at=workflow.started_at,
            completed_at=workflow.completed_at,
            tasks=task_responses,
        )

    def _to_research_response(self, workflow: Workflow) -> ResearchResponse:
        return ResearchResponse(
            workflow_id=workflow.workflow_id,
            topic=workflow.topic,
            scenario_id=workflow.scenario_id,
            description=workflow.description,
            status=workflow.status,
            report_url=workflow.report_url,
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
            started_at=workflow.started_at,
            completed_at=workflow.completed_at,
            tasks=[self._to_task_response(task) for task in workflow.tasks],
        )

    def _to_task_response(self, task) -> TaskResponse:
        return TaskResponse(
            task_id=task.task_id,
            title=task.title,
            intent=task.intent,
            query=task.query,
            order=task.order,
            status=task.status.value if hasattr(task.status, "value") else task.status,
            summary=task.summary,
            sources_summary=task.sources_summary,
            notices=task.notices,
            created_at=task.created_at,
            updated_at=task.updated_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
        )

    def get_report_file_path(self, report_id: str) -> Path | None:
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

    async def get_report_content(self, workflow_id: str | UUID) -> str | None:
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
