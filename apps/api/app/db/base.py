from sqlalchemy.orm import DeclarativeBase

from app.db.models.chunk_embedding import ChunkEmbedding
from app.db.models.chunk import Chunk
from app.db.models.project import Project
from app.db.models.source_object import SourceObject


class _ModelRegistry:
    chunk = Chunk
    chunk_embedding = ChunkEmbedding
    project = Project
    source_object = SourceObject


from app.db.session import Base  # noqa: E402
