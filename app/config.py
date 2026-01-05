"""Application configuration using Pydantic settings."""

from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )

    # Model settings
    model_name: str = "facebook/pe-av-large"
    model_cache_dir: str = "/tmp/models"
    device: Literal["cpu", "cuda"] = "cpu"
    hf_endpoint: str = ""  # Hugging Face mirror endpoint (e.g., https://hf-mirror.com)

    # Database settings
    database_url: str = "sqlite+aiosqlite:///./data/trenton.db"

    # Monitoring settings
    indexing_concurrent_jobs: int = 5
    file_event_cooldown_seconds: float = 2.0
    indexing_batch_size: int = 10

    # Search settings
    default_top_k: int = 10
    default_threshold: float = 0.0
    max_top_k: int = 100

    # API settings
    api_title: str = "Trenton Multimodal Search API"
    api_version: str = "1.0.0"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Logging
    log_level: str = "INFO"


# Global settings instance
settings = Settings()
