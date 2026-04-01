from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any

logger = logging.getLogger(__name__)


class RerankerInitializationError(RuntimeError):
    """Raised when the cross-encoder model cannot be initialized."""


class CrossEncoderReranker:
    """Cross-encoder reranker with lazy, production-friendly model loading."""

    def __init__(
        self,
        model_name: str,
        device: str,
        batch_size: int,
        scorer: Callable[[Sequence[tuple[str, str]]], Sequence[float]] | None = None,
    ) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.device = self._resolve_device(device)
        self._scorer = scorer
        self._model: Any | None = None

        if self._scorer is None:
            self._model = self._load_model()

    def _resolve_device(self, requested_device: str) -> str:
        device = requested_device.strip().lower() or "cpu"
        if device == "cpu":
            return "cpu"

        try:
            import torch
        except ImportError as exc:
            raise RerankerInitializationError(
                "Torch is required for non-CPU reranker devices."
            ) from exc

        if device.startswith("cuda") and not torch.cuda.is_available():
            logger.warning("CUDA requested for reranker but unavailable; falling back to CPU.")
            return "cpu"

        return device

    def _load_model(self) -> Any:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RerankerInitializationError(
                "sentence-transformers is not installed. Install API requirements to use reranking."
            ) from exc

        try:
            return CrossEncoder(self.model_name, device=self.device)
        except (OSError, ValueError) as exc:
            raise RerankerInitializationError(
                f"Unable to load reranker model '{self.model_name}'."
            ) from exc

    def _score_pairs(self, pairs: Sequence[tuple[str, str]]) -> list[float]:
        if self._scorer is not None:
            return [float(score) for score in self._scorer(pairs)]

        if self._model is None:
            raise RerankerInitializationError("Reranker model is not initialized.")

        scores = self._model.predict(list(pairs), batch_size=self.batch_size, show_progress_bar=False)
        return [float(score) for score in scores]

    def rerank(self, query: str, candidates: list[dict[str, Any]], top_n: int) -> list[dict[str, Any]]:
        """Rerank retrieved candidates and attach stable rank metadata."""
        if top_n <= 0:
            raise ValueError("top_n must be greater than 0 for reranking.")

        if not candidates:
            return []

        pairs = [(query, candidate["text"]) for candidate in candidates]
        scores = self._score_pairs(pairs)

        reranked: list[dict[str, Any]] = []
        for candidate, score in zip(candidates, scores, strict=True):
            enriched = dict(candidate)
            original_rank = int(enriched.get("original_rank", enriched.get("rank", 0)))
            enriched["original_rank"] = original_rank
            enriched["reranker_score"] = float(score)
            reranked.append(enriched)

        reranked.sort(
            key=lambda item: (
                -item["reranker_score"],
                item["original_rank"],
            )
        )

        for index, item in enumerate(reranked, start=1):
            item["reranked_rank"] = index

        return reranked[:top_n]
