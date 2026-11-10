from app.infrastructure.db.models import TaskModel, WorkflowModel
from app.infrastructure.db.repositories.base_workflow_repository import BaseWorkflowRepository
from app.research_assistant.models.enums import TaskStatus, WorkflowStatus
from app.research_assistant.models.models import Task, Workflow
from app.research_assistant.repositories import WorkflowRepository


class ResearchAssistantWorkflowRepositoryImpl(BaseWorkflowRepository, WorkflowRepository):
    def _to_domain_entity(self, model: WorkflowModel) -> Workflow:
        workflow = Workflow(
            workflow_id=model.workflow_id,
            topic=model.topic,
            scenario_id=model.scenario_id,
            description=model.description,
            status=WorkflowStatus(model.status) if isinstance(model.status, str) else model.status,
            report_url=model.report_url,
            created_at=model.created_at,
            updated_at=model.updated_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
        )
        for task_model in model.tasks:
            task = self._task_to_domain_entity(task_model)
            workflow.add_task(task)
        return workflow

    def _task_to_domain_entity(self, model: TaskModel) -> Task:
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
            completed_at=model.completed_at,
        )

    def _to_persistence_model(self, workflow: Workflow) -> WorkflowModel:
        return WorkflowModel(
            workflow_id=workflow.workflow_id,
            topic=workflow.topic,
            scenario_id=workflow.scenario_id,
            description=workflow.description,
            status=workflow.status,
            report_url=workflow.report_url,
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
            started_at=workflow.started_at,
            completed_at=workflow.completed_at,
        )
