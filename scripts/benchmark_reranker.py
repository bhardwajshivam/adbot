from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.append(str(API_ROOT))

from app.config import settings
from app.db.session import SessionLocal
from app.retrieval.retriever import ChunkRetriever
from app.services.rag_pipeline import PipelineResult, RetrievalRerankPipeline, build_default_pipeline


@dataclass(frozen=True)
class BenchmarkQuery:
    query: str
    expected_terms: list[str]


def load_queries(path: str | None) -> list[BenchmarkQuery]:
    if path is None:
        return [
            BenchmarkQuery(
                query="What changed in the Q4 marketing budget?",
                expected_terms=["budget", "marketing", "q4"],
            ),
            BenchmarkQuery(
                query="Which workstream mentioned operations?",
                expected_terms=["operations"],
            ),
        ]

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [BenchmarkQuery(query=item["query"], expected_terms=item["expected_terms"]) for item in payload]


def relevance_hit(candidates: list[dict], expected_terms: list[str], top_n: int) -> bool:
    lowered_terms = [term.lower() for term in expected_terms]
    for candidate in candidates[:top_n]:
        text = candidate["text"].lower()
        if any(term in text for term in lowered_terms):
            return True
    return False


def qualitative_example(result: PipelineResult) -> list[dict]:
    examples: list[dict] = []
    for item in result.candidates[:3]:
        examples.append(
            {
                "chunk_id": item["chunk_id"],
                "original_rank": item["original_rank"],
                "reranked_rank": item["reranked_rank"],
                "retrieval_score": item["retrieval_score"],
                "reranker_score": item["reranker_score"],
                "text_preview": item["text"][:120],
            }
        )
    return examples


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark retrieval-only vs retrieval plus reranking.")
    parser.add_argument("--project-id", required=True, help="Project to evaluate against.")
    parser.add_argument("--queries", help="Path to JSON query set.")
    parser.add_argument("--top-k", type=int, default=settings.retrieval_top_k)
    parser.add_argument("--top-n", type=int, default=settings.reranker_top_n)
    args = parser.parse_args()

    query_set = load_queries(args.queries)
    retrieval_only_pipeline = RetrievalRerankPipeline(
        retriever=ChunkRetriever(),
        reranker=None,
        app_settings=settings,
    )
    reranked_pipeline = build_default_pipeline()

    retrieval_only_rows: list[dict] = []
    reranked_rows: list[dict] = []

    with SessionLocal() as db:
        for item in query_set:
            retrieval_only = retrieval_only_pipeline.run(
                query=item.query,
                project_id=args.project_id,
                db=db,
                top_k=args.top_k,
                top_n=args.top_n,
            )
            reranked = reranked_pipeline.run(
                query=item.query,
                project_id=args.project_id,
                db=db,
                top_k=args.top_k,
                top_n=args.top_n,
            )

            retrieval_only_rows.append(
                {
                    "query": item.query,
                    "latency_ms": retrieval_only.timings.total_ms,
                    "top1_hit": relevance_hit(retrieval_only.candidates, item.expected_terms, top_n=1),
                    "top3_hit": relevance_hit(retrieval_only.candidates, item.expected_terms, top_n=3),
                    "examples": qualitative_example(retrieval_only),
                }
            )
            reranked_rows.append(
                {
                    "query": item.query,
                    "latency_ms": reranked.timings.total_ms,
                    "top1_hit": relevance_hit(reranked.candidates, item.expected_terms, top_n=1),
                    "top3_hit": relevance_hit(reranked.candidates, item.expected_terms, top_n=3),
                    "examples": qualitative_example(reranked),
                }
            )

    def summarize(rows: list[dict]) -> dict:
        count = max(len(rows), 1)
        return {
            "avg_latency_ms": sum(row["latency_ms"] for row in rows) / count,
            "top1_relevance_proxy": sum(1 for row in rows if row["top1_hit"]) / count,
            "top3_hit_rate_proxy": sum(1 for row in rows if row["top3_hit"]) / count,
            "queries": rows,
        }

    summary = {
        "project_id": args.project_id,
        "top_k": args.top_k,
        "top_n": args.top_n,
        "retrieval_only": summarize(retrieval_only_rows),
        "retrieval_plus_reranking": summarize(reranked_rows),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
