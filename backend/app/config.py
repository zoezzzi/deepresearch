from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """App 层配置 - 场景相关配置"""

    # 启用的场景列表（逗号分隔）
    ENABLED_SCENARIOS: str = "research_assistant_v1,dev_survey"

    @property
    def enabled_scenarios_list(self) -> list[str]:
        """解析启用的场景列表"""
        if not self.ENABLED_SCENARIOS:
            return []
        return [s.strip() for s in self.ENABLED_SCENARIOS.split(",") if s.strip()]

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


@lru_cache
def get_app_settings() -> AppSettings:
    return AppSettings()
