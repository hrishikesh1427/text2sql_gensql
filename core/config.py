from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str  # Required: Set in .env file
    OPENAI_API_KEY: str | None = None
    REFRESH_INTERVAL_SECONDS: int = 300
    MAX_ROWS: int = 1000
    PSEUDO_SCHEMA_MODEL: str = "gpt-4o-mini"
    SQL_GENERATION_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    TOP_K_GROUND: int = 5
    # Comma-separated list of schemas to introspect (empty = all non-system schemas)
    DATABASE_SCHEMAS: str = "public,chatbot"

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    def get_asyncpg_dsn(self) -> str:
        """
        Convert SQLAlchemy-style DATABASE_URL to asyncpg-compatible DSN.
        Removes the +asyncpg driver specification.
        """
        dsn = self.DATABASE_URL
        # Replace postgresql+asyncpg:// with postgresql://
        if dsn.startswith("postgresql+asyncpg://"):
            dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
        # Also handle postgres+asyncpg://
        elif dsn.startswith("postgres+asyncpg://"):
            dsn = dsn.replace("postgres+asyncpg://", "postgresql://", 1)
        return dsn

settings = Settings()
