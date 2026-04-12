from typing import Tuple
from tenacity import stop_after_attempt, wait_exponential, retry_if_exception_type
from tenacity.asyncio import AsyncRetrying
from domain.agents.search_agent import SearchAgent
from domain.agents.summarizer_agent import SummarizerAgent
from domain.entities.task import Task
from domain.value_objects.task_summary import TaskSummary
from domain.value_objects.sources_summary import SourcesSummary
from domain.value_objects.notices import Notices
from common.logger import logger


class TaskExecutionService:
    def __init__(self, search_agent: SearchAgent, summarizer_agent: SummarizerAgent):
        self.search_agent = search_agent
        self.summarizer_agent = summarizer_agent

    async def execute_task(
        self,
        task: Task
    ) -> Tuple[TaskSummary, SourcesSummary, Notices]:
        logger.info(f"[TaskExecutionService] Executing task: {task.task_id.value}")
        
        # 使用异步重试机制
        retrying = AsyncRetrying(
            stop=stop_after_attempt(2),
            wait=wait_exponential(multiplier=1, min=2, max=5),
            retry=retry_if_exception_type((ConnectionError,))
        )
        
        async for attempt in retrying:
            with attempt:
                try:
                    search_results = await self.search_agent.execute(task.query)
                    
                    summary, sources_summary, notices = await self.summarizer_agent.execute(
                        task.intent,
                        search_results
                    )
                    
                    logger.info(f"[TaskExecutionService] Task executed successfully: {task.task_id.value}")
                    return summary, sources_summary, notices
                except Exception as e:
                    logger.error(f"[TaskExecutionService] Failed to execute task {task.task_id.value}: {str(e)}")
                    raise
