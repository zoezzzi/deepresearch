from typing import List, Optional
from sqlalchemy.orm import Session
from domain.repositories.task_repository import TaskRepository
from domain.entities.task import Task
from infrastructure.db.models import TaskModel
from common.logger import logger


class TaskRepositoryImpl(TaskRepository):
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def _to_domain_entity(self, model: TaskModel) -> Task:
        from domain.value_objects.task_status import TaskStatus
        from domain.value_objects.task_intent import TaskIntent
        from domain.value_objects.search_query import SearchQuery
        from domain.value_objects.task_id import TaskId
        from domain.value_objects.workflow_id import WorkflowId
        from domain.value_objects.task_summary import TaskSummary
        from domain.value_objects.sources_summary import SourcesSummary
        from domain.value_objects.notices import Notices
        
        return Task(
            task_id=TaskId(str(model.task_id)),
            workflow_id=WorkflowId(str(model.workflow_id)),
            title=model.title,
            intent=TaskIntent(model.intent) if isinstance(model.intent, str) else model.intent,
            query=SearchQuery(model.query) if isinstance(model.query, str) else model.query,
            order=model.order,
            status=TaskStatus(model.status) if isinstance(model.status, str) else model.status,
            summary=TaskSummary(model.summary) if model.summary and isinstance(model.summary, str) else model.summary,
            sources_summary=SourcesSummary(model.sources_summary) if model.sources_summary and isinstance(model.sources_summary, str) else model.sources_summary,
            notices=Notices(model.notices) if model.notices and isinstance(model.notices, str) else model.notices,
            created_at=model.created_at,
            updated_at=model.updated_at,
            started_at=model.started_at,
            completed_at=model.completed_at
        )

    def _to_persistence_model(self, task: Task) -> TaskModel:
        return TaskModel(
            task_id=task.task_id.value,
            workflow_id=task.workflow_id.value,
            title=task.title,
            intent=task.intent.value,
            query=task.query.value,
            order=task.order,
            status=task.status,
            summary=task.summary.value if task.summary else None,
            sources_summary=task.sources_summary.value if task.sources_summary else None,
            notices=task.notices.value if task.notices else None,
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
        model = self.db_session.query(TaskModel).filter_by(task_id=task.task_id.value).first()
        if model:
            model.title = task.title
            model.intent = task.intent.value
            model.query = task.query.value
            model.order = task.order
            model.status = task.status
            model.summary = task.summary.value if task.summary else None
            model.sources_summary = task.sources_summary.value if task.sources_summary else None
            model.notices = task.notices.value if task.notices else None
            model.updated_at = task.updated_at
            model.started_at = task.started_at
            model.completed_at = task.completed_at
            self.db_session.flush()
            self.db_session.commit()
