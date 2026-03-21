"""
Dependency injection for the FastAPI application.

Singletons (persistence, broadcaster, registry, auth_service) are stored on
app.state and retrieved per-request via these helpers.

Usage in routes:
    current_user: User = Depends(get_current_user)
    persistence: PersistenceAdapter = Depends(get_persistence)
"""
from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth.models import User
from .auth.service import AuthService
from .persistence.adapter import PersistenceAdapter
from .realtime.ws_broadcaster import WebSocketBroadcaster
from .session_registry import TableSessionRegistry

_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Singleton accessors (read from app.state)
# ---------------------------------------------------------------------------

def get_persistence(request: Request) -> PersistenceAdapter:
    return request.app.state.persistence


def get_broadcaster(request: Request) -> WebSocketBroadcaster:
    return request.app.state.broadcaster


def get_registry(request: Request) -> TableSessionRegistry:
    return request.app.state.registry


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


# ---------------------------------------------------------------------------
# Per-request auth
# ---------------------------------------------------------------------------

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """
    Extract Bearer token from Authorization header, verify, return User.
    Raises HTTP 401 on any failure.
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail={"error": "UNAUTHORIZED", "message": "Authorization header required."},
        )
    try:
        return await auth_service.verify_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail={"error": "INVALID_TOKEN", "message": str(exc)},
        )


# ---------------------------------------------------------------------------
# Error response helper
# ---------------------------------------------------------------------------

def http_error(code: str, message: str, status: int = 400) -> HTTPException:
    """Return a consistent HTTPException with our standard error JSON shape."""
    return HTTPException(
        status_code=status,
        detail={"error": code, "message": message},
    )
