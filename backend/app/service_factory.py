from functools import lru_cache
from sqlalchemy.orm import Session

from app.infrastructure.db.session import SessionLocal
from app.infrastructure.db.repositories.workflow_repository_impl import WorkflowRepositoryImpl
from app.infrastructure.db.repositories.task_repository_impl import TaskRepositoryImpl
from app.infrastructure.db.repositories.evaluation_repository_impl import EvaluationRepositoryImpl
from harness.events.manager import SSEConnectionManager
from harness.llm.factory import get_llm_client
from harness.evaluation.orchestrator import EvaluationOrchestrator

from app.research_assistant.repositories import (
    WorkflowRepository,
    TaskRepository,
    EvaluationRepository
)
from app.research_assistant.services import EvaluationService, ResearchService

from app.dev_survey.repositories import (
    WorkflowRepository as DevSurveyWorkflowRepository,
    TaskRepository as DevSurveyTaskRepository,
    EvaluationRepository as DevSurveyEvaluationRepository
)
from app.dev_survey.services import (
    EvaluationService as DevSurveyEvaluationService, 
    ResearchService as DevSurveyResearchService
)


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
def get_research_assistant_evaluation_orchestrator():
    from app.scenarios.research_assistant.evaluation_config import get_evaluators, get_weights
    llm_client = get_llm_client()
    evaluators = get_evaluators(llm_client)
    weights = get_weights()
    return EvaluationOrchestrator(evaluators=evaluators, weights=weights)


@lru_cache()
def get_dev_survey_evaluation_orchestrator():
    from app.scenarios.dev_survey.evaluation_config import get_evaluators, get_weights
    llm_client = get_llm_client()
    evaluators = get_evaluators(llm_client)
    weights = get_weights()
    return EvaluationOrchestrator(evaluators=evaluators, weights=weights)


@lru_cache()
def get_evaluation_orchestrator():
    """获取评估编排器（默认使用 research_assistant 配置）"""
    return get_research_assistant_evaluation_orchestrator()


def create_evaluation_service(db: Session):
    evaluation_repository = get_evaluation_repository(db)
    return EvaluationService(evaluation_repository)


def create_research_service(db: Session, report_url_prefix: str):
    workflow_repository = get_workflow_repository(db)
    task_repository = get_task_repository(db)
    evaluation_service = create_evaluation_service(db)
    evaluation_orchestrator = get_research_assistant_evaluation_orchestrator()
    return ResearchService(
        workflow_repository=workflow_repository,
        task_repository=task_repository,
        evaluation_service=evaluation_service,
        evaluation_orchestrator=evaluation_orchestrator,
        report_url_prefix=report_url_prefix
    )


def create_dev_survey_service(db: Session, report_url_prefix: str):
    workflow_repository = get_workflow_repository(db)
    task_repository = get_task_repository(db)
    evaluation_service = DevSurveyEvaluationService(get_evaluation_repository(db))
    evaluation_orchestrator = get_dev_survey_evaluation_orchestrator()
    return DevSurveyResearchService(
        workflow_repository=workflow_repository,
        task_repository=task_repository,
        evaluation_service=evaluation_service,
        evaluation_orchestrator=evaluation_orchestrator,
        report_url_prefix=report_url_prefix
    )
