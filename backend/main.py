"""
FastAPI application factory.

Usage:
    uvicorn backend.main:app --reload

All singletons are created in the lifespan context and attached to app.state.
No singleton is created at import time (allows clean testing with overrides).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.auth_router import router as auth_router
from .api.clubs_router import router as clubs_router
from .api.health_router import router as health_router
from .api.tables_router import router as tables_router
from .auth.service import ConsoleAuthService
from .config import settings
from .dev_seed import seed_demo_data
from .persistence.memory import InMemoryPersistenceAdapter
from .persistence.sqlite_adapter import SqlitePersistenceAdapter
from .realtime.ws_broadcaster import WebSocketBroadcaster
from .realtime.ws_router import router as ws_router
from .session_registry import TableSessionRegistry


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- Startup ----
    if settings.use_sqlite:
        persistence = SqlitePersistenceAdapter(settings.database_url)
        await persistence.initialize()
    else:
        persistence = InMemoryPersistenceAdapter()
    broadcaster = WebSocketBroadcaster()
    registry = TableSessionRegistry()
    auth_service = ConsoleAuthService(persistence)

    app.state.persistence = persistence
    app.state.broadcaster = broadcaster
    app.state.registry = registry
    app.state.auth_service = auth_service

    if settings.app_env != "production":
        await seed_demo_data(persistence)

    yield

    # ---- Shutdown ----
    if settings.use_sqlite and isinstance(persistence, SqlitePersistenceAdapter):
        await persistence._engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Zepo Poker API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — allow all origins in dev; tighten in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.app_env != "production" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(clubs_router)
    app.include_router(tables_router)
    app.include_router(ws_router)

    return app


# Module-level instance used by uvicorn
app = create_app()
