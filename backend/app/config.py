from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py → backend/app → backend → project root
_ENV_FILE = Path(__file__).parent.parent.parent / ".env"


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://dungeon:dungeon@localhost:5432/dungeon"
    database_url_sync: str = (
        "postgresql+psycopg2://dungeon:dungeon@localhost:5432/dungeon"
    )
    redis_url: str = "redis://localhost:6379"

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
