from app.dev_survey.models.models import Task
from app.dev_survey.repositories import TaskRepository
from app.infrastructure.db.models import TaskModel
from app.infrastructure.db.repositories.base_task_repository import BaseTaskRepository


class DevSurveyTaskRepositoryImpl(BaseTaskRepository, TaskRepository):
    def _to_domain_entity(self, model: TaskModel) -> Task:
        status_value = model.status
        if hasattr(status_value, "value"):
            status_value = status_value.value

        return Task(
            task_id=str(model.task_id),
            workflow_id=str(model.workflow_id),
            title=model.title,
            intent=model.intent,
            query=model.query,
            order=model.order,
            depends_on=model.depends_on or [],
            status=str(status_value),
            summary=model.summary,
            sources_summary=model.sources_summary,
            notices=model.notices,
            created_at=model.created_at,
            updated_at=model.updated_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
        )

    def _to_persistence_model(self, task: Task) -> TaskModel:
        return TaskModel(
            task_id=task.task_id,
            workflow_id=task.workflow_id,
            title=task.title,
            intent=task.intent,
            query=task.query,
            order=task.order,
            depends_on=task.depends_on,
            status=task.status,
            summary=task.summary,
            sources_summary=task.sources_summary,
            notices=task.notices,
            created_at=task.created_at,
            updated_at=task.updated_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
        )
