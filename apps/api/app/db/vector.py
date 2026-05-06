from __future__ import annotations

from typing import Any

from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON, TypeDecorator


try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - exercised only before optional dependency install
    Vector = None  # type: ignore[assignment]


class EmbeddingVector(TypeDecorator):
    """Use pgvector on Postgres and JSON elsewhere for local tests."""

    impl = JSON
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            if Vector is not None:
                return dialect.type_descriptor(Vector(self.dimensions))
            return dialect.type_descriptor(postgresql.ARRAY(postgresql.DOUBLE_PRECISION))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Any, dialect):
        if value is None:
            return None
        return [float(item) for item in value]
