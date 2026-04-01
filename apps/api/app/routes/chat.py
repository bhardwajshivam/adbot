from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models.project import Project
from app.dependencies import get_db
from app.services.rag_pipeline import build_default_pipeline

router = APIRouter(prefix="/chat", tags=["chat"])


@lru_cache(maxsize=1)
def get_pipeline():
    return build_default_pipeline()


class ChatRequest(BaseModel):
    project_id: str
    message: str
    top_k: int | None = Field(default=None, ge=1)
    top_n: int | None = Field(default=None, ge=1)


class ChatMatch(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    retrieval_score: float
    reranker_score: float
    original_rank: int
    reranked_rank: int


class ChatResponse(BaseModel):
    response: str
    matches: list[ChatMatch]


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    project = db.query(Project).filter(Project.id == payload.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    pipeline = get_pipeline()
    pipeline_result = pipeline.run(
        query=payload.message,
        project_id=payload.project_id,
        db=db,
        top_k=payload.top_k,
        top_n=payload.top_n,
    )
    matches = [ChatMatch(**candidate) for candidate in pipeline_result.candidates]

    if matches:
        summary = " | ".join(
            (match.text[:220] + "...") if len(match.text) > 220 else match.text for match in matches
        )
        response = f"Project '{project.name}' context: {summary}"
    else:
        response = (
            f"No indexed context matched this message for project '{project.name}'. "
            "Ingest sources first, then retry."
        )

    return ChatResponse(response=response, matches=matches)
