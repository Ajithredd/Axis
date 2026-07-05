"""Axis — Application configuration via environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Central configuration loaded from environment variables."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # --- App ---
    app_name: str = "Axis"
    secret_key: str = "change-me-to-a-random-string"
    app_url: str = "http://localhost:5173"
    api_url: str = "http://localhost:8000"
    debug: bool = True

    # --- Database ---
    database_url: str = "postgresql+asyncpg://axis:axis@localhost:5432/axis"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Qdrant ---
    qdrant_url: str = "http://localhost:6333"

    # --- GitLab ---
    gitlab_url: str = "https://gitlab.com"
    gitlab_app_id: str = ""
    gitlab_app_secret: str = ""
    gitlab_personal_access_token: str = ""

    # --- Google Gemini ---
    gemini_api_key: str = ""
    # text-embedding-004 → 768 dims | gemini-embedding-001 → 3072 dims
    embedding_model: str = "text-embedding-004"
    embedding_dimensions: int = 768
    llm_model: str = "gemini-2.5-flash"

    # --- Chunking ---
    chunk_size: int = 1000
    chunk_overlap: int = 200
    child_chunk_size: int = 250
    child_chunk_overlap: int = 50

    # --- LangSmith Tracing ---
    langsmith_api_key: str = ""
    langsmith_project: str = "axis-rag"
    langsmith_enabled: bool = False  # Auto-enabled when langsmith_api_key is set

    # --- RAGAS Evaluation ---
    ragas_enabled: bool = True  # Run RAGAS eval post-generation (fire-and-forget)
    ragas_eval_model: str = "gemini-2.0-flash"  # Lighter model for eval judge

    # --- Advanced Retrieval ---
    step_back_prompting_enabled: bool = True
    contextual_compression_enabled: bool = True
    contextual_compression_threshold: float = 0.6  # Compress chunks with rerank score below this
    parent_document_retrieval_enabled: bool = True


settings = Settings()
