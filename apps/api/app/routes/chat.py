import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models.chunk import Chunk
from app.db.models.project import Project
from app.db.models.source_object import SourceObject
from app.dependencies import get_db

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    project_id: str
    message: str


class ChatMatch(BaseModel):
    chunk_id: str
    snippet: str


class ChatResponse(BaseModel):
    response: str
    matches: list[ChatMatch]


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    project = db.query(Project).filter(Project.id == payload.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    terms = [term for term in re.findall(r"[A-Za-z0-9_]+", payload.message.lower()) if len(term) > 2][:8]
    chunk_query = (
        db.query(Chunk)
        .join(SourceObject, SourceObject.id == Chunk.source_object_id)
        .filter(SourceObject.project_id == payload.project_id)
    )
    if terms:
        filters = [Chunk.content.ilike(f"%{term}%") for term in terms]
        chunk_query = chunk_query.filter(or_(*filters))

    hits = chunk_query.order_by(Chunk.created_at.desc()).limit(3).all()
    matches = [
        ChatMatch(
            chunk_id=hit.id,
            snippet=(hit.content[:220] + "...") if len(hit.content) > 220 else hit.content,
        )
        for hit in hits
    ]

    if matches:
        summary = " | ".join(match.snippet for match in matches)
        response = f"Project '{project.name}' context: {summary}"
    else:
        response = (
            f"No indexed context matched this message for project '{project.name}'. "
            "Ingest sources first, then retry."
        )

    return ChatResponse(response=response, matches=matches)
