from fastapi import FastAPI
from sqlalchemy import text

from app.config import settings
from app.db.base import Base
from app.db.session import engine
from app.routes.chat import router as chat_router
from app.routes.health import router as health_router
from app.routes.projects import router as projects_router

app = FastAPI(title=settings.app_name)


@app.on_event("startup")
def startup() -> None:
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)


app.include_router(health_router)
app.include_router(projects_router)
app.include_router(chat_router)
