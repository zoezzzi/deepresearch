"""
调研助手工作流图定义

定义 LangGraph 工作流的节点和边
"""
from typing import Dict, Any, List
import asyncio
from langgraph.graph import StateGraph, END
from app.research_assistant.workflow.state import WorkflowState
from app.research_assistant.services import (
    ResearchPlanService,
    TaskExecutionService,
    ReportGenerationService,
    EvaluationService
)
from app.research_assistant.models.models import Task
from app.research_assistant.repositories import TaskRepository
from app.research_assistant.events import EventPublisher
from app.research_assistant.tasks import run_evaluation_task
from harness.storage.base import ObjectStorage
from harness.evaluation.orchestrator import EvaluationOrchestrator
from harness.logger import logger
from app.common.utils.time_utils import get_current_utc_time


class ResearchWorkflowGraph:
    """
    调研工作流图
    
    定义调研任务的完整工作流：
    1. plan: 生成任务计划
    2. execute_task: 执行单个任务
    3. generate_report: 生成报告
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
        """构建工作流图"""
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
        """计划节点：生成任务列表"""
        logger.info(f"[Workflow] Executing plan node for workflow {state['workflow_id']}")

        try:
            workflow_id = state["workflow_id"]
            tasks = await self.research_plan_service.generate_tasks(
                workflow_id=workflow_id,
                topic=state["topic"],
                description=state.get("description", "")
            )

            task_dicts = [
                {
                    "task_id": task.task_id,
                    "title": task.title,
                    "intent": task.intent,
                    "query": task.query,
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
        """任务执行节点：执行单个任务"""
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
                task_id=current_task["task_id"],
                workflow_id=state["workflow_id"],
                title=current_task["title"],
                intent=current_task["intent"],
                query=current_task["query"],
                order=current_task["order"]
            )

            summary, sources_summary, notices = await self.task_execution_service.execute_task(task)

            task_result = {
                "task_id": current_task["task_id"],
                "title": current_task["title"],
                "summary": summary,
                "sources_summary": sources_summary,
                "notices": notices
            }

            await self.event_publisher.publish_task_complete_event(
                workflow_id=state["workflow_id"],
                task_id=current_task["task_id"],
                task_title=current_task["title"],
                summary=summary,
                sources_summary=sources_summary,
                notices=notices
            )

            tasks[current_index]["status"] = "completed"

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

            logger.info(f"[Workflow] Task {current_index + 1} completed")

            retrieved_chunks = state.get("retrieved_chunks", [])
            if sources_summary:
                retrieved_chunks.append(sources_summary)

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
            tasks[current_index]["status"] = "failed"

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
        """判断是否继续执行下一个任务"""
        if state.get("error"):
            return "generate_report"

        current_index = state["current_task_index"]
        tasks = state["tasks"]

        if current_index >= len(tasks):
            return "generate_report"
        return "continue"

    async def _generate_report_node(self, state: WorkflowState) -> Dict[str, Any]:
        """报告生成节点：生成最终报告"""
        logger.info(f"[Workflow] Generating report for workflow {state['workflow_id']}")

        tasks = state.get("tasks", [])
        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t.get("status") == "completed")
        failed_tasks = sum(1 for t in tasks if t.get("status") == "failed")

        logger.info(f"[Workflow] Task summary: {completed_tasks}/{total_tasks} completed, {failed_tasks} failed")

        task_summary = {
            "total": total_tasks,
            "completed": completed_tasks,
            "failed": failed_tasks
        }

        # 计算完成率门槛: 必须 > 50% 才能生成报告
        completion_rate = completed_tasks / total_tasks if total_tasks > 0 else 0
        
        if completion_rate <= 0.5:
            logger.warning(
                f"[Workflow] Completion rate {completion_rate:.1%} <= 50%, "
                f"skipping report generation. Completed: {completed_tasks}/{total_tasks}"
            )
            return {
                "report_content": None,
                "report_url": None,
                "workflow_status": "all_failed" if failed_tasks == total_tasks else "partial_failed",
                "task_summary": task_summary,
                "updated_at": get_current_utc_time()
            }
        
        logger.info(
            f"[Workflow] Completion rate {completion_rate:.1%} > 50%, "
            f"proceeding with report generation"
        )

        retrieved_chunks = state.get("retrieved_chunks", [])
        sub_questions = state.get("sub_questions", [])
        citations = state.get("citations", [])

        report_generated = False
        report_content = None
        report_url = None
        report_error = None
        evaluation_id = None

        try:
            workflow_id = state["workflow_id"]

            # 构建任务结果字典，方便查找
            task_results_map = {
                result["task_id"]: result 
                for result in state.get("task_results", [])
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
                
                # 如果任务有结果，填充摘要数据
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

            try:
                logger.info(f"[Workflow] Saving report to storage")
                report_content_bytes = report.content.encode("utf-8")
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
                report_url = f"/reports/{state['workflow_id']}"

            await self.event_publisher.publish_result_event(
                workflow_id=state["workflow_id"],
                report_url=report_url
            )

            if report_generated:
                try:
                    logger.info(f"[Workflow] Creating evaluation record for workflow {state['workflow_id']}")
                    evaluation = await self.evaluation_service.create_evaluation(workflow_id)
                    evaluation_id = evaluation.evaluation_id

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

        if report_generated:
            if completed_tasks == total_tasks:
                workflow_status = "all_success"
            else:
                workflow_status = "partial_failed"
        else:
            if completed_tasks == total_tasks:
                workflow_status = "report_failed"
            else:
                workflow_status = "partial_failed"

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
        """获取编译后的工作流图"""
        return self._graph
