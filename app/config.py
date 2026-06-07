import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, Literal

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    env: Literal["development", "production", "testing"] = "development"

    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    google_places_api_key: Optional[str] = None
    mapbox_token: Optional[str] = None
    foursquare_api_key: Optional[str] = None

    database_url: str = f"sqlite:///{PROJECT_ROOT}/data/local_scout.db"
    chroma_db_path: str = str(PROJECT_ROOT / "data" / "chroma")
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    redis_url: str = "redis://localhost:6379/0"

    ollama_base_url: str = "http://localhost:11434"

    llm_primary: Literal["claude", "gpt-4o", "ollama"] = "claude"
    llm_fallback_chain: str = "gpt-4o,ollama-llama3"

    crawl_concurrency_limit: int = Field(default=5, ge=1, le=20)
    crawl_rate_limit_rps: float = Field(default=1.0, ge=0.1)
    crawl_cache_ttl_hours: int = Field(default=72, ge=1)
    crawl_timeout_seconds: int = Field(default=30, ge=5, le=120)
    crawl_user_agent: str = "LocalScoutAgent/1.0 (academic-research@localscout.ai)"

    max_llm_daily_cost_usd: float = 5.00
    llm_request_timeout_seconds: int = Field(default=60, ge=10, le=300)
    llm_cache_ttl_seconds: int = Field(default=86400, ge=3600)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["text", "json"] = "text"

    model_cache_dir: str = str(PROJECT_ROOT / "models_cache")
    model_device: str = "cpu"
    model_batch_size: int = Field(default=32, ge=1, le=128)
    model_quantization: Literal["none", "int8", "onnx"] = "int8"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = Field(default=4, ge=1, le=16)
    api_rate_limit_per_minute: int = Field(default=60, ge=10)

    data_retention_days: int = Field(default=90, ge=1, le=365)
    request_timeout_seconds: int = Field(default=30, ge=5, le=120)

    sentry_dsn: Optional[str] = None
    prometheus_enabled: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
os.makedirs(settings.model_cache_dir, exist_ok=True)
os.makedirs(settings.chroma_db_path, exist_ok=True)
os.makedirs(PROJECT_ROOT / "data", exist_ok=True)
