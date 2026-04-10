from functools import lru_cache
from sqlalchemy.orm import Session

from infrastructure.db.session import SessionLocal
from infrastructure.db.repositories.workflow_repository_impl import WorkflowRepositoryImpl
from infrastructure.db.repositories.task_repository_impl import TaskRepositoryImpl
from infrastructure.sse.manager import SSEConnectionManager

from domain.repositories.workflow_repository import WorkflowRepository
from domain.repositories.task_repository import TaskRepository

from application.application_services.research_application_service import ResearchApplicationService


@lru_cache()
def get_sse_manager():
    return SSEConnectionManager()


def get_workflow_repository(db: Session):
    return WorkflowRepositoryImpl(db)


def get_task_repository(db: Session):
    return TaskRepositoryImpl(db)


def create_research_application_service(db: Session):
    workflow_repository = get_workflow_repository(db)
    task_repository = get_task_repository(db)
    return ResearchApplicationService(
        workflow_repository=workflow_repository,
        task_repository=task_repository
    )
