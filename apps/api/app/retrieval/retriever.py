from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models.chunk import Chunk
from app.db.models.source_object import SourceObject


def _tokenize_query(query: str) -> list[str]:
    """Return stable keyword tokens used by the current lexical retriever."""
    return [term for term in re.findall(r"[A-Za-z0-9_]+", query.lower()) if len(term) > 2][:8]


def _compute_retrieval_score(text: str, terms: Sequence[str]) -> float:
    """Expose a lightweight lexical overlap score without changing retrieval order."""
    if not terms:
        return 0.0

    lowered = text.lower()
    return float(sum(1 for term in terms if term in lowered))


class ChunkRetriever:
    """Preserves the current retrieval behavior and returns structured candidates."""

    def retrieve(self, query: str, project_id: str, db: Session, top_k: int) -> list[dict[str, Any]]:
        terms = _tokenize_query(query)
        chunk_query = (
            db.query(Chunk, SourceObject.external_id)
            .join(SourceObject, SourceObject.id == Chunk.source_object_id)
            .filter(SourceObject.project_id == project_id)
        )
        if terms:
            filters = [Chunk.content.ilike(f"%{term}%") for term in terms]
            chunk_query = chunk_query.filter(or_(*filters))

        hits = chunk_query.order_by(Chunk.created_at.desc()).limit(top_k).all()

        candidates: list[dict[str, Any]] = []
        for index, (chunk, doc_id) in enumerate(hits, start=1):
            candidates.append(
                {
                    "chunk_id": chunk.id,
                    "doc_id": doc_id,
                    "text": chunk.content,
                    "retrieval_score": _compute_retrieval_score(chunk.content, terms),
                    "rank": index,
                }
            )

        return candidates
