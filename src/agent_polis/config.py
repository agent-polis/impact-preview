"""
Application configuration using pydantic-settings.

Loads configuration from environment variables and .env files.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="agent-polis", description="Application name")
    app_env: Literal["development", "staging", "production"] = Field(
        default="development", description="Environment"
    )
    debug: bool = Field(default=False, description="Debug mode")
    secret_key: str = Field(
        default="change-me-in-production", description="Secret key for signing"
    )

    # Server
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")

    # Database
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/agent_polis",
        description="PostgreSQL connection URL",
    )
    database_echo: bool = Field(default=False, description="Echo SQL queries")

    # Redis
    redis_url: RedisDsn = Field(
        default="redis://localhost:6379/0", description="Redis connection URL"
    )

    # E2B Sandbox
    e2b_api_key: str | None = Field(default=None, description="E2B API key for sandbox execution")

    # Rate Limiting
    rate_limit_requests: int = Field(default=100, description="Max requests per window")
    rate_limit_window: int = Field(default=60, description="Rate limit window in seconds")

    # Agent Configuration
    default_simulation_timeout: int = Field(
        default=300, description="Default simulation timeout in seconds"
    )
    max_concurrent_simulations: int = Field(
        default=10, description="Maximum concurrent simulations"
    )

    # Metering
    enable_metering: bool = Field(default=True, description="Enable usage metering")
    free_tier_simulations_per_month: int = Field(
        default=100, description="Free tier simulation limit"
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Log level"
    )
    log_format: Literal["json", "text"] = Field(default="json", description="Log format")

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience export
settings = get_settings()
