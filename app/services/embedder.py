"""
INPUT:
- Text payloads requiring embedding vectors via Ollama HTTP API.
OUTPUT:
- Numeric embedding vectors for single or batched text inputs.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


class EmbeddingService:
    """Wrapper around the Ollama embeddings endpoint."""

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = base_url or settings.ollama_url
        self.model = model or settings.embedding_model
        self._client = httpx.Client(base_url=self.base_url)

    def get_embedding(self, text: str) -> list[float]:
        payload = {"model": self.model, "prompt": text}
        response = self._client.post("/api/embeddings", json=payload, timeout=60)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data.get("embedding", [])

    def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.get_embedding(text) for text in texts]


embedding_service = EmbeddingService()
