from app.scenarios.registry import ScenarioRegistry
from app.scenarios.research_assistant.executor import ResearchAssistantExecutor


def register_research_assistant() -> None:
    executor = ResearchAssistantExecutor()
    ScenarioRegistry.register(executor)
