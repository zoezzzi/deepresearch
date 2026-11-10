from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class HarnessSettings(BaseSettings):
    PROJECT_NAME: str = "DeepResearch"
    DEBUG: bool = True

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "12345"
    POSTGRES_DB: str = "deepresearch"

    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "deepresearch"
    MINIO_SECURE: bool = False

    REPORT_STORAGE_TYPE: str = "local"
    REPORT_STORAGE_PATH: str = "./reports"

    LLM_PROVIDER: str = "qwen"
    LLM_MODEL_ID: str = "qwen-plus"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_TIMEOUT: int = 600
    LLM_TEMPERATURE: float = 0.7

    LLM_TIMEOUT_PLAN: int = 300
    LLM_TIMEOUT_EXECUTE: int = 600
    LLM_TIMEOUT_REPORT: int = 900

    LLM_MAX_RETRIES: int = 3

    TAVILY_API_KEY: str = ""
    GITHUB_API_KEY: str = ""

    DB_POOL_MIN_SIZE: int = 5
    DB_POOL_MAX_SIZE: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_MAX_IDLE: int = 300
    DB_POOL_MAX_LIFETIME: int = 3600

    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "deepresearch"

    USE_PARALLEL_EXECUTION: bool = True
    MAX_CONCURRENT_TASKS: int = 3
    RESOURCE_CLEANUP_INTERVAL: int = 3600
    MAX_CACHE_AGE: int = 86400

    # Dev Survey 高级功能开关
    ENABLE_KNOWLEDGE_TRANSFER: bool = False  # 任务间知识传递
    MAX_REPORT_SELF_CHECK_TRIES: int = 1  # 报告自检最大尝试次数
    ENABLE_REFLECTION: bool = False  # 自反思模块启用

    @property
    def database_url(self) -> str:
        encoded_password = quote_plus(self.POSTGRES_PASSWORD)
        return f"postgresql+psycopg://{self.POSTGRES_USER}:{encoded_password}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def sync_database_url(self) -> str:
        encoded_password = quote_plus(self.POSTGRES_PASSWORD)
        return f"postgresql+psycopg2://{self.POSTGRES_USER}:{encoded_password}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


@lru_cache
def get_harness_settings() -> HarnessSettings:
    return HarnessSettings()
