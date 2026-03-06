from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models.chunk import Chunk
from app.db.models.project import Project
from app.db.models.source_object import SourceObject
from app.dependencies import get_db

router = APIRouter(prefix="/projects", tags=["projects"])


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
    db.commit()
    db.refresh(source_object)
    db.refresh(chunk)

    return SourceSeedResponse(source_object_id=source_object.id, chunk_id=chunk.id)
