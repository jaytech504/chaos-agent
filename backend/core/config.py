from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/chaos_agent"
    app_env: str = "development"
    frontend_url: str = "http://localhost:3000"

    # GitHub OAuth
    github_client_id: str = ""
    github_client_secret: str = ""

    # GitHub — optional fallback (for demo/dev use without OAuth)
    github_token: str = ""

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
