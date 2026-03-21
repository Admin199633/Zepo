# Task Breakdown — light-persistence-layer

> Date: 2026-03-19

---

## Pre-Implementation Research (T0 — No Files Written)

Before touching any code, read and confirm:

1. `backend/persistence/sqlite_adapter.py` — all schema definitions and method stubs
2. `backend/persistence/memory.py` — the reference implementation for every method
3. `backend/persistence/adapter.py` — the full interface contract
4. `backend/stats/models.py` — confirm `PlayerStats` fields: `wins`, `total_won`, `total_lost`
5. `backend/chat/models.py` — confirm `ChatMessage` has `is_system: bool` field
6. `poker_engine/engine/models.py` — confirm `PlayerSession` fields: `user_id`, `display_name`, `seat_index`, `stack`, `status`, `timeout_count`, `is_connected`, `disconnect_at`
7. `requirements.txt` — confirm whether `aiosqlite` and `sqlalchemy[asyncio]` are present

**Schema gaps identified (must fix in T1):**
- `player_stats_table`: `hands_won` → `wins`; `total_winnings` → `total_won`; `biggest_pot` → `total_lost`
- `chat_messages_table`: missing `is_system` (Boolean) column
- `player_sessions_table`: missing `timeout_count` (Integer, default=0) and `disconnect_at` (Float, nullable) columns

---

## T1 — Fix Schema and Add Dependencies

**File**: `backend/persistence/sqlite_adapter.py` — schema section only (lines 117–136 for stats; 106–115 for player_sessions; 128–136 for chat)

**File**: `requirements.txt` — add `aiosqlite>=0.19` if missing

**Changes**:

### player_stats_table — fix column names
```python
player_stats_table = sa.Table(
    "player_stats", metadata,
    sa.Column("club_id",      sa.String,  primary_key=True),
    sa.Column("user_id",      sa.String,  primary_key=True),
    sa.Column("display_name", sa.String,  nullable=False),
    sa.Column("hands_played", sa.Integer, nullable=False, default=0),
    sa.Column("wins",         sa.Integer, nullable=False, default=0),   # was hands_won
    sa.Column("total_won",    sa.Integer, nullable=False, default=0),   # was total_winnings
    sa.Column("total_lost",   sa.Integer, nullable=False, default=0),   # was biggest_pot
)
```

### chat_messages_table — add is_system
```python
chat_messages_table = sa.Table(
    "chat_messages", metadata,
    sa.Column("id",           sa.String,  primary_key=True),
    sa.Column("table_id",     sa.String,  nullable=False),
    sa.Column("user_id",      sa.String,  nullable=False),
    sa.Column("display_name", sa.String,  nullable=False),
    sa.Column("message",      sa.Text,    nullable=False),
    sa.Column("timestamp",    sa.Float,   nullable=False),
    sa.Column("is_system",    sa.Boolean, nullable=False, default=False),  # NEW
)
```

### player_sessions_table — add timeout_count and disconnect_at
```python
player_sessions_table = sa.Table(
    "player_sessions", metadata,
    sa.Column("table_id",      sa.String,  primary_key=True),
    sa.Column("user_id",       sa.String,  primary_key=True),
    sa.Column("display_name",  sa.String,  nullable=False),
    sa.Column("seat_index",    sa.Integer, nullable=False),
    sa.Column("stack",         sa.Integer, nullable=False),
    sa.Column("status",        sa.String,  nullable=False),
    sa.Column("timeout_count", sa.Integer, nullable=False, default=0),  # NEW
    sa.Column("is_connected",  sa.Boolean, nullable=False),
    sa.Column("disconnect_at", sa.Float,   nullable=True),              # NEW
)
```

---

## T2 — Implement `initialize()` and User Methods

**File**: `backend/persistence/sqlite_adapter.py`

```python
async def initialize(self) -> None:
    self._engine = create_async_engine(self._database_url, echo=False)
    async with self._engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

async def save_user(self, user: User) -> None:
    async with self._engine.begin() as conn:
        await conn.execute(
            users_table.insert().prefix_with("OR REPLACE").values(
                id=user.id, phone_number=user.phone_number,
                display_name=user.display_name, created_at=user.created_at,
            )
        )

async def get_user(self, user_id: str) -> Optional[User]:
    async with self._engine.connect() as conn:
        row = (await conn.execute(
            users_table.select().where(users_table.c.id == user_id)
        )).first()
    return User(**row._mapping) if row else None

async def get_user_by_phone(self, phone_number: str) -> Optional[User]:
    async with self._engine.connect() as conn:
        row = (await conn.execute(
            users_table.select().where(users_table.c.phone_number == phone_number)
        )).first()
    return User(**row._mapping) if row else None
```

---

## T3 — Implement Club Methods

**File**: `backend/persistence/sqlite_adapter.py`

```python
async def save_club(self, club: Club) -> None:
    async with self._engine.begin() as conn:
        await conn.execute(
            clubs_table.insert().prefix_with("OR REPLACE").values(
                id=club.id, name=club.name, owner_id=club.owner_id,
                invite_code=club.invite_code, created_at=club.created_at,
            )
        )
        for m in club.memberships:
            await conn.execute(
                club_memberships_table.insert().prefix_with("OR REPLACE").values(
                    club_id=m.club_id, user_id=m.user_id, role=m.role.value,
                    joined_at=m.joined_at, is_blocked=m.is_blocked,
                )
            )

async def get_club(self, club_id: str) -> Optional[Club]:
    async with self._engine.connect() as conn:
        row = (await conn.execute(
            clubs_table.select().where(clubs_table.c.id == club_id)
        )).first()
        if row is None:
            return None
        club = Club(
            id=row.id, name=row.name, owner_id=row.owner_id,
            invite_code=row.invite_code, created_at=row.created_at,
        )
        m_rows = (await conn.execute(
            club_memberships_table.select()
            .where(club_memberships_table.c.club_id == club_id)
        )).fetchall()
        club.memberships = [
            ClubMembership(
                club_id=r.club_id, user_id=r.user_id, role=ClubRole(r.role),
                joined_at=r.joined_at, is_blocked=r.is_blocked,
            )
            for r in m_rows
        ]
    return club

async def get_club_by_invite(self, invite_code: str) -> Optional[Club]:
    async with self._engine.connect() as conn:
        row = (await conn.execute(
            clubs_table.select().where(clubs_table.c.invite_code == invite_code)
        )).first()
    if row is None:
        return None
    return await self.get_club(row.id)

async def get_clubs_for_user(self, user_id: str) -> list[Club]:
    async with self._engine.connect() as conn:
        rows = (await conn.execute(
            club_memberships_table.select()
            .where(club_memberships_table.c.user_id == user_id)
            .where(club_memberships_table.c.is_blocked == False)
        )).fetchall()
    clubs = []
    for r in rows:
        club = await self.get_club(r.club_id)
        if club:
            clubs.append(club)
    return clubs

async def save_membership(self, membership: ClubMembership) -> None:
    async with self._engine.begin() as conn:
        await conn.execute(
            club_memberships_table.insert().prefix_with("OR REPLACE").values(
                club_id=membership.club_id, user_id=membership.user_id,
                role=membership.role.value, joined_at=membership.joined_at,
                is_blocked=membership.is_blocked,
            )
        )
```

---

## T4 — Implement Table and Hand Summary Methods

**File**: `backend/persistence/sqlite_adapter.py`

```python
async def save_table(self, table: TableRecord) -> None:
    config_json = json.dumps({
        "starting_stack": table.config.starting_stack,
        "small_blind": table.config.small_blind,
        "big_blind": table.config.big_blind,
        "turn_timer_seconds": table.config.turn_timer_seconds,
    })
    async with self._engine.begin() as conn:
        await conn.execute(
            tables_table.insert().prefix_with("OR REPLACE").values(
                id=table.id, club_id=table.club_id, config_json=config_json,
                created_by=table.created_by, created_at=table.created_at,
                is_active=table.is_active,
            )
        )

async def get_table(self, table_id: str) -> Optional[TableRecord]:
    async with self._engine.connect() as conn:
        row = (await conn.execute(
            tables_table.select().where(tables_table.c.id == table_id)
        )).first()
    if row is None:
        return None
    cfg = json.loads(row.config_json)
    return TableRecord(
        id=row.id, club_id=row.club_id,
        config=TableConfig(**cfg),
        created_by=row.created_by, created_at=row.created_at, is_active=row.is_active,
    )

async def get_club_table(self, club_id: str) -> Optional[TableRecord]:
    async with self._engine.connect() as conn:
        row = (await conn.execute(
            tables_table.select()
            .where(tables_table.c.club_id == club_id)
            .where(tables_table.c.is_active == True)
            .limit(1)
        )).first()
    if row is None:
        return None
    return await self.get_table(row.id)

async def save_hand_summary(self, summary: HandSummary) -> None:
    async with self._engine.begin() as conn:
        await conn.execute(
            hand_summaries_table.insert().values(
                hand_id=summary.hand_id, table_id=summary.table_id,
                club_id=summary.club_id, hand_number=summary.hand_number,
                phase_reached=summary.phase_reached,
                winner_ids_json=json.dumps(summary.winner_ids),
                pot_total=summary.pot_total,
                player_ids_json=json.dumps(summary.player_ids),
                stacks_before_json=json.dumps(summary.stacks_before),
                stacks_after_json=json.dumps(summary.stacks_after),
                community_cards_json=json.dumps(summary.community_cards),
                timestamp=summary.timestamp,
            )
        )

async def get_hand_history(self, table_id: str, limit: int = 50) -> list[HandSummary]:
    async with self._engine.connect() as conn:
        rows = (await conn.execute(
            hand_summaries_table.select()
            .where(hand_summaries_table.c.table_id == table_id)
            .order_by(hand_summaries_table.c.timestamp.asc())
            .limit(limit)
        )).fetchall()
    return [
        HandSummary(
            hand_id=r.hand_id, table_id=r.table_id, club_id=r.club_id,
            hand_number=r.hand_number, phase_reached=r.phase_reached,
            winner_ids=json.loads(r.winner_ids_json),
            pot_total=r.pot_total,
            player_ids=json.loads(r.player_ids_json),
            stacks_before=json.loads(r.stacks_before_json),
            stacks_after=json.loads(r.stacks_after_json),
            community_cards=json.loads(r.community_cards_json),
            timestamp=r.timestamp,
        )
        for r in rows
    ]
```

---

## T5 — Implement Snapshot and Player Session Methods

**File**: `backend/persistence/sqlite_adapter.py`

```python
import time as _time  # already available at module level

async def save_game_state_snapshot(self, table_id: str, snapshot: dict) -> None:
    if "hand" in snapshot and snapshot["hand"] is not None:
        import copy
        snapshot = copy.deepcopy(snapshot)
        snapshot["hand"].pop("deck", None)
    assert "deck" not in snapshot, "deck must never be persisted"
    async with self._engine.begin() as conn:
        await conn.execute(
            game_snapshots_table.insert().prefix_with("OR REPLACE").values(
                table_id=table_id,
                snapshot_json=json.dumps(snapshot),
                updated_at=_time.time(),
            )
        )

async def load_game_state_snapshot(self, table_id: str) -> Optional[dict]:
    async with self._engine.connect() as conn:
        row = (await conn.execute(
            game_snapshots_table.select()
            .where(game_snapshots_table.c.table_id == table_id)
        )).first()
    return json.loads(row.snapshot_json) if row else None

async def save_player_session(self, table_id: str, session: PlayerSession) -> None:
    async with self._engine.begin() as conn:
        await conn.execute(
            player_sessions_table.insert().prefix_with("OR REPLACE").values(
                table_id=table_id, user_id=session.user_id,
                display_name=session.display_name, seat_index=session.seat_index,
                stack=session.stack, status=session.status.value,
                timeout_count=session.timeout_count,
                is_connected=session.is_connected,
                disconnect_at=session.disconnect_at,
            )
        )

async def load_player_sessions(self, table_id: str) -> list[PlayerSession]:
    async with self._engine.connect() as conn:
        rows = (await conn.execute(
            player_sessions_table.select()
            .where(player_sessions_table.c.table_id == table_id)
        )).fetchall()
    return [
        PlayerSession(
            user_id=r.user_id, display_name=r.display_name,
            seat_index=r.seat_index, stack=r.stack,
            status=PlayerStatus(r.status),
            timeout_count=r.timeout_count,
            is_connected=r.is_connected,
            disconnect_at=r.disconnect_at,
        )
        for r in rows
    ]

async def delete_player_session(self, table_id: str, user_id: str) -> None:
    async with self._engine.begin() as conn:
        await conn.execute(
            player_sessions_table.delete().where(
                (player_sessions_table.c.table_id == table_id) &
                (player_sessions_table.c.user_id == user_id)
            )
        )
```

---

## T6 — Implement Stats and Chat Methods

**File**: `backend/persistence/sqlite_adapter.py`

```python
async def upsert_player_stats(
    self, club_id: str, user_id: str, display_name: str, delta: StatsDelta
) -> None:
    async with self._engine.begin() as conn:
        await conn.execute(
            player_stats_table.insert().prefix_with("OR IGNORE").values(
                club_id=club_id, user_id=user_id, display_name=display_name,
                hands_played=0, wins=0, total_won=0, total_lost=0,
            )
        )
        await conn.execute(
            player_stats_table.update()
            .where(
                (player_stats_table.c.club_id == club_id) &
                (player_stats_table.c.user_id == user_id)
            )
            .values(
                display_name=display_name,
                hands_played=player_stats_table.c.hands_played + delta.hands_played_delta,
                wins=player_stats_table.c.wins + delta.wins_delta,
                total_won=player_stats_table.c.total_won + delta.chips_won,
                total_lost=player_stats_table.c.total_lost + delta.chips_lost,
            )
        )

async def get_player_stats(self, club_id: str, user_id: str) -> Optional[PlayerStats]:
    async with self._engine.connect() as conn:
        row = (await conn.execute(
            player_stats_table.select().where(
                (player_stats_table.c.club_id == club_id) &
                (player_stats_table.c.user_id == user_id)
            )
        )).first()
    if row is None:
        return None
    return PlayerStats(
        user_id=row.user_id, club_id=row.club_id, display_name=row.display_name,
        hands_played=row.hands_played, wins=row.wins,
        total_won=row.total_won, total_lost=row.total_lost,
    )

async def get_leaderboard(self, club_id: str, limit: int = 20) -> list[PlayerStats]:
    async with self._engine.connect() as conn:
        rows = (await conn.execute(
            player_stats_table.select()
            .where(player_stats_table.c.club_id == club_id)
            .order_by(player_stats_table.c.wins.desc())
            .limit(limit)
        )).fetchall()
    return [
        PlayerStats(
            user_id=r.user_id, club_id=r.club_id, display_name=r.display_name,
            hands_played=r.hands_played, wins=r.wins,
            total_won=r.total_won, total_lost=r.total_lost,
        )
        for r in rows
    ]

async def save_chat_message(self, message: ChatMessage) -> None:
    async with self._engine.begin() as conn:
        await conn.execute(
            chat_messages_table.insert().values(
                id=message.id, table_id=message.table_id,
                user_id=message.user_id, display_name=message.display_name,
                message=message.message, timestamp=message.timestamp,
                is_system=message.is_system,
            )
        )

async def get_chat_history(self, table_id: str, limit: int = 50) -> list[ChatMessage]:
    async with self._engine.connect() as conn:
        rows = (await conn.execute(
            chat_messages_table.select()
            .where(chat_messages_table.c.table_id == table_id)
            .order_by(chat_messages_table.c.timestamp.asc())
            .limit(limit)
        )).fetchall()
    return [
        ChatMessage(
            id=r.id, table_id=r.table_id, user_id=r.user_id,
            display_name=r.display_name, message=r.message,
            timestamp=r.timestamp, is_system=r.is_system,
        )
        for r in rows
    ]
```

---

## T7 — Wire Adapter into App

**File**: `backend/config.py`
Add field after `use_redis`:
```python
use_sqlite: bool = Field(False, alias="USE_SQLITE")
```

**File**: `backend/main.py`
- Add import: `from .persistence.sqlite_adapter import SqlitePersistenceAdapter`
- Replace in lifespan:
```python
if settings.use_sqlite:
    persistence = SqlitePersistenceAdapter(settings.database_url)
    await persistence.initialize()
else:
    persistence = InMemoryPersistenceAdapter()
```
- Update shutdown comment: `# Future: close DB connections, flush Redis, etc.` → add `if settings.use_sqlite: await persistence._engine.dispose()`

---

## T8 — Write `tests/test_sqlite_persistence.py`

Create new file implementing all test cases from `qa-test-plan.md` (TC-01 through TC-33) plus TR-04 count check.

**Restart test helper** (use `tmp_path` — more portable than shared-cache `:memory:`):
```python
@pytest.fixture
def db_url(tmp_path):
    return f"sqlite+aiosqlite:///{tmp_path}/test.db"

@pytest.fixture
async def db(db_url) -> SqlitePersistenceAdapter:
    adapter = SqlitePersistenceAdapter(db_url)
    await adapter.initialize()
    yield adapter
    await adapter._engine.dispose()
```

For restart tests:
```python
async def test_user_restart_safety(db_url):
    db1 = SqlitePersistenceAdapter(db_url)
    await db1.initialize()
    await db1.save_user(User(id="u1", phone_number="+1234", display_name="Alice", created_at=0.0))
    await db1._engine.dispose()

    db2 = SqlitePersistenceAdapter(db_url)
    await db2.initialize()
    user = await db2.get_user("u1")
    await db2._engine.dispose()

    assert user is not None
    assert user.display_name == "Alice"
```

---

## T9 — Verify Requirements and Run Tests

1. Confirm `aiosqlite` is in `requirements.txt`; if not, add it
2. Run: `py -m pytest tests/test_sqlite_persistence.py -v`
3. Run: `py -m pytest --tb=short -q` (full regression — must be 235 + N all passing)
4. Import boundary check: confirm no `poker_engine` imports added to `backend/persistence/`
   (only the existing `from poker_engine.engine.models import PlayerSession` is allowed)

---

## Implementation Order

T0 → T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9

T1–T6 are all changes to one file (`sqlite_adapter.py`). T7 changes two small files. T8 is a new test file. T9 is verification only.
