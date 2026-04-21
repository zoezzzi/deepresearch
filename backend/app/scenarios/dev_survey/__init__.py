from app.scenarios.registry import ScenarioRegistry
from app.scenarios.dev_survey.executor import DevSurveyExecutor


def register_dev_survey() -> None:
    executor = DevSurveyExecutor()
    ScenarioRegistry.register(executor)
