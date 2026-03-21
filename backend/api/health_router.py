"""GET /health — public endpoint, no auth required."""
from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ..config import settings

router = APIRouter(tags=["health"])

VERSION = "0.1.0"


class HealthResponse(BaseModel):
    status: str
    app_env: str
    active_tables: int
    version: str
    state_persistence: str


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    registry = request.app.state.registry
    persistence_mode = (
        "in_memory_volatile"
        if settings.app_env != "production"
        else settings.database_url.split(":")[0]
    )
    return HealthResponse(
        status="ok",
        app_env=settings.app_env,
        active_tables=registry.active_count,
        version=VERSION,
        state_persistence=persistence_mode,
    )
