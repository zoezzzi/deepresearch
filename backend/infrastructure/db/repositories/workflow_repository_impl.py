from typing import Optional
from sqlalchemy.orm import Session
from domain.repositories.workflow_repository import WorkflowRepository
from domain.entities.workflow import Workflow
from domain.entities.task import Task
from domain.value_objects.workflow_id import WorkflowId
from domain.value_objects.workflow_status import WorkflowStatus
from domain.value_objects.report_url import ReportUrl
from infrastructure.db.models import WorkflowModel, TaskModel
from infrastructure.logger import logger


class WorkflowRepositoryImpl(WorkflowRepository):
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def _to_domain_entity(self, model: WorkflowModel) -> Workflow:
        workflow = Workflow(
            workflow_id=WorkflowId(model.workflow_id),
            topic=model.topic,
            description=model.description,
            status=WorkflowStatus(model.status) if isinstance(model.status, str) else model.status,
            report_url=ReportUrl(model.report_url) if model.report_url else None,
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
        from domain.value_objects.task_id import TaskId
        from domain.value_objects.workflow_id import WorkflowId
        from domain.value_objects.task_status import TaskStatus
        from domain.value_objects.task_intent import TaskIntent
        from domain.value_objects.search_query import SearchQuery
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

    def _to_persistence_model(self, workflow: Workflow) -> WorkflowModel:
        return WorkflowModel(
            workflow_id=str(workflow.workflow_id.value),
            topic=workflow.topic,
            description=workflow.description,
            status=workflow.status.value if hasattr(workflow.status, 'value') else str(workflow.status),
            report_url=workflow.report_url.value if workflow.report_url else None,
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
        logger.info(f"Finding workflow by id: {workflow_id}")
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
            model.status = workflow.status.value if hasattr(workflow.status, 'value') else str(workflow.status)
            model.report_url = workflow.report_url.value if workflow.report_url else None
            model.updated_at = workflow.updated_at
            model.started_at = workflow.started_at
            model.completed_at = workflow.completed_at
            self.db_session.flush()
            self.db_session.commit()
