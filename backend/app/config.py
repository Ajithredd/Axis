"""Axis — Application configuration via environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Central configuration loaded from environment variables."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

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
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 3072
    llm_model: str = "gemini-2.5-flash"

    # --- Chunking ---
    chunk_size: int = 1000
    chunk_overlap: int = 200


settings = Settings()
