from __future__ import annotations

from app.config import Settings
from app.services.rag_pipeline import RetrievalRerankPipeline, retrieve_and_rerank
from app.services.reranker import CrossEncoderReranker
from app.retrieval.retriever import ChunkRetriever


class StubRetriever(ChunkRetriever):
    def __init__(self, candidates: list[dict]) -> None:
        self._candidates = candidates

    def retrieve(self, query: str, project_id: str, db, top_k: int) -> list[dict]:
        return self._candidates[:top_k]


def test_normal_reranking_flow() -> None:
    candidates = [
        {"chunk_id": "c1", "doc_id": "d1", "text": "short note", "retrieval_score": 0.1, "rank": 1},
        {"chunk_id": "c2", "doc_id": "d2", "text": "budget planning update", "retrieval_score": 0.2, "rank": 2},
        {"chunk_id": "c3", "doc_id": "d3", "text": "operations memo", "retrieval_score": 0.3, "rank": 3},
    ]
    reranker = CrossEncoderReranker(
        model_name="stub",
        device="cpu",
        batch_size=2,
        scorer=lambda pairs: [0.1, 0.95, 0.4],
    )

    reranked = reranker.rerank("budget", candidates, top_n=2)

    assert [item["chunk_id"] for item in reranked] == ["c2", "c3"]
    assert reranked[0]["original_rank"] == 2
    assert reranked[0]["reranked_rank"] == 1


def test_fewer_retrieved_docs_than_top_n() -> None:
    candidates = [{"chunk_id": "c1", "doc_id": "d1", "text": "only one", "retrieval_score": 0.5, "rank": 1}]
    reranker = CrossEncoderReranker(
        model_name="stub",
        device="cpu",
        batch_size=2,
        scorer=lambda pairs: [0.7],
    )

    reranked = reranker.rerank("one", candidates, top_n=3)

    assert len(reranked) == 1
    assert reranked[0]["reranked_rank"] == 1


def test_empty_candidates() -> None:
    reranker = CrossEncoderReranker(
        model_name="stub",
        device="cpu",
        batch_size=2,
        scorer=lambda pairs: [],
    )

    assert reranker.rerank("query", [], top_n=3) == []


def test_deterministic_sorting_behavior() -> None:
    candidates = [
        {"chunk_id": "c1", "doc_id": "d1", "text": "alpha", "retrieval_score": 1.0, "rank": 1},
        {"chunk_id": "c2", "doc_id": "d2", "text": "beta", "retrieval_score": 0.9, "rank": 2},
    ]
    reranker = CrossEncoderReranker(
        model_name="stub",
        device="cpu",
        batch_size=2,
        scorer=lambda pairs: [0.5, 0.5],
    )

    reranked = reranker.rerank("query", candidates, top_n=2)

    assert [item["chunk_id"] for item in reranked] == ["c1", "c2"]
    assert reranked[0]["reranked_rank"] == 1
    assert reranked[1]["reranked_rank"] == 2


def test_config_loading(monkeypatch) -> None:
    monkeypatch.setenv("RETRIEVAL_TOP_K", "15")
    monkeypatch.setenv("RERANKER_MODEL_NAME", "cross-encoder/test")
    monkeypatch.setenv("RERANKER_TOP_N", "4")
    loaded = Settings()

    assert loaded.retrieval_top_k == 15
    assert loaded.reranker_model_name == "cross-encoder/test"
    assert loaded.reranker_top_n == 4


def test_pipeline_handles_empty_results() -> None:
    pipeline = RetrievalRerankPipeline(
        retriever=StubRetriever([]),
        reranker=None,
        app_settings=Settings(reranker_enabled=False, retrieval_top_k=5, reranker_top_n=3),
    )

    result = pipeline.run(query="query", project_id="project", db=None)

    assert result.candidates == []
    assert result.timings.retrieval_ms >= 0.0


def test_retrieve_and_rerank_helper_uses_pipeline() -> None:
    pipeline = RetrievalRerankPipeline(
        retriever=StubRetriever(
            [{"chunk_id": "c1", "doc_id": "d1", "text": "alpha", "retrieval_score": 0.4, "rank": 1}]
        ),
        reranker=CrossEncoderReranker(
            model_name="stub",
            device="cpu",
            batch_size=2,
            scorer=lambda pairs: [0.8],
        ),
        app_settings=Settings(reranker_enabled=True, retrieval_top_k=5, reranker_top_n=3),
    )

    result = retrieve_and_rerank(
        query="alpha",
        project_id="project",
        db=None,
        pipeline=pipeline,
    )

    assert result[0]["chunk_id"] == "c1"
    assert result[0]["reranker_score"] == 0.8
