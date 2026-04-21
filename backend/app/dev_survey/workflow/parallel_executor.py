"""
并行任务执行器

支持任务并行执行，提高工作流效率
"""
import asyncio
from typing import List, Dict, Any, Optional
from harness.logger import logger
from app.dev_survey.services.task_execution_service import TaskExecutionService
from app.dev_survey.models.models import Task
from app.dev_survey.events.event_publisher import EventPublisher


class ParallelTaskExecutor:
    """
    并行任务执行器
    
    管理多个任务的并行执行，控制并发度，处理错误
    """
    
    def __init__(
        self,
        task_execution_service: TaskExecutionService,
        event_publisher: EventPublisher,
        max_concurrent_tasks: int = 3
    ):
        self.task_execution_service = task_execution_service
        self.event_publisher = event_publisher
        self.max_concurrent_tasks = max_concurrent_tasks
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        logger.info(f"[ParallelExecutor] Initialized with max_concurrent_tasks={max_concurrent_tasks}")
    
    async def execute_single_task(self, task: Task) -> Dict[str, Any]:
        """
        执行单个任务（线程安全）
        
        Args:
            task: 任务对象
        
        Returns:
            任务结果字典
        """
        async with self.semaphore:
            logger.info(f"[ParallelExecutor] Executing task: {task.title}")
            
            try:
                await self.event_publisher.publish_task_start_event(
                    workflow_id=task.workflow_id,
                    task_id=task.task_id,
                    task_title=task.title
                )
                
                summary, sources_summary, notices = await self.task_execution_service.execute_task(task)
                
                task_result = {
                    "task_id": task.task_id,
                    "title": task.title,
                    "status": "completed",
                    "summary": summary,
                    "sources_summary": sources_summary,
                    "notices": notices
                }
                
                await self.event_publisher.publish_task_complete_event(
                    workflow_id=task.workflow_id,
                    task_id=task.task_id,
                    task_title=task.title,
                    summary=summary,
                    sources_summary=sources_summary,
                    notices=notices
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
                    "notices": None
                }
                
                await self.event_publisher.publish_error_event(
                    workflow_id=task.workflow_id,
                    message=f"Task {task.title} failed: {str(e)}"
                )
                
                return task_result
    
    async def execute_tasks_parallel(self, tasks: List[Task]) -> List[Dict[str, Any]]:
        """
        并行执行多个任务
        
        Args:
            tasks: 任务列表
        
        Returns:
            任务结果列表
        """
        logger.info(f"[ParallelExecutor] Starting parallel execution of {len(tasks)} tasks")
        
        # 创建所有任务的执行协程
        tasks_coroutines = [self.execute_single_task(task) for task in tasks]
        
        # 使用 gather 并行执行所有任务
        results = await asyncio.gather(*tasks_coroutines, return_exceptions=False)
        
        # 统计执行结果
        completed_count = sum(1 for r in results if r.get("status") == "completed")
        failed_count = sum(1 for r in results if r.get("status") == "failed")
        
        logger.info(f"[ParallelExecutor] Parallel execution complete: {completed_count} completed, {failed_count} failed")
        
        return results
    
    async def execute_tasks_parallel_with_timeout(
        self,
        tasks: List[Task],
        total_timeout: Optional[float] = None
    ) -> List[Dict[str, Any]]:
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
                    self.execute_tasks_parallel(tasks),
                    timeout=total_timeout
                )
            except asyncio.TimeoutError:
                logger.error(f"[ParallelExecutor] Parallel execution timed out after {total_timeout} seconds")
                raise
        else:
            return await self.execute_tasks_parallel(tasks)
