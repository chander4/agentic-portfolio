"""Runtime configuration via environment / .env."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    llm_provider: Literal["bedrock", "mock"] = "mock"
    bedrock_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    llm_max_tokens: int = 1024
    llm_temperature: float = 0.0

    # Router
    max_retries: int = 3
    request_timeout_seconds: float = 30.0

    # API
    host: str = "0.0.0.0"
    port: int = 8081
    log_level: str = "info"


@lru_cache
def get_settings() -> Settings:
    return Settings()
