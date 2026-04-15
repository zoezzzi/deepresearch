from typing import Dict, Any, List
import asyncio
from langgraph.graph import StateGraph, END
from .state import WorkflowState
from domain.domain_services.research_plan_service import ResearchPlanService
from domain.domain_services.task_execution_service import TaskExecutionService
from domain.domain_services.report_generation_service import ReportGenerationService
from domain.domain_services.evaluation_service import EvaluationService
from domain.value_objects.workflow_id import WorkflowId
from domain.value_objects.task_id import TaskId
from domain.value_objects.task_intent import TaskIntent
from domain.value_objects.search_query import SearchQuery
from domain.entities.task import Task
from domain.repositories.task_repository import TaskRepository
from application.events.event_publisher import EventPublisher
from application.tasks.evaluation_task import run_evaluation_task
from infrastructure.storage.base import ObjectStorage
from infrastructure.evaluation.orchestrator import EvaluationOrchestrator
from common.logger import logger
from common.utils.time_utils import get_current_utc_time


class ResearchWorkflowGraph:
    def __init__(
        self,
        research_plan_service: ResearchPlanService,
        task_execution_service: TaskExecutionService,
        report_generation_service: ReportGenerationService,
        event_publisher: EventPublisher,
        task_repository: TaskRepository,
        object_storage: ObjectStorage,
        evaluation_service: EvaluationService,
        evaluation_orchestrator: EvaluationOrchestrator
    ):
        self.research_plan_service = research_plan_service
        self.task_execution_service = task_execution_service
        self.report_generation_service = report_generation_service
        self.event_publisher = event_publisher
        self.task_repository = task_repository
        self.object_storage = object_storage
        self.evaluation_service = evaluation_service
        self.evaluation_orchestrator = evaluation_orchestrator
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(WorkflowState)

        workflow.add_node("plan", self._plan_node)
        workflow.add_node("execute_task", self._execute_task_node)
        workflow.add_node("generate_report", self._generate_report_node)

        workflow.set_entry_point("plan")
        workflow.add_edge("plan", "execute_task")
        workflow.add_conditional_edges(
            "execute_task",
            self._should_continue,
            {
                "continue": "execute_task",
                "generate_report": "generate_report"
            }
        )
        workflow.add_edge("generate_report", END)

        return workflow.compile()

    async def _plan_node(self, state: WorkflowState) -> Dict[str, Any]:
        logger.info(f"[Workflow] Executing plan node for workflow {state['workflow_id']}")
        
        try:
            workflow_id = WorkflowId(state["workflow_id"])
            tasks = await self.research_plan_service.generate_tasks(
                workflow_id=workflow_id,
                topic=state["topic"],
                description=state.get("description", "")
            )

            task_dicts = [
                {
                    "task_id": task.task_id.value,
                    "title": task.title,
                    "intent": task.intent.value,
                    "query": task.query.value,
                    "order": task.order,
                    "status": "pending"
                }
                for task in tasks
            ]

            try:
                await self.task_repository.save_batch(tasks)
                logger.info(f"[Workflow] Saved {len(tasks)} tasks to database")
            except Exception as db_error:
                logger.error(f"[Workflow] Failed to save tasks to database: {db_error}, but continuing workflow execution")

            await self.event_publisher.publish_plan_event(
                workflow_id=state["workflow_id"],
                tasks=task_dicts
            )

            # 提取子问题用于评估
            sub_questions = [task.title for task in tasks]

            logger.info(f"[Workflow] Plan generated with {len(task_dicts)} tasks")
            return {
                "tasks": task_dicts,
                "current_task_index": 0,
                "task_results": [],
                "sub_questions": sub_questions,
                "retrieved_chunks": [],
                "citations": [],
                "updated_at": get_current_utc_time()
            }
        except Exception as e:
            logger.error(f"[Workflow] Plan node failed: {str(e)}")
            await self.event_publisher.publish_error_event(
                workflow_id=state["workflow_id"],
                message=str(e)
            )
            return {
                "error": str(e),
                "updated_at": get_current_utc_time()
            }

    async def _execute_task_node(self, state: WorkflowState) -> Dict[str, Any]:
        current_index = state["current_task_index"]
        tasks = state["tasks"]

        if current_index >= len(tasks):
            return state

        current_task = tasks[current_index]
        logger.info(f"[Workflow] Executing task {current_index + 1}/{len(tasks)}: {current_task['title']}")

        try:
            await self.event_publisher.publish_task_start_event(
                workflow_id=state["workflow_id"],
                task_id=current_task["task_id"],
                task_title=current_task["title"]
            )

            task = Task(
                task_id=TaskId(current_task["task_id"]),
                workflow_id=WorkflowId(state["workflow_id"]),
                title=current_task["title"],
                intent=TaskIntent(current_task["intent"]),
                query=SearchQuery(current_task["query"]),
                order=current_task["order"]
            )

            summary, sources_summary, notices = await self.task_execution_service.execute_task(task)

            task_result = {
                "task_id": current_task["task_id"],
                "title": current_task["title"],
                "summary": summary.value,
                "sources_summary": sources_summary.value,
                "notices": notices.value
            }

            await self.event_publisher.publish_task_complete_event(
                workflow_id=state["workflow_id"],
                task_id=current_task["task_id"],
                task_title=current_task["title"],
                summary=summary.value,
                sources_summary=sources_summary.value,
                notices=notices.value
            )

            # 更新内存状态
            tasks[current_index]["status"] = "completed"

            # 【关键修复】同步更新数据库中的任务状态
            try:
                task_entity = await self.task_repository.find_by_id(current_task["task_id"])
                if task_entity:
                    task_entity.complete(summary, sources_summary, notices)
                    await self.task_repository.update(task_entity)
                    logger.info(f"[Workflow] Task {current_task['task_id']} status updated to completed in database")
                else:
                    logger.warning(f"[Workflow] Task {current_task['task_id']} not found in database, skipping status update")
            except Exception as db_error:
                logger.error(f"[Workflow] Failed to update task {current_task['task_id']} status in database: {db_error}")
                # 不影响主流程，继续执行

            logger.info(f"[Workflow] Task {current_index + 1} completed")
            
            # 收集检索到的片段用于评估
            retrieved_chunks = state.get("retrieved_chunks", [])
            if sources_summary.value:
                retrieved_chunks.append(sources_summary.value)
            
            return {
                "tasks": tasks,
                "current_task_index": current_index + 1,
                "task_results": state["task_results"] + [task_result],
                "retrieved_chunks": retrieved_chunks,
                "updated_at": get_current_utc_time()
            }
        except Exception as e:
            logger.error(f"[Workflow] Task execution failed: {str(e)}")
            await self.event_publisher.publish_error_event(
                workflow_id=state["workflow_id"],
                message=f"Task {current_task['title']} failed: {str(e)}"
            )
            # 更新内存状态
            tasks[current_index]["status"] = "failed"

            # 【关键修复】同步更新数据库中的任务状态为失败
            try:
                task_entity = await self.task_repository.find_by_id(current_task["task_id"])
                if task_entity:
                    task_entity.fail(str(e))
                    await self.task_repository.update(task_entity)
                    logger.info(f"[Workflow] Task {current_task['task_id']} status updated to failed in database")
            except Exception as db_error:
                logger.error(f"[Workflow] Failed to update task {current_task['task_id']} failed status in database: {db_error}")

            return {
                "tasks": tasks,
                "current_task_index": current_index + 1,
                "updated_at": get_current_utc_time()
            }

    def _should_continue(self, state: WorkflowState) -> str:
        if state.get("error"):
            return "generate_report"
        
        current_index = state["current_task_index"]
        tasks = state["tasks"]
        
        if current_index >= len(tasks):
            return "generate_report"
        return "continue"

    async def _generate_report_node(self, state: WorkflowState) -> Dict[str, Any]:
        """
        生成报告节点
        
        根据任务执行结果和报告生成情况，设置工作流完成状态：
        1. ALL_SUCCESS: 全部任务成功，报告生成成功
        2. PARTIAL_FAILED: 部分任务失败，报告生成成功
        3. ALL_FAILED: 全部任务失败，不生成报告
        4. REPORT_FAILED: 全部任务成功，但报告生成失败
        
        报告生成成功后，触发后台异步评估任务（不阻塞主工作流）
        """
        logger.info(f"[Workflow] Generating report for workflow {state['workflow_id']}")
        
        # 统计任务执行结果
        tasks = state.get("tasks", [])
        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t.get("status") == "completed")
        failed_tasks = sum(1 for t in tasks if t.get("status") == "failed")
        
        logger.info(f"[Workflow] Task summary: {completed_tasks}/{total_tasks} completed, {failed_tasks} failed")
        
        # 构建任务摘要
        task_summary = {
            "total": total_tasks,
            "completed": completed_tasks,
            "failed": failed_tasks
        }
        
        # 收集评估所需数据
        retrieved_chunks = state.get("retrieved_chunks", [])
        sub_questions = state.get("sub_questions", [])
        citations = state.get("citations", [])
        
        # 情况3：全部任务失败或空任务列表，不生成报告
        if total_tasks == 0 or failed_tasks == total_tasks:
            logger.info(f"[Workflow] All tasks failed or no tasks, skipping report generation")
            return {
                "report_content": None,
                "report_url": None,
                "workflow_status": "all_failed",
                "task_summary": task_summary,
                "updated_at": get_current_utc_time()
            }
        
        # 尝试生成报告
        report_generated = False
        report_content = None
        report_url = None
        report_error = None
        evaluation_id = None
        
        try:
            workflow_id = WorkflowId(state["workflow_id"])
            
            # 构建任务列表
            task_entities = []
            for task_dict, result_dict in zip(state["tasks"], state["task_results"]):
                task = Task(
                    task_id=TaskId(task_dict["task_id"]),
                    workflow_id=workflow_id,
                    title=task_dict["title"],
                    intent=TaskIntent(task_dict["intent"]),
                    query=SearchQuery(task_dict["query"]),
                    order=task_dict["order"]
                )
                task_entities.append(task)

            report = await self.report_generation_service.generate_report(
                workflow_id=workflow_id,
                topic=state["topic"],
                tasks=task_entities
            )
            report_content = report.content.value
            report_generated = True

            # 保存报告到存储
            try:
                logger.info(f"[Workflow] Saving report to storage")
                report_content_bytes = report.content.value.encode("utf-8")
                # 使用 workflow_id 作为文件名，便于后续查找
                report_filename = f"{state['workflow_id']}.md"
                report_url = await self.object_storage.upload_object(
                    bucket_name="reports",
                    object_name=report_filename,
                    data=report_content_bytes,
                    content_type="text/markdown"
                )
                logger.info(f"[Workflow] Report saved to storage: {report_url}")
            except Exception as storage_error:
                logger.error(f"[Workflow] Failed to save report to storage: {storage_error}")
                # 报告生成成功但保存失败，仍视为报告生成成功
                report_url = f"/reports/{state['workflow_id']}"  # 提供默认URL

            await self.event_publisher.publish_result_event(
                workflow_id=state["workflow_id"],
                report_url=report_url
            )
            
            # 创建评估记录并触发异步评估任务
            if report_generated:
                try:
                    logger.info(f"[Workflow] Creating evaluation record for workflow {state['workflow_id']}")
                    evaluation = await self.evaluation_service.create_evaluation(workflow_id)
                    evaluation_id = evaluation.evaluation_id
                    
                    # 触发后台异步评估任务
                    asyncio.create_task(
                        run_evaluation_task(
                            evaluation_id=evaluation_id,
                            workflow_id=state["workflow_id"],
                            report=report_content,
                            contexts=retrieved_chunks,
                            question=state["topic"],
                            sub_questions=sub_questions,
                            citations=citations,
                            evaluation_service=self.evaluation_service,
                            evaluation_orchestrator=self.evaluation_orchestrator
                        )
                    )
                    logger.info(f"[Workflow] Async evaluation task triggered: {evaluation_id}")
                except Exception as eval_error:
                    logger.error(f"[Workflow] Failed to trigger evaluation: {str(eval_error)}")

        except Exception as e:
            report_error = str(e)
            logger.error(f"[Workflow] Report generation failed: {report_error}")
            await self.event_publisher.publish_error_event(
                workflow_id=state["workflow_id"],
                message=f"Report generation failed: {report_error}"
            )
        
        # 根据结果设置工作流状态
        if report_generated:
            # 报告生成成功
            if completed_tasks == total_tasks:
                workflow_status = "all_success"  # 情况1：全部任务成功，报告生成成功
            else:
                workflow_status = "partial_failed"  # 情况2：部分任务失败，报告生成成功
        else:
            # 报告生成失败
            if completed_tasks == total_tasks:
                workflow_status = "report_failed"  # 情况4：全部任务成功，但报告生成失败
            else:
                workflow_status = "partial_failed"  # 部分失败且报告失败
        
        logger.info(f"[Workflow] Workflow completed with status: {workflow_status}")
        
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

    @property
    def graph(self):
        return self._graph
