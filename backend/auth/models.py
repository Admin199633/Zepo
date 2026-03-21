"""
Auth domain models.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass
class User:
    id: str
    phone_number: str          # E.164 format: +972501234567
    display_name: str
    created_at: float = 0.0    # epoch seconds

    def __post_init__(self) -> None:
        assert self.phone_number.startswith("+"), "Phone must be E.164"
        assert len(self.display_name.strip()) >= 1, "display_name required"


@dataclass
class OTPRecord:
    """Short-lived OTP state (never persisted to DB — in-memory only)."""
    phone_number: str
    code: str
    expires_at: float          # epoch seconds
    attempts: int = 0
    max_attempts: int = 3


@dataclass
class AuthToken:
    user_id: str
    token: str
    expires_at: float


class ClubRole(str, Enum):
    OWNER  = "owner"
    ADMIN  = "admin"
    MEMBER = "member"
