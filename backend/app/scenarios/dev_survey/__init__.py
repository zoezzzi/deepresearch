from app.scenarios.dev_survey.executor import DevSurveyExecutor
from app.scenarios.registry import ScenarioRegistry


def register_dev_survey() -> None:
    executor = DevSurveyExecutor()
    ScenarioRegistry.register(executor)
