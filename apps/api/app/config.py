from __future__ import annotations

import os
from dataclasses import dataclass, field


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "Adbot API"))
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    api_host: str = field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    api_port: int = field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))
    api_base_url: str = field(default_factory=lambda: os.getenv("API_BASE_URL", "http://localhost:8000"))
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://postgres:postgres@localhost:5432/adbot",
        )
    )
    retrieval_top_k: int = field(default_factory=lambda: int(os.getenv("RETRIEVAL_TOP_K", "10")))
    reranker_enabled: bool = field(default_factory=lambda: _get_bool("RERANKER_ENABLED", True))
    reranker_model_name: str = field(
        default_factory=lambda: os.getenv(
            "RERANKER_MODEL_NAME",
            "cross-encoder/ms-marco-MiniLM-L-6-v2",
        )
    )
    reranker_top_n: int = field(default_factory=lambda: int(os.getenv("RERANKER_TOP_N", "3")))
    reranker_batch_size: int = field(default_factory=lambda: int(os.getenv("RERANKER_BATCH_SIZE", "8")))
    reranker_device: str = field(default_factory=lambda: os.getenv("RERANKER_DEVICE", "cpu"))


settings = Settings()
