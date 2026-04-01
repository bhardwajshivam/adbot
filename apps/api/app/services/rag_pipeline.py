from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.retrieval.retriever import ChunkRetriever
from app.services.reranker import CrossEncoderReranker, RerankerInitializationError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineTimings:
    retrieval_ms: float
    reranking_ms: float
    total_ms: float


@dataclass(frozen=True)
class PipelineResult:
    candidates: list[dict[str, Any]]
    timings: PipelineTimings


class RetrievalRerankPipeline:
    """Orchestrates retrieval followed by cross-encoder reranking."""

    def __init__(
        self,
        retriever: ChunkRetriever,
        reranker: CrossEncoderReranker | None,
        app_settings: Settings = settings,
    ) -> None:
        self.retriever = retriever
        self.reranker = reranker
        self.app_settings = app_settings

    def run(
        self,
        query: str,
        project_id: str,
        db: Session,
        top_k: int | None = None,
        top_n: int | None = None,
    ) -> PipelineResult:
        start = time.perf_counter()
        retrieval_start = start
        candidates = self.retriever.retrieve(
            query=query,
            project_id=project_id,
            db=db,
            top_k=top_k or self.app_settings.retrieval_top_k,
        )
        retrieval_ms = (time.perf_counter() - retrieval_start) * 1000

        if not candidates:
            timings = PipelineTimings(
                retrieval_ms=retrieval_ms,
                reranking_ms=0.0,
                total_ms=(time.perf_counter() - start) * 1000,
            )
            logger.info(
                "rag_pipeline retrieval_ms=%.2f reranking_ms=%.2f total_ms=%.2f candidates=0",
                timings.retrieval_ms,
                timings.reranking_ms,
                timings.total_ms,
            )
            return PipelineResult(candidates=[], timings=timings)

        rerank_start = time.perf_counter()
        if self.reranker and self.app_settings.reranker_enabled:
            final_candidates = self.reranker.rerank(
                query=query,
                candidates=candidates,
                top_n=top_n or self.app_settings.reranker_top_n,
            )
        else:
            final_candidates = []
            for index, candidate in enumerate(candidates[: top_n or self.app_settings.reranker_top_n], start=1):
                item = dict(candidate)
                item["original_rank"] = int(item.get("rank", index))
                item["reranked_rank"] = index
                item["reranker_score"] = item["retrieval_score"]
                final_candidates.append(item)
        reranking_ms = (time.perf_counter() - rerank_start) * 1000
        total_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "rag_pipeline retrieval_ms=%.2f reranking_ms=%.2f total_ms=%.2f top_k=%s top_n=%s",
            retrieval_ms,
            reranking_ms,
            total_ms,
            top_k or self.app_settings.retrieval_top_k,
            top_n or self.app_settings.reranker_top_n,
        )
        for item in final_candidates:
            logger.info(
                "rag_pipeline_rank chunk_id=%s original_rank=%s reranked_rank=%s retrieval_score=%.4f reranker_score=%.4f",
                item["chunk_id"],
                item["original_rank"],
                item["reranked_rank"],
                item["retrieval_score"],
                item["reranker_score"],
            )

        return PipelineResult(
            candidates=final_candidates,
            timings=PipelineTimings(
                retrieval_ms=retrieval_ms,
                reranking_ms=reranking_ms,
                total_ms=total_ms,
            ),
        )


def build_default_pipeline(app_settings: Settings = settings) -> RetrievalRerankPipeline:
    reranker = None
    if app_settings.reranker_enabled:
        try:
            reranker = CrossEncoderReranker(
                model_name=app_settings.reranker_model_name,
                device=app_settings.reranker_device,
                batch_size=app_settings.reranker_batch_size,
            )
        except RerankerInitializationError:
            logger.exception("Reranker initialization failed; continuing with retrieval-only pipeline.")

    return RetrievalRerankPipeline(
        retriever=ChunkRetriever(),
        reranker=reranker,
        app_settings=app_settings,
    )


def retrieve_and_rerank(
    query: str,
    project_id: str,
    db: Session,
    top_k: int | None = None,
    top_n: int | None = None,
    pipeline: RetrievalRerankPipeline | None = None,
) -> list[dict[str, Any]]:
    """Return final contexts after retrieval and reranking."""
    active_pipeline = pipeline or build_default_pipeline()
    return active_pipeline.run(query=query, project_id=project_id, db=db, top_k=top_k, top_n=top_n).candidates
