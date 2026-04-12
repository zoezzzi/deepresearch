from typing import List, Dict, Any
import uuid
from domain.agents.plan_agent import PlanAgent
from domain.entities.task import Task
from domain.value_objects.task_id import TaskId
from domain.value_objects.workflow_id import WorkflowId
from domain.value_objects.task_intent import TaskIntent
from domain.value_objects.search_query import SearchQuery
from common.logger import logger


class ResearchPlanService:
    def __init__(self, plan_agent: PlanAgent):
        self.plan_agent = plan_agent

    async def generate_tasks(
        self,
        workflow_id: WorkflowId,
        topic: str,
        description: str = ""
    ) -> List[Task]:
        logger.info(f"[ResearchPlanService] Generating tasks for workflow: {workflow_id.value}")
        
        try:
            task_data_list = await self.plan_agent.execute(topic, description)
            tasks = []
            
            for task_data in task_data_list:
                task_id = TaskId(str(uuid.uuid4()))
                task = Task(
                    task_id=task_id,
                    workflow_id=workflow_id,
                    title=task_data.get("title", "Untitled Task"),
                    intent=TaskIntent(task_data.get("intent", f"Research about {topic}")),
                    query=SearchQuery(task_data.get("query", topic)),
                    order=task_data.get("order", len(tasks) + 1)
                )
                tasks.append(task)
            
            logger.info(f"[ResearchPlanService] Generated {len(tasks)} tasks")
            return tasks
        except Exception as e:
            logger.error(f"[ResearchPlanService] Failed to generate tasks: {str(e)}")
            raise
