"""
WebSocket gateway — /ws/table/{table_id}?token=<jwt>

Flow:
  1. Accept WS upgrade
  2. Validate token → close 4001 if invalid
  3. Look up table in persistence → close 4004 if missing
  4. Get/create TableSessionManager from registry
  5. Register connection in broadcaster
  6. Dispatch loop: parse ClientEnvelope → route to session_manager
  7. finally: unregister + disconnect (ALWAYS runs, even on exception)

The try/finally in the main handler is the single most critical correctness item.
It guarantees that ghost sessions cannot accumulate regardless of how the handler exits.
"""
from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from ..auth.service import AuthService
from ..persistence.adapter import PersistenceAdapter
from ..realtime.schemas import (
    ActionPayload,
    CardDTO,
    CardsDealtPayload,
    ChatPayload,
    ClientEnvelope,
    ClientMessageType,
    ErrorPayload,
    JoinTablePayload,
    ServerEnvelope,
    ServerEventType,
)
from ..realtime.ws_broadcaster import WebSocketBroadcaster
from ..session_registry import TableSessionRegistry
from ..sessions.session_manager import TableSessionManager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.websocket("/ws/table/{table_id}")
async def ws_table_endpoint(
    websocket: WebSocket,
    table_id: str,
    token: str = "",
) -> None:
    await websocket.accept()

    # Read singletons from app.state (same as HTTP routes via request.app.state)
    persistence: PersistenceAdapter = websocket.app.state.persistence
    broadcaster: WebSocketBroadcaster = websocket.app.state.broadcaster
    registry: TableSessionRegistry = websocket.app.state.registry
    auth_service: AuthService = websocket.app.state.auth_service

    # ------------------------------------------------------------------
    # 1. Token validation
    # ------------------------------------------------------------------
    if not token:
        await websocket.close(code=4001, reason="unauthorized")
        return

    try:
        user = await auth_service.verify_token(token)
    except ValueError:
        await websocket.close(code=4001, reason="unauthorized")
        return

    # ------------------------------------------------------------------
    # 2. Table lookup
    # ------------------------------------------------------------------
    table_record = await persistence.get_table(table_id)
    if table_record is None:
        await websocket.close(code=4004, reason="table_not_found")
        return

    # ------------------------------------------------------------------
    # 3. Get / create session manager
    # ------------------------------------------------------------------
    session_manager: TableSessionManager = await registry.get_or_create(
        table_id=table_id,
        club_id=table_record.club_id,
        config=table_record.config,
        persistence=persistence,
        broadcaster=broadcaster,
    )

    # ------------------------------------------------------------------
    # 4. Register connection (role unknown until JOIN_TABLE)
    # ------------------------------------------------------------------
    connection_id = str(uuid.uuid4())
    await broadcaster.register(table_id, user.id, websocket, role="unknown")

    # ------------------------------------------------------------------
    # 5. Dispatch loop
    # ------------------------------------------------------------------
    try:
        async for text in websocket.iter_text():
            await _dispatch_message(
                text=text,
                user_id=user.id,
                display_name=user.display_name,
                table_id=table_id,
                connection_id=connection_id,
                session_manager=session_manager,
                broadcaster=broadcaster,
                websocket=websocket,
            )
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Unexpected error in WS handler for table %s user %s", table_id, user.id)
    finally:
        # CRITICAL: always runs — prevents ghost sessions
        await broadcaster.unregister(table_id, user.id)
        await session_manager.disconnect(user.id)


# ---------------------------------------------------------------------------
# Message dispatcher
# ---------------------------------------------------------------------------


async def _dispatch_message(
    *,
    text: str,
    user_id: str,
    display_name: str,
    table_id: str,
    connection_id: str,
    session_manager: TableSessionManager,
    broadcaster: WebSocketBroadcaster,
    websocket: WebSocket,
) -> None:
    """
    Parse one client message and route it to the session manager.
    Never raises — all errors become ERROR events.
    """
    # Parse envelope
    try:
        envelope = ClientEnvelope.model_validate_json(text)
    except (ValueError, ValidationError) as exc:
        await _send_error(
            websocket, table_id,
            code="INVALID_MESSAGE",
            message=f"Could not parse message: {exc}",
            request_id=None,
            seq=0,
        )
        return

    req_id = envelope.request_id

    try:
        match envelope.type:

            case ClientMessageType.JOIN_TABLE:
                payload = JoinTablePayload.model_validate(envelope.payload)
                if payload.role == "player":
                    result = await session_manager.join_as_player(
                        user_id=user_id,
                        display_name=display_name,
                        connection_id=connection_id,
                    )
                    if not result.success:
                        await _send_error(
                            websocket, table_id,
                            code=result.error_code.value if result.error_code else "JOIN_FAILED",
                            message=result.error_message or "Could not join table.",
                            request_id=req_id,
                            seq=0,
                        )
                    else:
                        await broadcaster.update_role(table_id, user_id, "player")
                else:
                    await session_manager.join_as_spectator(
                        user_id=user_id,
                        display_name=display_name,
                        connection_id=connection_id,
                    )
                    await broadcaster.update_role(table_id, user_id, "spectator")

            case ClientMessageType.ACTION:
                payload = ActionPayload.model_validate(envelope.payload)
                await session_manager.handle_action(
                    user_id=user_id,
                    action_type=payload.action,
                    amount=payload.amount,
                    request_id=req_id,
                )

            case ClientMessageType.CHAT:
                payload = ChatPayload.model_validate(envelope.payload)
                await session_manager.handle_chat(
                    user_id=user_id,
                    display_name=display_name,
                    message=payload.message,
                )

            case ClientMessageType.SIT_OUT:
                await session_manager.sit_out(user_id)

            case ClientMessageType.SIT_IN:
                await session_manager.sit_in(user_id)

            case ClientMessageType.LEAVE_TABLE:
                await session_manager.leave(user_id)

            case ClientMessageType.SYNC_REQUEST:
                await session_manager.send_sync(user_id)

    except ValidationError as exc:
        await _send_error(
            websocket, table_id,
            code="INVALID_PAYLOAD",
            message=str(exc),
            request_id=req_id,
            seq=0,
        )
    except ValueError as exc:
        await _send_error(
            websocket, table_id,
            code="INVALID_ACTION",
            message=str(exc),
            request_id=req_id,
            seq=0,
        )
    except Exception:
        logger.exception("Error dispatching %s from user %s", envelope.type, user_id)
        await _send_error(
            websocket, table_id,
            code="INTERNAL_ERROR",
            message="An internal error occurred. Please try again.",
            request_id=req_id,
            seq=0,
        )


# ---------------------------------------------------------------------------
# Error helper
# ---------------------------------------------------------------------------


async def _send_error(
    websocket: WebSocket,
    table_id: str,
    code: str,
    message: str,
    request_id: str | None,
    seq: int,
) -> None:
    """Send an ERROR event envelope. Never raises."""
    try:
        env = ServerEnvelope.build(
            seq=seq,
            table_id=table_id,
            event_type=ServerEventType.ERROR,
            payload=ErrorPayload(
                code=code,
                message=message,
                request_id=request_id,
            ),
        )
        await websocket.send_text(env.to_json())
    except Exception as exc:
        logger.warning("Failed to send ERROR event: %s", exc)
