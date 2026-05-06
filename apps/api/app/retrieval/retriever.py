from __future__ import annotations

import math
import re
from collections.abc import Sequence
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.db.models.chunk import Chunk
from app.db.models.chunk_embedding import ChunkEmbedding
from app.db.models.source_object import SourceObject
from app.services.embeddings import TextEmbedder, build_default_embedder


def _tokenize_query(query: str) -> list[str]:
    """Return stable keyword tokens used by the lexical retriever."""
    return [term for term in re.findall(r"[A-Za-z0-9_]+", query.lower()) if len(term) > 2][:8]


def _compute_retrieval_score(text: str, terms: Sequence[str]) -> float:
    """Expose a lightweight lexical overlap score."""
    if not terms:
        return 0.0

    lowered = text.lower()
    return float(sum(1 for term in terms if term in lowered))


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    dot_product = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)


class ChunkRetriever:
    """Hybrid keyword + vector retriever for project-scoped chunks."""

    def __init__(
        self,
        app_settings: Settings = settings,
        embedder: TextEmbedder | None = None,
    ) -> None:
        self.app_settings = app_settings
        self._embedder = embedder

    @property
    def embedder(self) -> TextEmbedder:
        if self._embedder is None:
            self._embedder = build_default_embedder(
                model_name=self.app_settings.embedding_model_name,
                dimensions=self.app_settings.embedding_dimensions,
            )
        return self._embedder

    def retrieve(self, query: str, project_id: str, db: Session, top_k: int) -> list[dict[str, Any]]:
        terms = _tokenize_query(query)
        lexical_candidates = self._retrieve_lexical(terms=terms, project_id=project_id, db=db, top_k=top_k)
        vector_candidates = self._retrieve_vector(query=query, project_id=project_id, db=db, top_k=top_k)

        merged: dict[str, dict[str, Any]] = {}
        for candidate in lexical_candidates + vector_candidates:
            existing = merged.get(candidate["chunk_id"])
            if existing is None:
                merged[candidate["chunk_id"]] = candidate
                continue

            existing["retrieval_score"] = max(existing["retrieval_score"], candidate["retrieval_score"])
            existing["lexical_score"] = max(existing.get("lexical_score", 0.0), candidate.get("lexical_score", 0.0))
            existing["vector_score"] = max(existing.get("vector_score", 0.0), candidate.get("vector_score", 0.0))

        for item in merged.values():
            item["retrieval_score"] = item.get("lexical_score", 0.0) + item.get("vector_score", 0.0)

        ranked = sorted(
            merged.values(),
            key=lambda item: (
                -item["retrieval_score"],
                -item.get("vector_score", 0.0),
                item["created_at_sort"],
            ),
        )[:top_k]

        for index, item in enumerate(ranked, start=1):
            item["rank"] = index
            item.pop("created_at_sort", None)

        return ranked

    def _base_chunk_query(self, project_id: str, db: Session):
        return (
            db.query(Chunk, SourceObject.external_id)
            .join(SourceObject, SourceObject.id == Chunk.source_object_id)
            .filter(SourceObject.project_id == project_id)
        )

    def _retrieve_lexical(
        self,
        terms: Sequence[str],
        project_id: str,
        db: Session,
        top_k: int,
    ) -> list[dict[str, Any]]:
        chunk_query = self._base_chunk_query(project_id=project_id, db=db)
        if terms:
            filters = [Chunk.content.ilike(f"%{term}%") for term in terms]
            chunk_query = chunk_query.filter(or_(*filters))

        hits = chunk_query.order_by(Chunk.created_at.desc()).limit(top_k).all()
        candidates: list[dict[str, Any]] = []
        for chunk, doc_id in hits:
            lexical_score = _compute_retrieval_score(chunk.content, terms)
            candidates.append(
                {
                    "chunk_id": chunk.id,
                    "doc_id": doc_id,
                    "text": chunk.content,
                    "retrieval_score": lexical_score,
                    "lexical_score": lexical_score,
                    "vector_score": 0.0,
                    "created_at_sort": -chunk.created_at.timestamp(),
                }
            )
        return candidates

    def _retrieve_vector(self, query: str, project_id: str, db: Session, top_k: int) -> list[dict[str, Any]]:
        if not self.app_settings.vector_retrieval_enabled or not query.strip():
            return []

        query_embedding = self.embedder.embed_query(query)
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            return self._retrieve_vector_postgres(
                query_embedding=query_embedding,
                project_id=project_id,
                db=db,
                top_k=top_k,
            )
        return self._retrieve_vector_in_memory(
            query_embedding=query_embedding,
            project_id=project_id,
            db=db,
            top_k=top_k,
        )

    def _retrieve_vector_postgres(
        self,
        query_embedding: Sequence[float],
        project_id: str,
        db: Session,
        top_k: int,
    ) -> list[dict[str, Any]]:
        distance = ChunkEmbedding.embedding.op("<=>")(list(query_embedding)).label("distance")
        hits = (
            db.query(Chunk, SourceObject.external_id, distance)
            .join(SourceObject, SourceObject.id == Chunk.source_object_id)
            .join(ChunkEmbedding, ChunkEmbedding.chunk_id == Chunk.id)
            .filter(SourceObject.project_id == project_id)
            .order_by(distance.asc(), Chunk.created_at.desc())
            .limit(top_k)
            .all()
        )

        candidates: list[dict[str, Any]] = []
        for chunk, doc_id, distance_value in hits:
            vector_score = 1.0 - float(distance_value or 0.0)
            candidates.append(
                {
                    "chunk_id": chunk.id,
                    "doc_id": doc_id,
                    "text": chunk.content,
                    "retrieval_score": vector_score,
                    "lexical_score": 0.0,
                    "vector_score": vector_score,
                    "created_at_sort": -chunk.created_at.timestamp(),
                }
            )
        return candidates

    def _retrieve_vector_in_memory(
        self,
        query_embedding: Sequence[float],
        project_id: str,
        db: Session,
        top_k: int,
    ) -> list[dict[str, Any]]:
        hits = (
            db.query(Chunk, SourceObject.external_id, ChunkEmbedding.embedding)
            .join(SourceObject, SourceObject.id == Chunk.source_object_id)
            .join(ChunkEmbedding, ChunkEmbedding.chunk_id == Chunk.id)
            .filter(SourceObject.project_id == project_id)
            .all()
        )

        candidates: list[dict[str, Any]] = []
        for chunk, doc_id, chunk_embedding in hits:
            vector_score = _cosine_similarity(query_embedding, chunk_embedding)
            candidates.append(
                {
                    "chunk_id": chunk.id,
                    "doc_id": doc_id,
                    "text": chunk.content,
                    "retrieval_score": vector_score,
                    "lexical_score": 0.0,
                    "vector_score": vector_score,
                    "created_at_sort": -chunk.created_at.timestamp(),
                }
            )

        return sorted(candidates, key=lambda item: -item["vector_score"])[:top_k]
