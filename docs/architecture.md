# Architecture

## Services
- `apps/api`: FastAPI service exposing health, project, and chat endpoints.
- `apps/ui`: Streamlit UI with Chat and Dashboard pages.
- `infra`: Docker compose and Dockerfiles for local orchestration.

## Data Layer
- Postgres is the primary store.
- SQLAlchemy models: `projects`, `source_objects`, `chunks`.

## Runtime Flow
1. UI calls API over HTTP.
2. API reads/writes project metadata to Postgres.
3. Chat route currently returns an echo stub and is ready for LLM integration.
