"""Scenario assembly entry point: decide which scenarios to register at startup."""

from collections.abc import Callable

from app.scenarios.dev_survey import register_dev_survey
from app.scenarios.research_assistant import register_research_assistant
from harness.logger import logger

_SCENARIO_REGISTRY: dict[str, Callable[[], None]] = {
    # 场景 ID -> 注册函数；注册函数内部会把执行器写入 ScenarioRegistry
    "research_assistant_v1": register_research_assistant,
    "dev_survey": register_dev_survey,
}


def register_enabled_scenarios(enabled_scenarios: list[str]) -> None:
    """Register the scenarios enabled by configuration.

    A single failing scenario is logged and skipped instead of aborting startup;
    unknown ids are ignored so one config file can be reused across branches.
    """
    from app.scenarios.registry import ScenarioRegistry

    registered_count = 0

    for scenario_id in enabled_scenarios:
        if scenario_id in _SCENARIO_REGISTRY:
            try:
                _SCENARIO_REGISTRY[scenario_id]()
                logger.info(f"[ScenarioManager] 已注册场景: {scenario_id}")
                registered_count += 1
            except Exception as e:
                logger.error(f"[ScenarioManager] 注册场景失败: {scenario_id}, 错误: {e}")
        else:
            logger.warning(f"[ScenarioManager] 未知场景 ID，跳过注册: {scenario_id}")

    logger.info(
        f"[ScenarioManager] 场景注册完成，共注册 {registered_count}/{len(enabled_scenarios)} 个场景"
    )
    logger.info(f"[ScenarioManager] 当前已注册场景数: {len(ScenarioRegistry.list_executors())}")


def get_available_scenarios() -> list[str]:
    """Return scenario ids that have a built-in registration function."""
    return list(_SCENARIO_REGISTRY.keys())
