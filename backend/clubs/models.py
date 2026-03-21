"""
Club domain models.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..auth.models import ClubRole


@dataclass
class ClubMembership:
    club_id: str
    user_id: str
    role: ClubRole
    joined_at: float = 0.0
    is_blocked: bool = False


@dataclass
class Club:
    id: str
    name: str
    owner_id: str
    invite_code: str
    created_at: float = 0.0
    memberships: list[ClubMembership] = field(default_factory=list)

    def is_member(self, user_id: str) -> bool:
        return any(m.user_id == user_id and not m.is_blocked for m in self.memberships)

    def is_admin(self, user_id: str) -> bool:
        return any(
            m.user_id == user_id and m.role in (ClubRole.OWNER, ClubRole.ADMIN)
            for m in self.memberships
        )

    def get_membership(self, user_id: str) -> ClubMembership | None:
        return next((m for m in self.memberships if m.user_id == user_id), None)
