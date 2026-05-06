from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Callable, Sequence
from typing import Any

logger = logging.getLogger(__name__)


class EmbeddingInitializationError(RuntimeError):
    """Raised when the embedding model cannot be initialized."""


class TextEmbedder:
    """Sentence-transformer embedder with a deterministic fallback for development."""

    def __init__(
        self,
        model_name: str,
        dimensions: int,
        encoder: Callable[[Sequence[str]], Sequence[Sequence[float]]] | None = None,
    ) -> None:
        self.model_name = model_name
        self.dimensions = dimensions
        self._encoder = encoder
        self._model: Any | None = None

        if self._encoder is None:
            self._model = self._load_model()

    def _load_model(self) -> Any:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EmbeddingInitializationError(
                "sentence-transformers is not installed. Install API requirements to generate embeddings."
            ) from exc

        try:
            return SentenceTransformer(self.model_name)
        except (OSError, ValueError) as exc:
            raise EmbeddingInitializationError(f"Unable to load embedding model '{self.model_name}'.") from exc

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        if self._encoder is not None:
            return [self._normalize(vector) for vector in self._encoder(texts)]

        if self._model is None:
            raise EmbeddingInitializationError("Embedding model is not initialized.")

        vectors = self._model.encode(
            list(texts),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [self._normalize(vector) for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def _normalize(self, vector: Sequence[float]) -> list[float]:
        values = [float(item) for item in vector]
        if len(values) != self.dimensions:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.dimensions}, received {len(values)}."
            )

        norm = math.sqrt(sum(item * item for item in values))
        if norm == 0:
            return values
        return [item / norm for item in values]


class HashingTextEmbedder(TextEmbedder):
    """Small deterministic embedder used when model loading is unavailable."""

    def __init__(self, model_name: str, dimensions: int) -> None:
        super().__init__(model_name=model_name, dimensions=dimensions, encoder=self._encode)

    def _encode(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._hash_text(text) for text in texts]

    def _hash_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], byteorder="big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        return vector


def build_default_embedder(model_name: str, dimensions: int) -> TextEmbedder:
    if model_name.startswith("hashing"):
        return HashingTextEmbedder(model_name=model_name, dimensions=dimensions)

    try:
        return TextEmbedder(model_name=model_name, dimensions=dimensions)
    except EmbeddingInitializationError:
        logger.exception("Embedding model initialization failed; using deterministic hashing embedder.")
        return HashingTextEmbedder(model_name=f"hashing:{dimensions}", dimensions=dimensions)

