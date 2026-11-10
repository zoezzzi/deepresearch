"""Application dependency-assembly factory.

Centralizes construction of repositories, domain services, the evaluation
orchestrator and scenario-shared components. Functions decorated with
``@lru_cache`` are process-level singletons, so their results must not hold
request-scoped state.
"""

from functools import lru_cache

from sqlalchemy.orm import Session

from app.dev_survey.agents import GenerateAgent, PlanAgent, SearchAgent, SummarizerAgent
from app.dev_survey.agents.critic_agent import CriticAgent
from app.dev_survey.events import get_event_publisher
from app.dev_survey.repositories import (
    DevSurveyTaskRepositoryImpl,
    DevSurveyWorkflowRepositoryImpl,
)
from app.dev_survey.repositories import (
    TaskRepository as DevSurveyTaskRepository,
)
from app.dev_survey.repositories import (
    WorkflowRepository as DevSurveyWorkflowRepository,
)
from app.dev_survey.services import EvaluationService as DevSurveyEvaluationService
from app.dev_survey.services import ResearchService as DevSurveyResearchService
from app.infrastructure.db.repositories.evaluation_repository_impl import EvaluationRepositoryImpl
from app.infrastructure.db.repositories.trace_repository_impl import TraceRepositoryImpl
from app.research_assistant.repositories import (
    ResearchAssistantTaskRepositoryImpl,
    ResearchAssistantWorkflowRepositoryImpl,
    TaskRepository,
    WorkflowRepository,
)
from app.research_assistant.services import EvaluationService, ResearchService
from harness.config import get_harness_settings
from harness.evaluation.orchestrator import EvaluationOrchestrator
from harness.events.manager import SSEConnectionManager
from harness.llm.factory import clear_llm_client_cache, get_llm_client
from harness.logger import logger
from harness.observability.trace_service import TraceService, get_trace_service
from harness.storage.local_storage import LocalObjectStorage

settings = get_harness_settings()


@lru_cache
def get_sse_manager():
    """Return the process-wide SSE connection manager singleton."""
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


@lru_cache
def get_research_assistant_evaluation_orchestrator():
    from app.scenarios.research_assistant.evaluation_config import get_evaluators, get_weights

    llm_client = get_llm_client()
    evaluators = get_evaluators(llm_client)
    weights = get_weights()
    return EvaluationOrchestrator(evaluators=evaluators, weights=weights)


@lru_cache
def get_dev_survey_evaluation_orchestrator():
    from app.scenarios.dev_survey.evaluation_config import get_evaluators, get_weights

    llm_client = get_llm_client()
    evaluators = get_evaluators(llm_client)
    weights = get_weights()
    return EvaluationOrchestrator(evaluators=evaluators, weights=weights)


@lru_cache
def get_evaluation_orchestrator():
    """获取评估编排器（默认使用 research_assistant 配置）"""
    return get_research_assistant_evaluation_orchestrator()


def create_evaluation_service(db: Session):
    evaluation_repository = get_evaluation_repository(db)
    return EvaluationService(evaluation_repository)


def create_research_service(db: Session, report_url_prefix: str):
    """Build a request-scoped ResearchService bound to the given session.

    The session is owned by the caller (scenario executor), so this factory does
    not close it.
    """
    workflow_repository = get_research_assistant_workflow_repository(db)
    task_repository = get_research_assistant_task_repository(db)
    evaluation_service = create_evaluation_service(db)
    evaluation_orchestrator = get_research_assistant_evaluation_orchestrator()
    return ResearchService(
        workflow_repository=workflow_repository,
        task_repository=task_repository,
        evaluation_service=evaluation_service,
        evaluation_orchestrator=evaluation_orchestrator,
        report_url_prefix=report_url_prefix,
    )


# --- DevSurvey 共享组件缓存（每个组件独立懒加载） ---


@lru_cache
def _get_dev_survey_plan_agent():
    return PlanAgent(get_llm_client())


@lru_cache
def _get_dev_survey_search_agent():
    return SearchAgent()


@lru_cache
def _get_dev_survey_summarizer_agent():
    return SummarizerAgent(get_llm_client())


@lru_cache
def _get_dev_survey_generate_agent():
    return GenerateAgent(get_llm_client())


@lru_cache
def _get_dev_survey_critic_agent():
    return CriticAgent(get_llm_client())


@lru_cache
def _get_dev_survey_event_publisher():
    return get_event_publisher()


@lru_cache
def _get_dev_survey_object_storage():
    return LocalObjectStorage(url_prefix="/dev-research/reports")


@lru_cache
def _get_dev_survey_trace_service() -> TraceService:
    repository = TraceRepositoryImpl()
    return get_trace_service(repository=repository)


def create_trace_service() -> TraceService:
    """创建 TraceService（app 层工厂，负责注入 TraceRepositoryImpl）"""
    repository = TraceRepositoryImpl()
    return get_trace_service(repository=repository)


def create_dev_survey_service(db: Session, report_url_prefix: str):
    """Build a request-scoped DevSurvey service with lazily-shared components.

    Agent/storage/trace factories are injected as callables so heavy singletons
    are only created when the workflow actually needs them.
    """
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
    )


async def invalidate_llm_client_cache():
    """Drop every LLM-related cache after configuration changes.

    All cached agents hold a client instance, so they must be evicted together
    with the client cache; otherwise stale clients keep being reused.
    """
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
