from functools import lru_cache
from sqlalchemy.orm import Session

from infrastructure.db.session import SessionLocal
from infrastructure.db.repositories.workflow_repository_impl import WorkflowRepositoryImpl
from infrastructure.db.repositories.task_repository_impl import TaskRepositoryImpl
from infrastructure.db.repositories.evaluation_repository_impl import EvaluationRepositoryImpl
from infrastructure.sse.manager import SSEConnectionManager
from infrastructure.llm.factory import get_llm_client
from infrastructure.evaluation.orchestrator import EvaluationOrchestrator

from domain.repositories.workflow_repository import WorkflowRepository
from domain.repositories.task_repository import TaskRepository
from domain.repositories.evaluation_repository import EvaluationRepository
from domain.domain_services.evaluation_service import EvaluationService

from application.application_services.research_application_service import ResearchApplicationService


@lru_cache()
def get_sse_manager():
    return SSEConnectionManager()


def get_workflow_repository(db: Session):
    return WorkflowRepositoryImpl(db)


def get_task_repository(db: Session):
    return TaskRepositoryImpl(db)


def get_evaluation_repository(db: Session):
    return EvaluationRepositoryImpl(db)


@lru_cache()
def get_evaluation_orchestrator():
    llm_client = get_llm_client()
    return EvaluationOrchestrator(llm_client)


def create_evaluation_service(db: Session):
    evaluation_repository = get_evaluation_repository(db)
    return EvaluationService(evaluation_repository)


def create_research_application_service(db: Session):
    workflow_repository = get_workflow_repository(db)
    task_repository = get_task_repository(db)
    evaluation_service = create_evaluation_service(db)
    evaluation_orchestrator = get_evaluation_orchestrator()
    return ResearchApplicationService(
        workflow_repository=workflow_repository,
        task_repository=task_repository,
        evaluation_service=evaluation_service,
        evaluation_orchestrator=evaluation_orchestrator
    )
