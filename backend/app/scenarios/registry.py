from typing import Dict
from app.scenarios.protocols import ScenarioExecutor, ScenarioMetadata


class ScenarioRegistry:
    _executors: Dict[str, ScenarioExecutor] = {}
    
    @classmethod
    def register(cls, executor: ScenarioExecutor) -> None:
        metadata = executor.get_metadata()
        cls._executors[metadata.scenario_id] = executor
    
    @classmethod
    def get(cls, scenario_id: str) -> ScenarioExecutor | None:
        return cls._executors.get(scenario_id)
    
    @classmethod
    def list_all(cls) -> list[ScenarioMetadata]:
        return [executor.get_metadata() for executor in cls._executors.values()]
    
    @classmethod
    def list_executors(cls) -> list[ScenarioExecutor]:
        return list(cls._executors.values())
