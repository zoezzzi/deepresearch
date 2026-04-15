from pydantic_settings import BaseSettings
from functools import lru_cache
from urllib.parse import quote_plus


class Settings(BaseSettings):
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
    REPORT_URL_PREFIX: str = "/research/reports"
    
    # QWEN_API_KEY: str = ""
    # QWEN_BASE_URL: str = ""
    LLM_PROVIDER: str = "qwen"         
    LLM_MODEL_ID: str = "qwen-plus"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_TIMEOUT: int = 300  # 增加到 300 秒（5 分钟），报告生成需要更多时间
    LLM_TEMPERATURE: float = 0.7
    
    TAVILY_API_KEY: str = ""
    
    # 数据库连接池配置
    DB_POOL_MIN_SIZE: int = 5
    DB_POOL_MAX_SIZE: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_MAX_IDLE: int = 300
    DB_POOL_MAX_LIFETIME: int = 3600
    
    @property
    def DATABASE_URL(self) -> str:
        # URL 编码密码，防止特殊字符导致连接失败
        encoded_password = quote_plus(self.POSTGRES_PASSWORD)
        return f"postgresql+psycopg://{self.POSTGRES_USER}:{encoded_password}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    @property
    def SYNC_DATABASE_URL(self) -> str:
        # 同步数据库 URL（用于 SQLAlchemy）
        encoded_password = quote_plus(self.POSTGRES_PASSWORD)
        return f"postgresql+psycopg2://{self.POSTGRES_USER}:{encoded_password}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
