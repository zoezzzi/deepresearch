"""
开发者调研助手工作流图定义（并行执行版）

支持任务并行执行，提高工作流效率
"""
from typing import Dict, Any, List
import asyncio
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
from app.common.utils.time_utils import get_current_utc_time

settings = get_harness_settings()


class ResearchWorkflowGraphParallel:
    """
    调研工作流图（并行执行版）

    定义调研任务的完整工作流，支持任务并行执行
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
        use_parallel_execution: bool = True,
        max_concurrent_tasks: int = 3
    ):
        self.research_plan_service = research_plan_service
        self.task_execution_service = task_execution_service
        self.report_generation_service = report_generation_service
        self.event_publisher = event_publisher
        self.task_repository = task_repository
        self.object_storage = object_storage
        self.evaluation_service = evaluation_service
        self.evaluation_orchestrator = evaluation_orchestrator
        self.use_parallel_execution = use_parallel_execution
        self.max_concurrent_tasks = max_concurrent_tasks
        
        # 初始化并行执行器
        self.parallel_executor = ParallelTaskExecutor(
            task_execution_service=task_execution_service,
            event_publisher=event_publisher,
            max_concurrent_tasks=max_concurrent_tasks
        ) if use_parallel_execution else None
        
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """构建工作流图"""
        workflow = StateGraph(WorkflowState)

        workflow.add_node("plan", self._plan_node)
        
        if self.use_parallel_execution:
            workflow.add_node("execute_tasks_parallel", self._execute_tasks_parallel_node)
        else:
            workflow.add_node("execute_task", self._execute_task_node)
        
        workflow.add_node("generate_report", self._generate_report_node)

        workflow.set_entry_point("plan")
        
        if self.use_parallel_execution:
            workflow.add_edge("plan", "execute_tasks_parallel")
            workflow.add_edge("execute_tasks_parallel", "generate_report")
        else:
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
        logger.info(f"[WorkflowParallel] Executing plan node for workflow {state['workflow_id']}")

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
                logger.info(f"[WorkflowParallel] Saved {len(tasks)} tasks to database")
            except Exception as db_error:
                logger.error(f"[WorkflowParallel] Failed to save tasks to database: {db_error}, but continuing workflow execution")

            await self.event_publisher.publish_plan_event(
                workflow_id=state["workflow_id"],
                tasks=task_dicts
            )

            sub_questions = [task.title for task in tasks]
            checklist_items = sub_questions

            logger.info(f"[WorkflowParallel] Plan generated with {len(task_dicts)} tasks")
            return {
                "tasks": task_dicts,
                "current_task_index": 0,
                "task_results": [],
                "sub_questions": sub_questions,
                "checklist_items": checklist_items,
                "retrieved_chunks": [],
                "retrieved_documents": [],
                "citations": [],
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

    async def _execute_tasks_parallel_node(self, state: WorkflowState) -> Dict[str, Any]:
        """并行任务执行节点：同时执行所有任务"""
        workflow_id = state["workflow_id"]
        task_dicts = state["tasks"]
        
        logger.info(f"[WorkflowParallel] Starting parallel execution of {len(task_dicts)} tasks")

        # 构建任务实体列表
        tasks = []
        for task_dict in task_dicts:
            task = Task(
                task_id=task_dict["task_id"],
                workflow_id=workflow_id,
                title=task_dict["title"],
                intent=task_dict["intent"],
                query=task_dict["query"],
                order=task_dict["order"]
            )
            tasks.append(task)

        # 并行执行任务
        try:
            task_results = await self.parallel_executor.execute_tasks_parallel(tasks)
            
            # 更新任务字典状态
            updated_tasks = task_dicts.copy()
            for result in task_results:
                for i, task_dict in enumerate(updated_tasks):
                    if task_dict["task_id"] == result["task_id"]:
                        updated_tasks[i]["status"] = result["status"]
                        break
            
            # 收集检索到的内容
            retrieved_chunks = []
            retrieved_documents = []
            for result in task_results:
                if result.get("sources_summary"):
                    retrieved_chunks.append(result["sources_summary"])
                    retrieved_documents.append({
                        "content": result["sources_summary"],
                        "title": result["title"],
                        "task_id": result["task_id"]
                    })
            
            # 批量更新数据库
            try:
                await self._update_tasks_batch(workflow_id, task_results)
            except Exception as db_error:
                logger.error(f"[WorkflowParallel] Failed to update tasks in database: {db_error}")
            
            logger.info(f"[WorkflowParallel] Parallel execution complete")
            
            return {
                "tasks": updated_tasks,
                "task_results": task_results,
                "retrieved_chunks": retrieved_chunks,
                "retrieved_documents": retrieved_documents,
                "updated_at": get_current_utc_time()
            }
            
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

    async def _update_tasks_batch(self, workflow_id: str, task_results: List[Dict[str, Any]]):
        """批量更新任务状态到数据库"""
        try:
            for result in task_results:
                task = await self.task_repository.find_by_id(result["task_id"])
                if task:
                    if result["status"] == "completed":
                        task.complete(result["summary"], result["sources_summary"], result["notices"])
                    else:
                        task.fail(result.get("error", "Unknown error"))
                    await self.task_repository.update(task)
            logger.info(f"[WorkflowParallel] Batch updated {len(task_results)} tasks in database")
        except Exception as e:
            logger.error(f"[WorkflowParallel] Batch update failed: {str(e)}")
            raise

    async def _execute_task_node(self, state: WorkflowState) -> Dict[str, Any]:
        """任务执行节点：执行单个任务（原始串行版本）"""
        current_index = state["current_task_index"]
        tasks = state["tasks"]

        if current_index >= len(tasks):
            return state

        current_task = tasks[current_index]
        logger.info(f"[WorkflowParallel] Executing task {current_index + 1}/{len(tasks)}: {current_task['title']}")

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
                    logger.info(f"[WorkflowParallel] Task {current_task['task_id']} status updated to completed in database")
                else:
                    logger.warning(f"[WorkflowParallel] Task {current_task['task_id']} not found in database, skipping status update")
            except Exception as db_error:
                logger.error(f"[WorkflowParallel] Failed to update task {current_task['task_id']} status in database: {db_error}")

            logger.info(f"[WorkflowParallel] Task {current_index + 1} completed")

            retrieved_chunks = state.get("retrieved_chunks", [])
            retrieved_documents = state.get("retrieved_documents", [])

            if sources_summary:
                retrieved_chunks.append(sources_summary)
                retrieved_documents.append({
                    "content": sources_summary,
                    "title": current_task["title"],
                    "task_id": current_task["task_id"]
                })

            return {
                "tasks": tasks,
                "current_task_index": current_index + 1,
                "task_results": state["task_results"] + [task_result],
                "retrieved_chunks": retrieved_chunks,
                "retrieved_documents": retrieved_documents,
                "updated_at": get_current_utc_time()
            }
        except Exception as e:
            logger.error(f"[WorkflowParallel] Task execution failed: {str(e)}")
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
                    logger.info(f"[WorkflowParallel] Task {current_task['task_id']} status updated to failed in database")
                else:
                    logger.warning(f"[WorkflowParallel] Task {current_task['task_id']} not found in database, skipping status update")
            except Exception as db_error:
                logger.error(f"[WorkflowParallel] Failed to update task {current_task['task_id']} failed status in database: {db_error}")

            return {
                "tasks": tasks,
                "current_task_index": current_index + 1,
                "updated_at": get_current_utc_time()
            }

    def _should_continue(self, state: WorkflowState) -> str:
        """判断是否继续执行下一个任务（用于串行版本）"""
        if state.get("error"):
            return "generate_report"

        current_index = state["current_task_index"]
        tasks = state["tasks"]

        if current_index >= len(tasks):
            return "generate_report"
        return "continue"

    async def _generate_report_node(self, state: WorkflowState) -> Dict[str, Any]:
        """报告生成节点：生成最终报告"""
        logger.info(f"[WorkflowParallel] Generating report for workflow {state['workflow_id']}")

        tasks = state.get("tasks", [])
        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t.get("status") == "completed")
        failed_tasks = sum(1 for t in tasks if t.get("status") == "failed")

        logger.info(f"[WorkflowParallel] Task summary: {completed_tasks}/{total_tasks} tasks completed, {failed_tasks} failed")

        task_summary = {
            "total": total_tasks,
            "completed": completed_tasks,
            "failed": failed_tasks
        }

        completion_rate = completed_tasks / total_tasks if total_tasks > 0 else 0

        if completion_rate <= 0.5:
            logger.warning(
                f"[WorkflowParallel] Completion rate {completion_rate:.1%} <= 50%, skipping report generation. Completed {completed_tasks}/{total_tasks} tasks"
            )
            return {
                "report_content": None,
                "report_url": None,
                "workflow_status": "all_failed" if failed_tasks == total_tasks else "partial_failed",
                "task_summary": task_summary,
                "updated_at": get_current_utc_time()
            }

        logger.info(
            f"[WorkflowParallel] Completion rate {completion_rate:.1%} > 50%, proceeding with report generation"
        )

        retrieved_chunks = state.get("retrieved_chunks", [])
        sub_questions = state.get("sub_questions", [])
        checklist_items = state.get("checklist_items", sub_questions)
        retrieved_documents = state.get("retrieved_documents", [])
        citations = state.get("citations", [])

        report_generated = False
        report_content = None
        report_url = None
        report_error = None
        evaluation_id = None

        try:
            logger.info(f"[WorkflowParallel] Starting report generation for workflow {state['workflow_id']}")
            workflow_id = state["workflow_id"]

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

            logger.info(f"[WorkflowParallel] Report generated successfully: {len(report_content) if report_content else 0} characters")

            try:
                logger.info(f"[WorkflowParallel] Saving report to storage")
                report_content_bytes = report.content.encode("utf-8")
                report_filename = f"{state['workflow_id']}.md"
                report_url = await self.object_storage.upload_object(
                    bucket_name="reports",
                    object_name=report_filename,
                    data=report_content_bytes,
                    content_type="text/markdown"
                )
                logger.info(f"[WorkflowParallel] Report saved to storage: {report_url}")
            except Exception as storage_error:
                logger.error(f"[WorkflowParallel] Failed to save report to storage: {storage_error}")
                report_url = f"/reports/{state['workflow_id']}"

            await self.event_publisher.publish_result_event(
                workflow_id=state["workflow_id"],
                report_url=report_url
            )

            if report_generated:
                try:
                    logger.info(f"[WorkflowParallel] Creating evaluation record for workflow {state['workflow_id']}")
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
                            checklist_items=checklist_items,
                            retrieved_documents=retrieved_documents,
                            citations=citations,
                            evaluation_service=self.evaluation_service,
                            evaluation_orchestrator=self.evaluation_orchestrator
                        )
                    )
                    logger.info(f"[WorkflowParallel] Async evaluation task triggered: {evaluation_id}")
                except Exception as eval_error:
                    logger.error(f"[WorkflowParallel] Failed to trigger evaluation: {str(eval_error)}")

        except Exception as e:
            report_error = str(e)
            logger.error(f"[WorkflowParallel] Report generation failed: {report_error}")

            # 尝试使用已有的任务摘要生成最小化报告作为降级方案
            try:
                logger.warning(f"[WorkflowParallel] Attempting minimal report generation as fallback")
                minimal_report = await self._generate_minimal_report(state)
                if minimal_report:
                    report_content = minimal_report
                    report_generated = True
                    logger.info(f"[WorkflowParallel] Minimal report generated successfully")

                    # 保存简化报告
                    try:
                        report_content_bytes = report_content.encode("utf-8")
                        report_filename = f"{state['workflow_id']}.md"
                        report_url = await self.object_storage.upload_object(
                            bucket_name="reports",
                            object_name=report_filename,
                            data=report_content_bytes,
                            content_type="text/markdown"
                        )
                        logger.info(f"[WorkflowParallel] Minimal report saved to storage: {report_url}")
                        await self.event_publisher.publish_result_event(
                            workflow_id=state["workflow_id"],
                            report_url=report_url
                        )
                    except Exception as storage_error:
                        logger.error(f"[WorkflowParallel] Failed to save minimal report: {storage_error}")
            except Exception as fallback_error:
                logger.error(f"[WorkflowParallel] Minimal report generation failed: {fallback_error}")

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

        logger.info(f"[WorkflowParallel] Workflow completed with status: {workflow_status}")

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
        """生成最小化报告作为降级方案"""
        try:
            topic = state["topic"]
            tasks = state.get("tasks", [])

            report_parts = [f"# {topic}", "", "## 任务摘要", ""]

            for task in tasks:
                if task.get("status") == "completed":
                    report_parts.append(f"### {task.get('title', 'Untitled')}")
                    task_results = state.get("task_results", [])
                    for result in task_results:
                        if result.get("task_id") == task.get("task_id"):
                            summary = result.get("summary", "")
                            if summary:
                                report_parts.append(f"{summary[:200]}...")
                            break
                    report_parts.append("")

            report_parts.append("---")
            report_parts.append("*Note: This is a minimal report due to full report generation failure.*")

            return "\n".join(report_parts)
        except Exception as e:
            logger.error(f"[WorkflowParallel] Minimal report generation failed: {e}")
            return ""

    @property
    def graph(self):
        """获取编译后的工作流图"""
        return self._graph
