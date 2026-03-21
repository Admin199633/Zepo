"""
POST   /clubs
GET    /clubs/{club_id}
POST   /clubs/{club_id}/join
"""
from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator

from ..auth.models import ClubRole, User
from ..clubs.models import Club, ClubMembership
from ..dependencies import get_current_user, get_persistence, http_error
from ..persistence.adapter import PersistenceAdapter
from ..tables.models import TableRecord
from poker_engine.engine.models import TableConfig

router = APIRouter(prefix="/clubs", tags=["clubs"])

_DEFAULT_CONFIG = TableConfig(
    max_players=9,
    starting_stack=1000,
    small_blind=5,
    big_blind=10,
    turn_timer_seconds=30,
    house_rules=[],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CreateClubBody(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 64:
            raise ValueError("Club name must be 1–64 characters")
        return v


class JoinClubBody(BaseModel):
    invite_code: str


class ClubResponse(BaseModel):
    club_id: str
    name: str
    owner_id: str
    invite_code: str
    member_count: int


class CreateClubResponse(BaseModel):
    club_id: str
    table_id: str
    invite_code: str


class JoinClubResponse(BaseModel):
    club_id: str
    table_id: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("", status_code=201, response_model=CreateClubResponse)
async def create_club(
    body: CreateClubBody,
    current_user: User = Depends(get_current_user),
    persistence: PersistenceAdapter = Depends(get_persistence),
) -> CreateClubResponse:
    club_id = str(uuid.uuid4())
    table_id = str(uuid.uuid4())
    invite_code = uuid.uuid4().hex[:8].upper()
    now = time.time()

    club = Club(
        id=club_id,
        name=body.name,
        owner_id=current_user.id,
        invite_code=invite_code,
        created_at=now,
        memberships=[
            ClubMembership(
                club_id=club_id,
                user_id=current_user.id,
                role=ClubRole.OWNER,
                joined_at=now,
            )
        ],
    )
    table = TableRecord(
        id=table_id,
        club_id=club_id,
        config=_DEFAULT_CONFIG,
        created_by=current_user.id,
        created_at=now,
        is_active=True,
    )

    await persistence.save_club(club)
    await persistence.save_table(table)

    return CreateClubResponse(
        club_id=club_id,
        table_id=table_id,
        invite_code=invite_code,
    )


@router.get("/mine", response_model=list[ClubResponse])
async def get_my_clubs(
    current_user: User = Depends(get_current_user),
    persistence: PersistenceAdapter = Depends(get_persistence),
) -> list[ClubResponse]:
    clubs = await persistence.get_clubs_for_user(current_user.id)
    return [
        ClubResponse(
            club_id=club.id,
            name=club.name,
            owner_id=club.owner_id,
            invite_code=club.invite_code,
            member_count=len(club.memberships),
        )
        for club in clubs
    ]


@router.get("/{club_id}", response_model=ClubResponse)
async def get_club(
    club_id: str,
    current_user: User = Depends(get_current_user),
    persistence: PersistenceAdapter = Depends(get_persistence),
) -> ClubResponse:
    club = await persistence.get_club(club_id)
    if club is None:
        raise http_error("NOT_FOUND", "Club not found.", status=404)
    if not club.is_member(current_user.id):
        raise http_error("NOT_MEMBER", "You are not a member of this club.", status=403)
    return ClubResponse(
        club_id=club.id,
        name=club.name,
        owner_id=club.owner_id,
        invite_code=club.invite_code,
        member_count=len(club.memberships),
    )


@router.post("/{club_id}/join", response_model=JoinClubResponse)
async def join_club(
    club_id: str,
    body: JoinClubBody,
    current_user: User = Depends(get_current_user),
    persistence: PersistenceAdapter = Depends(get_persistence),
) -> JoinClubResponse:
    club = await persistence.get_club_by_invite(body.invite_code)
    if club is None or club.id != club_id:
        raise http_error("INVALID_INVITE_CODE", "Invite code is invalid.")

    if club.is_member(current_user.id):
        raise http_error("ALREADY_MEMBER", "You are already a member of this club.", status=409)

    membership = ClubMembership(
        club_id=club.id,
        user_id=current_user.id,
        role=ClubRole.MEMBER,
        joined_at=time.time(),
    )
    club.memberships.append(membership)
    await persistence.save_club(club)
    await persistence.save_membership(membership)

    table = await persistence.get_club_table(club.id)
    table_id = table.id if table else ""

    return JoinClubResponse(club_id=club.id, table_id=table_id)
