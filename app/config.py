"""
INPUT:
- Environment values or defaults for configuring Nexus backend services.
OUTPUT:
- Configuration helper exposing resolved settings constants.
"""
from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class NexusSettings(BaseSettings):
    """Application-wide configuration container."""

    db_path: Path = Path("./data/nexus.db")
    db_path_prod: Path = Path("/home/micha/nexus/data/nexus.db")
    ollama_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    chapter_model: str = "qwen2.5:7b"
    ingress_path: Path = Path("/home/micha/nexus/ingress/")
    originals_path: Path = Path("./data/originals")
    chapters_path: Path = Path("./data/chapters")

    model_config = SettingsConfigDict(env_prefix="NEXUS_", case_sensitive=False)


settings = NexusSettings()
