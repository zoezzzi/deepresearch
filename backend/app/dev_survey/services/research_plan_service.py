import uuid

from app.dev_survey.agents import PlanAgent
from app.dev_survey.models.models import Task
from harness.logger import logger


class ResearchPlanService:
    def __init__(self, plan_agent: PlanAgent):
        self.plan_agent = plan_agent

    async def generate_tasks(
        self, workflow_id: str, topic: str, description: str = ""
    ) -> list[Task]:
        logger.info(f"[ResearchPlanService] Generating tasks for workflow: {workflow_id}")

        try:
            task_data_list = await self.plan_agent.execute(topic, description)
            tasks = []
            order_to_task_id = {}

            for task_data in task_data_list:
                task_id = str(uuid.uuid4())
                order = task_data.get("order", len(tasks) + 1)
                order_to_task_id[order] = task_id
                task = Task(
                    task_id=task_id,
                    workflow_id=workflow_id,
                    title=task_data.get("title", "Untitled Task"),
                    intent=task_data.get("intent", f"Research about {topic}"),
                    query=task_data.get("query", topic),
                    order=order,
                )
                tasks.append(task)

            for i, task_data in enumerate(task_data_list):
                raw_deps = task_data.get("depends_on") or []
                task = tasks[i]
                mapped_deps = []
                for dep_order in raw_deps:
                    mapped_id = order_to_task_id.get(dep_order)
                    if mapped_id:
                        mapped_deps.append(mapped_id)
                    else:
                        logger.warning(
                            f"[ResearchPlanService] Task '{task.task_id}' depends_on "
                            f"unknown order {dep_order}, skipping"
                        )
                task.depends_on = mapped_deps

            logger.info(f"[ResearchPlanService] Generated {len(tasks)} tasks")
            return tasks
        except Exception as e:
            logger.error(f"[ResearchPlanService] Failed to generate tasks: {str(e)}")
            raise
