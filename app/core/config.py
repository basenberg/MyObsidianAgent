"""Application configuration using pydantic-settings.

This module provides centralized configuration management:
- Environment variable loading from .env file
- Type-safe settings with validation
- Cached settings instance with @lru_cache
- Settings for application, LLM, auth, CORS, and optional database configuration
"""

from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    """Application-wide configuration.

    All settings can be overridden via environment variables.
    Environment variables are case-insensitive.
    Settings are loaded from .env file if present.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Don't fail if .env file doesn't exist
        extra="ignore",
    )

    # Application metadata
    app_name: str = "Obsidian Agent Project"
    version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api"

    # LLM configuration
    llm_provider: str = "anthropic"
    llm_model: str = "claude-haiku-4-5-20251001"
    llm_api_key: str = ""

    # API authentication
    api_key: str = ""

    # Database — optional, not required for agent-only deployments
    database_url: str = ""

    # CORS settings
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8123",
        "app://obsidian.md",
        "capacitor://localhost",
    ]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    The @lru_cache decorator ensures settings are only loaded once
    and reused across the application lifecycle.

    Returns:
        The application settings instance.
    """
    return Settings()
