from typing import Optional
from app.infrastructure.db.models import WorkflowModel, TaskModel
from app.infrastructure.db.repositories.base_workflow_repository import BaseWorkflowRepository
from app.dev_survey.repositories import WorkflowRepository
from app.dev_survey.models.models import Workflow, Task
from harness.logger import logger


class DevSurveyWorkflowRepositoryImpl(BaseWorkflowRepository, WorkflowRepository):
    def _to_domain_entity(self, model: WorkflowModel) -> Workflow:
        workflow = Workflow(
            workflow_id=model.workflow_id,
            topic=model.topic,
            scenario_id=model.scenario_id,
            description=model.description,
            status=model.status,  # 直接使用字符串
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
        status_value = model.status
        if hasattr(status_value, 'value'):
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
            completed_at=model.completed_at
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
            completed_at=workflow.completed_at
        )
