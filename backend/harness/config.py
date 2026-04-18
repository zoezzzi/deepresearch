from pydantic_settings import BaseSettings
from functools import lru_cache
from urllib.parse import quote_plus


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
    LLM_TIMEOUT: int = 300
    LLM_TEMPERATURE: float = 0.7
    
    TAVILY_API_KEY: str = ""
    
    DB_POOL_MIN_SIZE: int = 5
    DB_POOL_MAX_SIZE: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_MAX_IDLE: int = 300
    DB_POOL_MAX_LIFETIME: int = 3600
    
    @property
    def DATABASE_URL(self) -> str:
        encoded_password = quote_plus(self.POSTGRES_PASSWORD)
        return f"postgresql+psycopg://{self.POSTGRES_USER}:{encoded_password}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    @property
    def SYNC_DATABASE_URL(self) -> str:
        encoded_password = quote_plus(self.POSTGRES_PASSWORD)
        return f"postgresql+psycopg2://{self.POSTGRES_USER}:{encoded_password}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_harness_settings() -> HarnessSettings:
    return HarnessSettings()
