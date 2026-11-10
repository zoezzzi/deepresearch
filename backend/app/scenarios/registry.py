"""Scenario registry: process-wide mapping from scenario_id to executor."""

from app.scenarios.protocols import ScenarioExecutor, ScenarioMetadata


class ScenarioRegistry:
    """In-process scenario registry, populated at startup and read-only afterwards.

    Registration happens inside the FastAPI lifespan startup (see
    ``register_enabled_scenarios``); the API layer then resolves a
    ``ScenarioExecutor`` by ``scenario_id``.
    """

    _executors: dict[str, ScenarioExecutor] = {}

    @classmethod
    def register(cls, executor: ScenarioExecutor) -> None:
        """Register an executor keyed by its metadata scenario_id (re-register overwrites)."""
        metadata = executor.get_metadata()
        cls._executors[metadata.scenario_id] = executor

    @classmethod
    def get(cls, scenario_id: str) -> ScenarioExecutor | None:
        """Look up an executor by id, returning None when unregistered."""
        return cls._executors.get(scenario_id)

    @classmethod
    def list_all(cls) -> list[ScenarioMetadata]:
        """Return metadata of every registered scenario for the UI selector."""
        return [executor.get_metadata() for executor in cls._executors.values()]

    @classmethod
    def list_executors(cls) -> list[ScenarioExecutor]:
        """Return all registered executor instances."""
        return list(cls._executors.values())
