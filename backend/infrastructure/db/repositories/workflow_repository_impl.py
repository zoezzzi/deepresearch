from typing import Optional
from sqlalchemy.orm import Session
from core.repositories import WorkflowRepository
from core.models import Workflow, Task
from core.models.enums import WorkflowStatus
from infrastructure.db.models import WorkflowModel, TaskModel
from common.logger import logger


class WorkflowRepositoryImpl(WorkflowRepository):
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def _to_domain_entity(self, model: WorkflowModel) -> Workflow:
        workflow = Workflow(
            workflow_id=model.workflow_id,
            topic=model.topic,
            description=model.description,
            status=WorkflowStatus(model.status) if isinstance(model.status, str) else model.status,
            report_url=model.report_url,
            created_at=model.created_at,
            updated_at=model.updated_at,
            started_at=model.started_at,
            completed_at=model.completed_at
        )
        for task_model in model.tasks:
            task = self._task_to_domain_entity(task_model)
            workflow.add_task(task)
        return workflow

    def _task_to_domain_entity(self, model: TaskModel) -> Task:
        from core.models.enums import TaskStatus

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

    def _to_persistence_model(self, workflow: Workflow) -> WorkflowModel:
        return WorkflowModel(
            workflow_id=workflow.workflow_id,
            topic=workflow.topic,
            description=workflow.description,
            status=workflow.status,
            report_url=workflow.report_url,
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
            started_at=workflow.started_at,
            completed_at=workflow.completed_at
        )

    async def save(self, workflow: Workflow) -> None:
        logger.info(f"Saving workflow: {workflow.workflow_id}")
        model = self._to_persistence_model(workflow)
        self.db_session.add(model)
        self.db_session.flush()
        self.db_session.commit()

    async def find_by_id(self, workflow_id: str) -> Optional[Workflow]:
        workflow_id_str = str(workflow_id)
        model = self.db_session.query(WorkflowModel).filter_by(workflow_id=workflow_id_str).first()
        if not model:
            return None
        return self._to_domain_entity(model)

    async def update(self, workflow: Workflow) -> None:
        logger.info(f"Updating workflow: {workflow.workflow_id}")
        workflow_id_str = str(workflow.workflow_id)
        model = self.db_session.query(WorkflowModel).filter_by(workflow_id=workflow_id_str).first()
        if model:
            model.topic = workflow.topic
            model.description = workflow.description
            model.status = workflow.status
            model.report_url = workflow.report_url
            model.updated_at = workflow.updated_at
            model.started_at = workflow.started_at
            model.completed_at = workflow.completed_at
            self.db_session.flush()
            self.db_session.commit()
