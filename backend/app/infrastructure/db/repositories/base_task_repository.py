from abc import ABC, abstractmethod
from typing import List, Optional, Any
from sqlalchemy.orm import Session
from app.infrastructure.db.models import TaskModel
from app.infrastructure.db.session import with_db_retry
from harness.logger import logger


class BaseTaskRepository(ABC):
    def __init__(self, db_session: Session):
        self.db_session = db_session

    @abstractmethod
    def _to_domain_entity(self, model: TaskModel) -> Any:
        pass

    @abstractmethod
    def _to_persistence_model(self, task: Any) -> TaskModel:
        pass

    async def save(self, task: Any) -> None:
        logger.info(f"Saving task: {task.task_id}")
        model = self._to_persistence_model(task)

        @with_db_retry(max_attempts=3)
        def _save():
            self.db_session.add(model)
            self.db_session.flush()

        try:
            _save()
            self.db_session.commit()
        except Exception:
            self.db_session.rollback()
            raise

    async def save_batch(self, tasks: List[Any]) -> None:
        logger.info(f"Saving batch of {len(tasks)} tasks")
        models = [self._to_persistence_model(task) for task in tasks]

        @with_db_retry(max_attempts=3)
        def _save_batch():
            self.db_session.bulk_save_objects(models)
            self.db_session.flush()

        try:
            _save_batch()
            self.db_session.commit()
        except Exception:
            self.db_session.rollback()
            raise

    async def find_by_id(self, task_id: str) -> Optional[Any]:
        logger.info(f"Finding task by id: {task_id}")

        @with_db_retry(max_attempts=3)
        def _find():
            model = self.db_session.query(TaskModel).filter_by(task_id=task_id).first()
            if not model:
                return None
            return self._to_domain_entity(model)

        try:
            result = _find()
            self.db_session.commit()
            return result
        except Exception:
            self.db_session.rollback()
            raise

    async def find_by_ids(self, task_ids: List[str]) -> List[Any]:
        """批量查询 task，一次查询替代 N 次 find_by_id"""
        if not task_ids:
            return []
        logger.info(f"Finding tasks by ids: {len(task_ids)} tasks")

        @with_db_retry(max_attempts=3)
        def _find():
            models = self.db_session.query(TaskModel).filter(
                TaskModel.task_id.in_(task_ids)
            ).all()
            return [self._to_domain_entity(model) for model in models]

        try:
            result = _find()
            self.db_session.commit()
            return result
        except Exception:
            self.db_session.rollback()
            raise

    async def find_by_workflow_id(self, workflow_id: str) -> List[Any]:
        logger.info(f"Finding tasks by workflow id: {workflow_id}")

        @with_db_retry(max_attempts=3)
        def _find():
            models = self.db_session.query(TaskModel).filter_by(workflow_id=workflow_id).order_by(TaskModel.order).all()
            return [self._to_domain_entity(model) for model in models]

        try:
            result = _find()
            self.db_session.commit()
            return result
        except Exception:
            self.db_session.rollback()
            raise

    async def update(self, task: Any) -> None:
        logger.info(f"Updating task: {task.task_id}")

        @with_db_retry(max_attempts=3)
        def _update():
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

        try:
            _update()
            self.db_session.commit()
        except Exception:
            self.db_session.rollback()
            raise

    async def update_batch(self, tasks: List[Any]) -> None:
        logger.info(f"Updating batch of {len(tasks)} tasks")

        from app.common.utils.time_utils import get_current_utc_time

        @with_db_retry(max_attempts=3)
        def _update_batch():
            for task in tasks:
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
                    model.updated_at = get_current_utc_time()
                    model.started_at = task.started_at
                    model.completed_at = task.completed_at

            self.db_session.flush()

        try:
            _update_batch()
            self.db_session.commit()
        except Exception:
            self.db_session.rollback()
            raise

        logger.info(f"Batch update of {len(tasks)} tasks completed")
