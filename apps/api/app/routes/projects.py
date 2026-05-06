from functools import lru_cache
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.chunk import Chunk
from app.db.models.chunk_embedding import ChunkEmbedding
from app.db.models.project import Project
from app.db.models.source_object import SourceObject
from app.dependencies import get_db
from app.services.embeddings import build_default_embedder

router = APIRouter(prefix="/projects", tags=["projects"])


@lru_cache(maxsize=1)
def get_embedder():
    return build_default_embedder(
        model_name=settings.embedding_model_name,
        dimensions=settings.embedding_dimensions,
    )


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectRead(BaseModel):
    id: str
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class SourceSeedRequest(BaseModel):
    connector: str = "manual"
    external_id: str
    content: str


class SourceSeedResponse(BaseModel):
    source_object_id: str
    chunk_id: str
    embedding_id: str | None = None


@router.get("", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    return db.query(Project).order_by(Project.created_at.desc()).all()


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    existing = db.query(Project).filter(Project.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Project with that name already exists")

    project = Project(name=payload.name, description=payload.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.post("/{project_id}/sources", response_model=SourceSeedResponse, status_code=status.HTTP_201_CREATED)
def seed_project_source(
    project_id: str,
    payload: SourceSeedRequest,
    db: Session = Depends(get_db),
) -> SourceSeedResponse:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    source_object = SourceObject(
        project_id=project_id,
        connector=payload.connector,
        external_id=payload.external_id,
    )
    db.add(source_object)
    db.flush()

    chunk = Chunk(source_object_id=source_object.id, content=payload.content)
    db.add(chunk)
    db.flush()

    if settings.vector_retrieval_enabled:
        embedder = get_embedder()
        chunk_embedding = ChunkEmbedding(
            chunk_id=chunk.id,
            model_name=embedder.model_name,
            embedding=embedder.embed_texts([payload.content])[0],
        )
        db.add(chunk_embedding)
        db.flush()
        chunk.embedding_id = chunk_embedding.id

    db.commit()
    db.refresh(source_object)
    db.refresh(chunk)

    return SourceSeedResponse(source_object_id=source_object.id, chunk_id=chunk.id, embedding_id=chunk.embedding_id)
