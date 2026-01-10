"""Application configuration using Pydantic Settings."""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: Literal["dev", "staging", "prod"] = "dev"
    debug: bool = False

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"

    # GitHub Webhook
    github_webhook_secret: str = ""

    # GitHub API (for log fetching)
    github_token: str = ""
    github_api_base_url: str = "https://api.github.com"

    # Log fetching
    log_max_size_mb: int = 10

    # Database
    database_url: str = "postgresql+asyncpg://sre_agent:sre_agent_password@localhost:5432/sre_agent"

    # Redis (Celery Broker)
    redis_url: str = "redis://localhost:6379/0"

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "text"] = "json"

    # Rate Limiting
    rate_limit_requests_per_minute: int = 100

    # LLM Configuration
    llm_provider: Literal["ollama", "mock"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "deepseek-coder:6.7b"
    fix_max_tokens: int = 2000
    fix_max_files: int = 3
    fix_max_lines: int = 50

    # Sandbox Configuration
    sandbox_docker_image: str = "python:3.11-slim"
    sandbox_timeout_seconds: int = 300
    sandbox_memory_limit: str = "512m"
    sandbox_cpu_limit: float = 1.0
    sandbox_network_enabled: bool = False

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "prod"

    @property
    def celery_broker_url(self) -> str:
        """Celery broker URL (Redis)."""
        return self.redis_url

    @property
    def celery_result_backend(self) -> str:
        """Celery result backend (Redis)."""
        return self.redis_url


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
