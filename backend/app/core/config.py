from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "dev"
    DATABASE_URL: str = "sqlite+aiosqlite:///./novel_agent.db"
    SECRET_KEY: str = "change-this-to-a-random-secret-key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    @property
    def is_prod(self) -> bool:
        return self.APP_ENV == "prod"

    @property
    def db_driver(self) -> str:
        return "MySQL" if self.is_prod else "SQLite"

    class Config:
        env_file = ".env"


settings = Settings()
