import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Union, Dict, Any
from uuid import UUID
from application.dtos import (
    CreateResearchRequest,
    WorkflowResponse,
    TaskResponse,
    ResearchResponse
)
from application.workflow import ResearchWorkflowGraph, WorkflowState, get_saver_manager
from application.events import get_event_publisher
from domain.entities.workflow import Workflow
from domain.value_objects.workflow_id import WorkflowId
from domain.value_objects.workflow_status import WorkflowStatus
from domain.domain_services.research_plan_service import ResearchPlanService
from domain.domain_services.task_execution_service import TaskExecutionService
from domain.domain_services.report_generation_service import ReportGenerationService
from domain.repositories.workflow_repository import WorkflowRepository
from domain.repositories.task_repository import TaskRepository
from domain.agents.plan_agent import PlanAgent
from domain.agents.search_agent import SearchAgent
from domain.agents.summarizer_agent import SummarizerAgent
from domain.agents.generate_agent import GenerateAgent
from infrastructure.llm.factory import get_llm_client
from infrastructure.search.factory import get_search_source
from infrastructure.storage.local_storage import LocalObjectStorage
from infrastructure.config import get_settings
from infrastructure.logger import logger
from common.utils.time_utils import get_current_utc_time

settings = get_settings()


class ResearchApplicationService:
    def __init__(
        self,
        workflow_repository: WorkflowRepository,
        task_repository: TaskRepository
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
        
        self.event_publisher = get_event_publisher()
        self.object_storage = LocalObjectStorage()
        
        self.workflow_graph = ResearchWorkflowGraph(
            research_plan_service=self.research_plan_service,
            task_execution_service=self.task_execution_service,
            report_generation_service=self.report_generation_service,
            event_publisher=self.event_publisher,
            task_repository=task_repository,
            object_storage=self.object_storage
        )
        
        # 使用 AsyncPostgresSaverManager 进行状态持久化管理
        self.saver_manager = get_saver_manager()
        logger.info("Using AsyncPostgresSaverManager for workflow state persistence")

    async def create_research_workflow(self, request: CreateResearchRequest) -> WorkflowResponse:
        logger.info(f"[ResearchApplicationService] Creating research workflow for topic: {request.topic}")
        
        workflow_id = WorkflowId(str(uuid.uuid4()))
        workflow = Workflow(
            workflow_id=workflow_id,
            topic=request.topic,
            description=request.description,
            status=WorkflowStatus.PENDING
        )
        
        try:
            await self.workflow_repository.save(workflow)
        except Exception as db_error:
            logger.error(f"[ResearchApplicationService] Failed to save workflow to database: {db_error}, but continuing with in-memory workflow")
        
        logger.info(f"[ResearchApplicationService] Workflow created: {workflow_id.value}")
        return self._to_workflow_response(workflow)

    async def execute_research_workflow(self, workflow_id: Union[str, UUID]) -> None:
        workflow_id_str = str(workflow_id)
        logger.info(f"[ResearchApplicationService] Executing research workflow: {workflow_id_str}")
        
        workflow = await self.workflow_repository.find_by_id(workflow_id_str)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id_str}")
        
        workflow.start()
        try:
            await self.workflow_repository.update(workflow)
        except Exception as db_error:
            logger.error(f"[ResearchApplicationService] Failed to update workflow to database: {db_error}, but continuing with execution")
        
        initial_state: WorkflowState = {
            "workflow_id": workflow_id_str,
            "topic": workflow.topic,
            "description": workflow.description,
            "tasks": [],
            "current_task_index": 0,
            "task_results": [],
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
            # 获取 saver 实例
            checkpointer = await self.saver_manager.get_saver()
            
            await self.workflow_graph.graph.ainvoke(
                initial_state,
                config=config,
                checkpointer=checkpointer
            )
            
            final_state = await self._get_final_state(config, workflow, workflow_id_str)
            logger.info(f"[ResearchApplicationService] Final state: {final_state}")
            
            await self._update_workflow_state(workflow, final_state, workflow_id_str)
            await self._force_update_workflow_to_database(workflow)
            
            logger.info(f"[ResearchApplicationService] Workflow execution completed: {workflow_id}")
        except Exception as e:
            logger.error(f"[ResearchApplicationService] Workflow execution failed: {str(e)}")
            workflow.fail()
            try:
                await self.workflow_repository.update(workflow)
            except Exception as db_error:
                logger.error(f"[ResearchApplicationService] Failed to update workflow in database after failure: {db_error}")
            await self.event_publisher.publish_error_event(
                workflow_id=workflow_id,
                message=str(e)
            )
            raise

    async def _get_final_state(self, config, workflow, workflow_id_str) -> Optional[Dict[str, Any]]:
        """
        多级获取最终状态：优先从 checkpoint 获取，然后从数据库任务完成情况计算
        增强版：支持重试，当 checkpoint 获取失败时重新获取连接
        """
        max_retries = 2
        for retry in range(max_retries):
            try:
                # 获取 saver 实例（连接会自动检查并重新连接）
                checkpointer = await self.saver_manager.get_saver()

                # 检查是否是 AsyncPostgresSaver
                from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
                if isinstance(checkpointer, AsyncPostgresSaver):
                    # 对于 AsyncPostgresSaver
                    checkpoint_tuple = await checkpointer.aget_tuple(config)
                    if checkpoint_tuple and checkpoint_tuple.checkpoint:
                        final_state = checkpoint_tuple.checkpoint.get("channel_values", {})
                        if final_state:
                            logger.info(f"[ResearchApplicationService] Got final state from AsyncPostgresSaver checkpoint (retry={retry})")
                            return final_state
                else:
                    # 对于 InMemorySaver
                    final_state = checkpointer.get(config)
                    if final_state:
                        logger.info(f"[ResearchApplicationService] Got final state from InMemorySaver checkpoint (retry={retry})")
                        return final_state

                # 如果没有找到状态，说明确实没有
                break
            except Exception as e:
                if retry < max_retries - 1:
                    logger.warning(f"[ResearchApplicationService] Failed to get state from checkpoint (retry={retry}): {e}, retrying...")
                    # 重置 saver 实例，让下次重新连接
                    if hasattr(self.saver_manager, '_close_saver'):
                        await self.saver_manager._close_saver()
                else:
                    logger.warning(f"[ResearchApplicationService] Failed to get state from checkpoint after {max_retries} retries: {e}")

        # 从数据库计算状态
        logger.warning(f"[ResearchApplicationService] No state from checkpoint, calculating from database")
        return await self._calculate_state_from_database(workflow_id_str)

    async def _calculate_state_from_database(self, workflow_id_str: str) -> Optional[Dict[str, Any]]:
        """
        基于数据库任务完成情况计算状态
        【增强版】补充从存储系统查询 report_url
        """
        try:
            tasks = await self.task_repository.find_by_workflow_id(workflow_id_str)
            completed_count = sum(1 for task in tasks if (task.status.value if hasattr(task.status, 'value') else task.status) == "completed")
            total_count = len(tasks)

            logger.info(f"[ResearchApplicationService] Tasks: {completed_count}/{total_count} completed from database")

            # 【关键修复】从存储系统查询已生成的报告 URL
            report_url = None
            try:
                report_url = await self.object_storage.get_report_url_by_workflow_id(workflow_id_str)
                if report_url:
                    logger.info(f"[ResearchApplicationService] Found report URL from storage: {report_url}")
            except Exception as storage_error:
                logger.warning(f"[ResearchApplicationService] Failed to get report URL from storage: {storage_error}")

            state = {
                "report_url": report_url,
                "error": None,
                "tasks": tasks
            }

            return state
        except Exception as e:
            logger.error(f"[ResearchApplicationService] Failed to calculate state from database: {e}")
            return None

    async def _update_workflow_state(self, workflow: Workflow, final_state: Optional[Dict[str, Any]], workflow_id_str: str):
        """
        从最终状态更新 workflow 对象
        """
        if final_state:
            report_url = final_state.get("report_url")
            error = final_state.get("error")
            
            logger.info(f"[ResearchApplicationService] Report URL: {report_url}")
            logger.info(f"[ResearchApplicationService] Error: {error}")
            
            if report_url:
                from domain.value_objects.report_url import ReportUrl
                workflow.complete(ReportUrl(report_url))
            elif error:
                workflow.fail()
            else:
                logger.warning("[ResearchApplicationService] No report_url and no error, checking tasks for completion")
                tasks = final_state.get("tasks", [])
                completed_count = 0
                failed_count = 0
                total_count = len(tasks)
                
                if hasattr(tasks, "__len__") and total_count > 0:
                    if hasattr(tasks[0], "get"):
                        completed_count = sum(1 for t in tasks if t.get("status") == "completed")
                        failed_count = sum(1 for t in tasks if t.get("status") == "failed")
                    else:
                        completed_count = sum(1 for t in tasks if (t.status.value if hasattr(t.status, 'value') else t.status) == "completed")
                        failed_count = sum(1 for t in tasks if (t.status.value if hasattr(t.status, 'value') else t.status) == "failed")
                
                logger.info(f"[ResearchApplicationService] Tasks: {completed_count}/{total_count} completed, {failed_count}/{total_count} failed in state")
                
                if completed_count > 0 and completed_count == total_count:
                    # 所有任务都完成
                    from domain.value_objects.report_url import ReportUrl
                    workflow.complete(ReportUrl(f"/reports/{workflow_id_str}"))
                elif failed_count > 0 and completed_count == 0:
                    # 所有任务都失败
                    workflow.fail()
                    logger.warning(f"[ResearchApplicationService] All tasks failed, marking workflow as failed")
                elif completed_count > 0 and failed_count > 0:
                    # 部分任务完成，部分失败 - 生成部分报告
                    from domain.value_objects.report_url import ReportUrl
                    workflow.complete(ReportUrl(f"/reports/{workflow_id_str}"))
                    logger.info(f"[ResearchApplicationService] Partial completion: {completed_count}/{total_count} tasks completed, generating partial report")
                elif total_count == 0:
                    # 没有任务
                    workflow.fail()
                    logger.warning(f"[ResearchApplicationService] No tasks found in state, marking workflow as failed")
                else:
                    # 任务仍在进行中
                    logger.warning(f"[ResearchApplicationService] Workflow still in progress: {completed_count}/{total_count} tasks completed")
        else:
            logger.warning("[ResearchApplicationService] No final state available, checking database tasks")
            await self._update_workflow_from_database(workflow, workflow_id_str)

    async def _force_update_workflow_to_database(self, workflow: Workflow):
        """
        强制更新 workflow 到数据库，无论状态如何
        """
        try:
            await self.workflow_repository.update(workflow)
            logger.info(f"[ResearchApplicationService] Workflow force updated - status: {workflow.status}, completed_at: {workflow.completed_at}")
        except Exception as db_error:
            logger.error(f"[ResearchApplicationService] Failed to force update workflow in database: {db_error}")

    async def get_workflow_status(self, workflow_id: Union[str, UUID]) -> ResearchResponse:
        workflow_id_str = str(workflow_id)
        logger.info(f"[ResearchApplicationService] Getting workflow status: {workflow_id_str}")

        workflow = await self.workflow_repository.find_by_id(workflow_id_str)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id_str}")

        return self._to_research_response(workflow)

    async def _update_workflow_from_database(self, workflow: Workflow, workflow_id_str: str) -> None:
        """
        当 final_state 为 None 时，从数据库获取最新的 workflow 状态并更新
        """
        try:
            db_workflow = await self.workflow_repository.find_by_id(workflow_id_str)
            if not db_workflow:
                logger.warning(f"[ResearchApplicationService] Workflow not found in database: {workflow_id_str}")
                return

            status_value = db_workflow.status.value if hasattr(db_workflow.status, 'value') else db_workflow.status
            
            if status_value == "completed":
                logger.info(f"[ResearchApplicationService] Workflow already completed in database")
                workflow.status = db_workflow.status
                workflow.report_url = db_workflow.report_url
                workflow.completed_at = db_workflow.completed_at
            elif status_value == "failed":
                logger.info(f"[ResearchApplicationService] Workflow already failed in database")
                workflow.status = db_workflow.status
            else:
                logger.warning(f"[ResearchApplicationService] Workflow status in database is still '{status_value}', checking tasks for completion")
                tasks = await self.task_repository.find_by_workflow_id(workflow_id_str)
                completed_count = sum(1 for task in tasks if (task.status.value if hasattr(task.status, 'value') else task.status) == "completed")
                total_count = len(tasks)
                
                logger.info(f"[ResearchApplicationService] Tasks: {completed_count}/{total_count} completed")
                
                if completed_count > 0 and completed_count == total_count:
                    from domain.value_objects.report_url import ReportUrl
                    workflow.complete(ReportUrl(f"/reports/{workflow_id_str}"))
                    logger.info(f"[ResearchApplicationService] Workflow marked as completed based on task completion")
                elif completed_count == 0 and total_count == 0:
                    workflow.fail()
                    logger.warning(f"[ResearchApplicationService] No tasks found, marking workflow as failed")
                else:
                    logger.warning(f"[ResearchApplicationService] Workflow still in progress: {completed_count}/{total_count} tasks completed")

            await self.workflow_repository.update(workflow)
            logger.info(f"[ResearchApplicationService] Workflow updated from database - status: {workflow.status}")
        except Exception as e:
            logger.error(f"[ResearchApplicationService] Failed to update workflow from database: {e}")

    def _to_workflow_response(self, workflow: Workflow) -> WorkflowResponse:
        task_responses = [
            self._to_task_response(task)
            for task in workflow.tasks
        ]
        
        return WorkflowResponse(
            workflow_id=workflow.workflow_id.value if hasattr(workflow.workflow_id, 'value') else workflow.workflow_id,
            topic=workflow.topic,
            description=workflow.description,
            status=workflow.status.value if hasattr(workflow.status, 'value') else workflow.status,
            report_url=workflow.report_url.value if workflow.report_url and hasattr(workflow.report_url, 'value') else workflow.report_url,
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
            started_at=workflow.started_at,
            completed_at=workflow.completed_at,
            tasks=task_responses
        )

    def _to_research_response(self, workflow: Workflow) -> ResearchResponse:
        return ResearchResponse(
            workflow_id=workflow.workflow_id.value if hasattr(workflow.workflow_id, 'value') else workflow.workflow_id,
            topic=workflow.topic,
            description=workflow.description,
            status=workflow.status.value if hasattr(workflow.status, 'value') else workflow.status,
            report_url=workflow.report_url.value if workflow.report_url and hasattr(workflow.report_url, 'value') else workflow.report_url,
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
            started_at=workflow.started_at,
            completed_at=workflow.completed_at,
            tasks=[self._to_task_response(task) for task in workflow.tasks]
        )

    def _to_task_response(self, task) -> TaskResponse:
        return TaskResponse(
            task_id=task.task_id.value if hasattr(task.task_id, 'value') else task.task_id,
            title=task.title,
            intent=task.intent.value if hasattr(task.intent, 'value') else task.intent,
            query=task.query.value if hasattr(task.query, 'value') else task.query,
            order=task.order,
            status=task.status.value if hasattr(task.status, 'value') else task.status,
            summary=task.summary.value if task.summary and hasattr(task.summary, 'value') else task.summary,
            sources_summary=task.sources_summary.value if task.sources_summary and hasattr(task.sources_summary, 'value') else task.sources_summary,
            notices=task.notices.value if task.notices and hasattr(task.notices, 'value') else task.notices,
            created_at=task.created_at,
            updated_at=task.updated_at,
            started_at=task.started_at,
            completed_at=task.completed_at
        )
    
    def get_report_file_path(self, report_id: str) -> Optional[Path]:
        """
        获取报告文件的完整路径
        在application层处理路径逻辑，controller只负责调用
        """
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
