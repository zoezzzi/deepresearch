from functools import lru_cache
from sqlalchemy.orm import Session

from app.infrastructure.db.session import SessionLocal
from app.infrastructure.db.repositories.evaluation_repository_impl import EvaluationRepositoryImpl
from harness.events.manager import SSEConnectionManager
from harness.llm.factory import get_llm_client, clear_llm_client_cache, remove_llm_client
from harness.evaluation.orchestrator import EvaluationOrchestrator

from app.research_assistant.repositories import (
    WorkflowRepository,
    TaskRepository,
    EvaluationRepository,
    ResearchAssistantWorkflowRepositoryImpl,
    ResearchAssistantTaskRepositoryImpl,
)
from app.research_assistant.services import EvaluationService, ResearchService

from app.dev_survey.repositories import (
    WorkflowRepository as DevSurveyWorkflowRepository,
    TaskRepository as DevSurveyTaskRepository,
    EvaluationRepository as DevSurveyEvaluationRepository,
    DevSurveyWorkflowRepositoryImpl,
    DevSurveyTaskRepositoryImpl,
)
from app.dev_survey.services import (
    EvaluationService as DevSurveyEvaluationService,
    ResearchService as DevSurveyResearchService
)
from app.dev_survey.agents import PlanAgent, SearchAgent, SummarizerAgent, GenerateAgent
from app.dev_survey.agents.critic_agent import CriticAgent
from app.dev_survey.events import get_event_publisher
from harness.storage.local_storage import LocalObjectStorage
from harness.observability.trace_service import get_trace_service
from harness.config import get_harness_settings
from langgraph.store.memory import InMemoryStore
from harness.logger import logger

settings = get_harness_settings()


@lru_cache()
def get_sse_manager():
    return SSEConnectionManager()


def get_research_assistant_workflow_repository(db: Session) -> WorkflowRepository:
    return ResearchAssistantWorkflowRepositoryImpl(db)


def get_research_assistant_task_repository(db: Session) -> TaskRepository:
    return ResearchAssistantTaskRepositoryImpl(db)


def get_dev_survey_workflow_repository(db: Session) -> DevSurveyWorkflowRepository:
    return DevSurveyWorkflowRepositoryImpl(db)


def get_dev_survey_task_repository(db: Session) -> DevSurveyTaskRepository:
    return DevSurveyTaskRepositoryImpl(db)


def get_workflow_repository(db: Session) -> WorkflowRepository:
    return get_research_assistant_workflow_repository(db)


def get_task_repository(db: Session) -> TaskRepository:
    return get_research_assistant_task_repository(db)


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
    workflow_repository = get_research_assistant_workflow_repository(db)
    task_repository = get_research_assistant_task_repository(db)
    evaluation_service = create_evaluation_service(db)
    evaluation_orchestrator = get_research_assistant_evaluation_orchestrator()
    return ResearchService(
        workflow_repository=workflow_repository,
        task_repository=task_repository,
        evaluation_service=evaluation_service,
        evaluation_orchestrator=evaluation_orchestrator,
        report_url_prefix=report_url_prefix
    )


# --- DevSurvey 共享组件缓存（每个组件独立懒加载） ---

@lru_cache()
def _get_dev_survey_plan_agent():
    return PlanAgent(get_llm_client())

@lru_cache()
def _get_dev_survey_search_agent():
    return SearchAgent()

@lru_cache()
def _get_dev_survey_summarizer_agent():
    return SummarizerAgent(get_llm_client())

@lru_cache()
def _get_dev_survey_generate_agent():
    return GenerateAgent(get_llm_client())

@lru_cache()
def _get_dev_survey_critic_agent():
    return CriticAgent(get_llm_client())

@lru_cache()
def _get_dev_survey_event_publisher():
    return get_event_publisher()

@lru_cache()
def _get_dev_survey_object_storage():
    return LocalObjectStorage(url_prefix="/dev-research/reports")

@lru_cache()
def _get_dev_survey_trace_service():
    return get_trace_service()

@lru_cache()
def _get_dev_survey_store():
    try:
        from langgraph.store.postgres import AsyncPostgresStore
        return AsyncPostgresStore.from_conn_string(conn_string=settings.DATABASE_URL)
    except Exception as e:
        logger.warning(f"[ServiceFactory] AsyncPostgresStore unavailable: {e}")
        return InMemoryStore()


def create_dev_survey_service(db: Session, report_url_prefix: str):
    workflow_repository = get_dev_survey_workflow_repository(db)
    task_repository = get_dev_survey_task_repository(db)
    evaluation_service = DevSurveyEvaluationService(get_evaluation_repository(db))
    evaluation_orchestrator = get_dev_survey_evaluation_orchestrator()

    return DevSurveyResearchService(
        workflow_repository=workflow_repository,
        task_repository=task_repository,
        evaluation_service=evaluation_service,
        evaluation_orchestrator=evaluation_orchestrator,
        report_url_prefix=report_url_prefix,
        plan_agent_factory=_get_dev_survey_plan_agent,
        search_agent_factory=_get_dev_survey_search_agent,
        summarizer_agent_factory=_get_dev_survey_summarizer_agent,
        generate_agent_factory=_get_dev_survey_generate_agent,
        critic_agent_factory=_get_dev_survey_critic_agent,
        event_publisher_factory=_get_dev_survey_event_publisher,
        object_storage_factory=_get_dev_survey_object_storage,
        trace_service_factory=_get_dev_survey_trace_service,
        store_factory=_get_dev_survey_store,
    )


async def invalidate_llm_client_cache():
    await clear_llm_client_cache()
    _get_dev_survey_plan_agent.cache_clear()
    _get_dev_survey_search_agent.cache_clear()
    _get_dev_survey_summarizer_agent.cache_clear()
    _get_dev_survey_generate_agent.cache_clear()
    _get_dev_survey_critic_agent.cache_clear()
    get_research_assistant_evaluation_orchestrator.cache_clear()
    get_dev_survey_evaluation_orchestrator.cache_clear()
    get_evaluation_orchestrator.cache_clear()
    logger.info("[ServiceFactory] All LLM-related caches invalidated")
