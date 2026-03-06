from fastapi import APIRouter

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
def chat(payload: dict) -> dict:
    project_id = payload.get("project_id")
    message = payload.get("message", "")
    response = f"Echo for project {project_id or 'unknown'}: {message}".strip()
    return {"response": response}
