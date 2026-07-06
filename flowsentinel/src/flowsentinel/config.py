import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    database_url: str = Field(default="postgresql://postgres:postgres@127.0.0.1:5432/flowsentinel")
    redis_url: str = Field(default="redis://127.0.0.1:6379/0")
    anthropic_api_key: str | None = Field(default=None)
    pipeline_backpressure_limit: int = Field(default=100)
    mempool_semaphore_limit: int = Field(default=10)
    liquidity_semaphore_limit: int = Field(default=5)
    
    # Alerting Settings
    webhook_url: str | None = Field(default=None)
    telegram_token: str | None = Field(default=None)
    telegram_chat_id: str | None = Field(default=None)
    circuit_breaker_cooldown: float = Field(default=30.0)
    circuit_breaker_max_failures: int = Field(default=5)

    # Allow loading from project root .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate settings singleton
settings = Settings()
