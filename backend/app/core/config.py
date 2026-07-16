from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "dev"
    DATABASE_URL: str = "sqlite+aiosqlite:///./novel_agent.db"
    SECRET_KEY: str = "change-this-to-a-random-secret-key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    DEEPSEEK_API_KEY: str = ""

    # Retrieval / vector search
    RETRIEVAL_ENABLED: bool = True
    QDRANT_URL: str = "http://127.0.0.1:6333"
    QDRANT_COLLECTION: str = "novel-context-v1"
    MODEL_STUDIO_BASE_URL: str = ""
    MODEL_STUDIO_API_KEY: str = ""
    MODEL_STUDIO_EMBEDDING_MODEL: str = "text-embedding-v4"
    MODEL_STUDIO_RERANK_MODEL: str = "qwen3-rerank"

    @property
    def is_prod(self) -> bool:
        return self.APP_ENV == "prod"

    @property
    def db_driver(self) -> str:
        return "MySQL" if self.is_prod else "SQLite"

    class Config:
        env_file = ".env"


settings = Settings()
