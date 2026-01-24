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
    repo_webhook_rate_limit_per_minute: int = 30

    # Pipeline Reliability
    repo_pipeline_concurrency_limit: int = 2
    repo_pipeline_concurrency_ttl_seconds: int = 1200
    max_pipeline_attempts: int = 3
    base_backoff_seconds: int = 30
    max_backoff_seconds: int = 600
    cooldown_seconds: int = 900

    # LLM Configuration
    llm_provider: Literal["ollama", "mock"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "deepseek-coder:6.7b"
    fix_max_tokens: int = 2000
    fix_max_files: int = 3
    fix_max_lines: int = 50

    # Sandbox Configuration
    sandbox_docker_image: str = "sre-agent-sandbox:scanners-2026-01-20"
    sandbox_timeout_seconds: int = 300
    sandbox_memory_limit: str = "512m"
    sandbox_cpu_limit: float = 1.0
    sandbox_network_enabled: bool = False
    enable_scans: bool = True
    fail_on_secrets: bool = True
    fail_on_vuln_severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "HIGH"
    scanner_timeout_seconds: int = 120
    artifacts_dir: str = "artifacts"

    safety_policy_path: str = "config/safety_policy.yaml"

    # ============================================
    # NOTIFICATION CONFIGURATION
    # ============================================

    # Slack Integration
    slack_enabled: bool = False
    slack_webhook_url: str = ""
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_default_channel: str = "#sre-alerts"
    slack_critical_channel: str = "#sre-critical"
    slack_approval_channel: str = "#sre-approvals"

    # Microsoft Teams Integration
    teams_enabled: bool = False
    teams_webhook_url: str = ""

    # Email Integration
    email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from_address: str = "sre-agent@company.com"
    smtp_from_name: str = "SRE Agent"
    email_default_recipients: str = ""  # Comma-separated
    email_critical_recipients: str = ""  # Comma-separated
    sendgrid_api_key: str = ""

    # PagerDuty Integration
    pagerduty_enabled: bool = False
    pagerduty_routing_key: str = ""
    pagerduty_api_key: str = ""
    pagerduty_auto_resolve: bool = True

    # Generic Webhook
    webhook_enabled: bool = False
    webhook_url: str = ""
    webhook_auth_type: str = ""  # "bearer", "basic", "hmac"
    webhook_auth_token: str = ""
    webhook_hmac_secret: str = ""

    # Notification Manager Settings
    notification_parallel_dispatch: bool = True
    notification_rate_limit_enabled: bool = True
    notification_rate_limit_per_minute: int = 30
    notification_min_level: str = "info"  # debug, info, warning, error, critical

    # ============================================
    # AUTHENTICATION CONFIGURATION
    # ============================================

    # JWT Settings
    jwt_secret_key: str = "change-this-to-a-secure-secret-key-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # GitHub OAuth
    github_oauth_client_id: str = ""
    github_oauth_client_secret: str = ""
    github_oauth_redirect_uri: str = "http://localhost:8000/api/v1/auth/oauth/github/callback"

    # Google OAuth
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/api/v1/auth/oauth/google/callback"

    # Session Settings
    session_max_age_hours: int = 24
    require_email_verification: bool = False

    # ============================================
    # CI/CD PROVIDER CONFIGURATION (Phase 2)
    # ============================================

    # Enabled providers (comma-separated)
    enabled_ci_providers: str = "github"

    # GitLab Integration
    gitlab_enabled: bool = False
    gitlab_url: str = "https://gitlab.com"
    gitlab_token: str = ""
    gitlab_webhook_token: str = ""

    # CircleCI Integration
    circleci_enabled: bool = False
    circleci_token: str = ""
    circleci_webhook_secret: str = ""

    # Jenkins Integration
    jenkins_enabled: bool = False
    jenkins_url: str = ""
    jenkins_user: str = ""
    jenkins_token: str = ""
    jenkins_webhook_token: str = ""

    # Azure DevOps Integration
    azure_devops_enabled: bool = False
    azure_devops_org: str = ""
    azure_devops_pat: str = ""
    azure_devops_webhook_secret: str = ""

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
