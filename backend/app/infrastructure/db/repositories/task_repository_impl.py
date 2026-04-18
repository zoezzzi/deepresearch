from typing import List, Optional
from sqlalchemy.orm import Session
from app.research_assistant.repositories import TaskRepository
from app.research_assistant.models.models import Task
from app.infrastructure.db.models import TaskModel
from harness.logger import logger


class TaskRepositoryImpl(TaskRepository):
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def _to_domain_entity(self, model: TaskModel) -> Task:
        from app.research_assistant.models.enums import TaskStatus

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

    async def save(self, task: Task) -> None:
        logger.info(f"Saving task: {task.task_id}")
        model = self._to_persistence_model(task)
        self.db_session.add(model)
        self.db_session.flush()
        self.db_session.commit()

    async def save_batch(self, tasks: List[Task]) -> None:
        logger.info(f"Saving batch of {len(tasks)} tasks")
        models = [self._to_persistence_model(task) for task in tasks]
        self.db_session.bulk_save_objects(models)
        self.db_session.flush()
        self.db_session.commit()

    async def find_by_id(self, task_id: str) -> Optional[Task]:
        logger.info(f"Finding task by id: {task_id}")
        model = self.db_session.query(TaskModel).filter_by(task_id=task_id).first()
        if not model:
            return None
        return self._to_domain_entity(model)

    async def find_by_workflow_id(self, workflow_id: str) -> List[Task]:
        logger.info(f"Finding tasks by workflow id: {workflow_id}")
        models = self.db_session.query(TaskModel).filter_by(workflow_id=workflow_id).order_by(TaskModel.order).all()
        return [self._to_domain_entity(model) for model in models]

    async def update(self, task: Task) -> None:
        logger.info(f"Updating task: {task.task_id}")
        model = self.db_session.query(TaskModel).filter_by(task_id=task.task_id).first()
        if model:
            model.title = task.title
            model.intent = task.intent
            model.query = task.query
            model.order = task.order
            model.status = task.status
            model.summary = task.summary
            model.sources_summary = task.sources_summary
            model.notices = task.notices
            model.updated_at = task.updated_at
            model.started_at = task.started_at
            model.completed_at = task.completed_at
            self.db_session.flush()
            self.db_session.commit()
