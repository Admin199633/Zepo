"""
Harness-flavoured app factory.

Creates a live TestClient with:
  - lifespan triggered (app.state populated)
  - _TestAuthService injected (deterministic OTP "123456")
  - BETWEEN_HANDS_DELAY overridden for fast CI execution
"""
from __future__ import annotations

import backend.sessions.session_manager as _sm
import poker_engine.engine.models as _engine_models
from backend.main import create_app
from fastapi.testclient import TestClient
from tests.test_app_integration import _TestAuthService

_DEFAULT_DELAY = 3.0
_DEFAULT_VALID_TURN_TIMERS = frozenset(_engine_models.VALID_TURN_TIMERS)


def make_test_client(between_hands_delay: float = 0.05) -> TestClient:
    """
    Return a live TestClient with lifespan run and auth overridden.

    The caller MUST call `client.__exit__(None, None, None)` in teardown
    (or use the client as a context manager) to avoid resource leaks.

    Patches applied (restored by restore_delays()):
      - BETWEEN_HANDS_DELAY → between_hands_delay (fast hands between tests)
      - VALID_TURN_TIMERS → adds {2} so turn_timer_seconds=2 is valid in tests
    """
    _sm.BETWEEN_HANDS_DELAY = between_hands_delay
    # Allow short turn timers in test mode (2 s for S6 timeout scenario).
    # This is a runtime patch only — no engine source file is modified.
    _engine_models.VALID_TURN_TIMERS = set(_DEFAULT_VALID_TURN_TIMERS) | {2}

    _app = create_app()
    client = TestClient(_app, raise_server_exceptions=True)
    client.__enter__()  # trigger lifespan → app.state populated
    _app.state.auth_service = _TestAuthService(_app.state.persistence)
    return client


def restore_delays() -> None:
    """Reset module-level constants to production defaults. Call in fixture teardown."""
    _sm.BETWEEN_HANDS_DELAY = _DEFAULT_DELAY
    _engine_models.VALID_TURN_TIMERS = set(_DEFAULT_VALID_TURN_TIMERS)
