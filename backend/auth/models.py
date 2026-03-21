"""
Auth domain models.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass
class User:
    id: str
    phone_number: str          # E.164 for OTP users; "" for username-auth users
    display_name: str
    created_at: float = 0.0    # epoch seconds
    username: str = ""         # unique username for password-auth users
    password_hash: str = ""    # bcrypt hash; "" for OTP users

    def __post_init__(self) -> None:
        assert len(self.phone_number.strip()) >= 1 or len(self.username.strip()) >= 1, \
            "phone_number or username required"
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
