from typing import List, Optional
from app.infrastructure.db.models import TaskModel
from app.infrastructure.db.repositories.base_task_repository import BaseTaskRepository
from app.research_assistant.repositories import TaskRepository
from app.research_assistant.models.models import Task
from app.research_assistant.models.enums import TaskStatus
from harness.logger import logger


class ResearchAssistantTaskRepositoryImpl(BaseTaskRepository, TaskRepository):
    def _to_domain_entity(self, model: TaskModel) -> Task:
        return Task(
            task_id=str(model.task_id),
            workflow_id=str(model.workflow_id),
            title=model.title,
            intent=model.intent,
            query=model.query,
            order=model.order,
            status=TaskStatus(model.status) if isinstance(model.status, str) else model.status,
            summary=model.summary,
            sources_summary=model.sources_summary,
            notices=model.notices,
            created_at=model.created_at,
            updated_at=model.updated_at,
            started_at=model.started_at,
            completed_at=model.completed_at
        )

    def _to_persistence_model(self, task: Task) -> TaskModel:
        return TaskModel(
            task_id=task.task_id,
            workflow_id=task.workflow_id,
            title=task.title,
            intent=task.intent,
            query=task.query,
            order=task.order,
            status=task.status,
            summary=task.summary,
            sources_summary=task.sources_summary,
            notices=task.notices,
            created_at=task.created_at,
            updated_at=task.updated_at,
            started_at=task.started_at,
            completed_at=task.completed_at
        )
