from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import DATABASE_URL, FRONTEND_ORIGINS, SYNC_SHARED_SECRET
from .database import Base, build_database
from .routers import agents, incidents, resources, sync, teams


def create_app(
    database_url: str = DATABASE_URL,
    *,
    create_tables: bool = True,
    sync_shared_secret: str | None = None,
) -> FastAPI:
    engine, session_factory = build_database(database_url)

    def ensure_database_directory() -> None:
        if database_url.startswith("sqlite:///") and ":memory:" not in database_url:
            Path(database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)

    if create_tables:
        ensure_database_directory()
        Base.metadata.create_all(bind=engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if create_tables:
            ensure_database_directory()
            Base.metadata.create_all(bind=engine)
        yield
        engine.dispose()

    application = FastAPI(
        title="ResQMesh AI API",
        version="2.0.0",
        description="Persistent coordination records with a shared-secret LAN incident sync prototype.",
        lifespan=lifespan,
    )
    application.state.session_factory = session_factory
    application.state.sync_shared_secret = (
        SYNC_SHARED_SECRET if sync_shared_secret is None else sync_shared_secret
    )
    application.state.sync_dashboard_origins = tuple(FRONTEND_ORIGINS)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=FRONTEND_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    application.include_router(agents.router)
    application.include_router(incidents.router)
    application.include_router(teams.router)
    application.include_router(resources.router)
    application.include_router(sync.router)

    @application.get("/api/health", tags=["health"])
    def health():
        return {"status": "ok"}

    return application


app = create_app()
