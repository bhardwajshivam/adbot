from __future__ import annotations

from collections.abc import Sequence

from app.config import Settings
from app.db.models.chunk import Chunk
from app.db.models.chunk_embedding import ChunkEmbedding
from app.db.models.project import Project
from app.db.models.source_object import SourceObject
from app.retrieval.retriever import ChunkRetriever
from app.services.embeddings import TextEmbedder


def test_vector_retrieval_finds_semantic_match_without_keyword_overlap(db_session):
    project = Project(name="Vector Project")
    db_session.add(project)
    db_session.flush()

    source = SourceObject(project_id=project.id, connector="manual", external_id="doc-vector")
    db_session.add(source)
    db_session.flush()

    relevant = Chunk(source_object_id=source.id, content="Q4 budget reduction and media spend notes")
    unrelated = Chunk(source_object_id=source.id, content="Office snack inventory and desk setup")
    db_session.add_all([relevant, unrelated])
    db_session.flush()

    db_session.add_all(
        [
            ChunkEmbedding(chunk_id=relevant.id, model_name="stub", embedding=[1.0, 0.0]),
            ChunkEmbedding(chunk_id=unrelated.id, model_name="stub", embedding=[0.0, 1.0]),
        ]
    )
    db_session.commit()

    def encode(texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    retriever = ChunkRetriever(
        app_settings=Settings(
            vector_retrieval_enabled=True,
            embedding_model_name="stub",
            embedding_dimensions=2,
            reranker_enabled=False,
        ),
        embedder=TextEmbedder(model_name="stub", dimensions=2, encoder=encode),
    )

    results = retriever.retrieve(
        query="financial planning question",
        project_id=project.id,
        db=db_session,
        top_k=1,
    )

    assert len(results) == 1
    assert results[0]["chunk_id"] == relevant.id
    assert results[0]["vector_score"] > 0.99
