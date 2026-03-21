"""
Shared pytest fixtures for backend integration tests.
"""
import asyncio
import pytest

from poker_engine.engine.models import TableConfig
from backend.persistence.memory import InMemoryPersistenceAdapter
from backend.realtime.broadcaster import CapturingBroadcaster
from backend.sessions.session_manager import TableSessionManager


@pytest.fixture
def config() -> TableConfig:
    return TableConfig(
        starting_stack=1000,
        small_blind=10,
        big_blind=20,
        turn_timer_seconds=30,
        max_players=6,
        house_rules=[],
    )


@pytest.fixture
def persistence() -> InMemoryPersistenceAdapter:
    return InMemoryPersistenceAdapter()


@pytest.fixture
def broadcaster() -> CapturingBroadcaster:
    return CapturingBroadcaster()


@pytest.fixture
def manager(config, persistence, broadcaster) -> TableSessionManager:
    return TableSessionManager(
        table_id="table-test",
        club_id="club-test",
        config=config,
        persistence=persistence,
        broadcaster=broadcaster,
    )
