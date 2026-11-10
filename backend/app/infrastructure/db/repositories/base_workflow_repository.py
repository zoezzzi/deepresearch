from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.infrastructure.db.models import TaskModel, WorkflowModel
from harness.db.session import with_db_retry
from harness.logger import logger


class BaseWorkflowRepository(ABC):
    def __init__(self, db_session: Session):
        self.db_session = db_session

    @abstractmethod
    def _to_domain_entity(self, model: WorkflowModel) -> Any:
        pass

    @abstractmethod
    def _task_to_domain_entity(self, model: TaskModel) -> Any:
        pass

    @abstractmethod
    def _to_persistence_model(self, workflow: Any) -> WorkflowModel:
        pass

    async def save(self, workflow: Any) -> None:
        logger.info(f"Saving workflow: {workflow.workflow_id}")
        model = self._to_persistence_model(workflow)

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

    async def find_by_id(self, workflow_id: str) -> Any | None:
        workflow_id_str = str(workflow_id)

        @with_db_retry(max_attempts=3)
        def _find():
            model = (
                self.db_session.query(WorkflowModel)
                .options(joinedload(WorkflowModel.tasks))
                .filter_by(workflow_id=workflow_id_str)
                .first()
            )
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

    async def update(self, workflow: Any) -> None:
        logger.info(f"Updating workflow: {workflow.workflow_id}")
        workflow_id_str = str(workflow.workflow_id)

        @with_db_retry(max_attempts=3)
        def _update():
            model = (
                self.db_session.query(WorkflowModel).filter_by(workflow_id=workflow_id_str).first()
            )
            if model:
                model.topic = workflow.topic
                model.scenario_id = workflow.scenario_id
                model.description = workflow.description
                model.status = workflow.status
                model.report_url = workflow.report_url
                model.updated_at = workflow.updated_at
                model.started_at = workflow.started_at
                model.completed_at = workflow.completed_at
                self.db_session.flush()

        try:
            _update()
            self.db_session.commit()
        except Exception:
            self.db_session.rollback()
            raise
