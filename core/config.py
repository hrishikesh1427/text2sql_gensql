from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://pguser:pgpass@localhost:5432/mydb"
    OPENAI_API_KEY: str | None = None
    REFRESH_INTERVAL_SECONDS: int = 300
    MAX_ROWS: int = 1000
    PSEUDO_SCHEMA_MODEL: str = "gpt-4o-mini"
    SQL_GENERATION_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    TOP_K_GROUND: int = 5

    class Config:
        env_file = ".env"

settings = Settings()
