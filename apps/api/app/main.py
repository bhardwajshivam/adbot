from fastapi import FastAPI

from app.config import settings
from app.db.base import Base
from app.db.session import engine
from app.routes.chat import router as chat_router
from app.routes.health import router as health_router
from app.routes.projects import router as projects_router

app = FastAPI(title=settings.app_name)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


app.include_router(health_router)
app.include_router(projects_router)
app.include_router(chat_router)
