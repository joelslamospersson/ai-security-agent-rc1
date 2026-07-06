"""
Typed configuration settings for the Management Server.

Loads from:
  1. Internal defaults
  2. .env file
  3. Environment variables (MGMT_ prefix)
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="MGMT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # General
    debug: bool = False
    log_level: str = "INFO"
    log_format: str = "json"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1

    # Database
    # Override URL (if set, takes priority over individual db_* fields)
    database_url_override: str = ""

    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "ai_security"
    db_password: str = "ai_security"
    db_database: str = "ai_security"
    db_ssl_mode: str = "prefer"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_connect_timeout: int = 10
    db_application_name: str = "management-server"
    db_echo: bool = False  # Log SQL statements (debug only)

    @property
    def database_url(self) -> str:
        """Build the PostgreSQL connection URL, or return override if set."""
        if self.database_url_override:
            return self.database_url_override
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_database}"
            f"?application_name={self.db_application_name}"
            f"&connect_timeout={self.db_connect_timeout}"
            f"&sslmode={self.db_ssl_mode}"
        )

    @property
    def database_url_sync(self) -> str:
        """Build the synchronous PostgreSQL URL for Alembic."""
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_database}"
        )

    # Security
    secret_key: str = "change-me-in-production"


def get_settings() -> Settings:
    """Return application settings, loading from environment."""
    return Settings()
