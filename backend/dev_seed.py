"""
Dev-only demo data seeded at startup when app_env != "production".

Fixed deterministic IDs — restart wipes all data (InMemoryPersistenceAdapter)
and re-seeds fresh. Tokens follow the dev format: dev_{user_id}.

Demo club invite code: ZEPODEV1
Alice token:  dev_00000000-0000-0000-0000-000000000001
Bob token:    dev_00000000-0000-0000-0000-000000000002
Table ID:     00000000-0000-0000-0000-000000000020
"""
from __future__ import annotations

import time

from .auth.models import User
from .clubs.models import Club, ClubMembership
from .auth.models import ClubRole
from .persistence.adapter import PersistenceAdapter
from .tables.models import TableRecord
from poker_engine.engine.models import TableConfig

DEMO_ALICE_ID  = "00000000-0000-0000-0000-000000000001"
DEMO_BOB_ID    = "00000000-0000-0000-0000-000000000002"
DEMO_CLUB_ID   = "00000000-0000-0000-0000-000000000010"
DEMO_TABLE_ID  = "00000000-0000-0000-0000-000000000020"
DEMO_INVITE    = "ZEPODEV1"

_DEMO_CONFIG = TableConfig(
    max_players=9,
    starting_stack=1000,
    small_blind=5,
    big_blind=10,
    turn_timer_seconds=15,
    house_rules=[],
)


async def seed_demo_data(persistence: PersistenceAdapter) -> None:
    now = time.time()

    alice = User(
        id=DEMO_ALICE_ID,
        phone_number="+972500000001",
        display_name="Alice",
        created_at=now,
    )
    bob = User(
        id=DEMO_BOB_ID,
        phone_number="+972500000002",
        display_name="Bob",
        created_at=now,
    )
    await persistence.save_user(alice)
    await persistence.save_user(bob)

    club = Club(
        id=DEMO_CLUB_ID,
        name="Demo Club",
        owner_id=DEMO_ALICE_ID,
        invite_code=DEMO_INVITE,
        created_at=now,
        memberships=[
            ClubMembership(
                club_id=DEMO_CLUB_ID,
                user_id=DEMO_ALICE_ID,
                role=ClubRole.OWNER,
                joined_at=now,
            ),
            ClubMembership(
                club_id=DEMO_CLUB_ID,
                user_id=DEMO_BOB_ID,
                role=ClubRole.MEMBER,
                joined_at=now,
            ),
        ],
    )
    await persistence.save_club(club)

    table = TableRecord(
        id=DEMO_TABLE_ID,
        club_id=DEMO_CLUB_ID,
        config=_DEMO_CONFIG,
        created_by=DEMO_ALICE_ID,
        created_at=now,
        is_active=True,
    )
    await persistence.save_table(table)

    print(
        f"\n[Zepo:DevSeed] Demo data seeded.\n"
        f"  Club:  {DEMO_CLUB_ID}  (invite: {DEMO_INVITE})\n"
        f"  Table: {DEMO_TABLE_ID}\n"
        f"  Alice token: dev_{DEMO_ALICE_ID}\n"
        f"  Bob   token: dev_{DEMO_BOB_ID}\n"
    )
