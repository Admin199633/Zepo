"""
AuthService interface (Protocol) and a stub implementation.

Full implementation requires SMS provider and DB — wired up in main app.
"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from .models import AuthToken, User


@runtime_checkable
class AuthService(Protocol):
    """Interface for authentication operations."""

    async def register(self, username: str, password: str, display_name: str) -> AuthToken:
        """Create a new user. Raises ValueError if username taken or fields invalid."""
        ...

    async def login(self, username: str, password: str) -> AuthToken:
        """Authenticate by username+password. Raises ValueError on bad credentials."""
        ...

    async def request_otp(self, phone_number: str) -> None:
        """Send OTP to phone_number. Raises ValueError on invalid number."""
        ...

    async def verify_otp(
        self, phone_number: str, code: str, display_name: Optional[str] = None
    ) -> AuthToken:
        """
        Verify OTP and return a JWT token.
        Creates user if they don't exist (display_name required for new users).
        Raises ValueError on wrong/expired code.
        """
        ...

    async def verify_token(self, token: str) -> User:
        """
        Decode and validate a JWT token.
        Returns the authenticated User.
        Raises ValueError on invalid/expired token.
        """
        ...


# ---------------------------------------------------------------------------
# Console stub (for development — prints OTP to stdout)
# ---------------------------------------------------------------------------

class ConsoleAuthService:
    """
    Development-only auth service.
    Supports username/password register+login for playtesting.
    Legacy OTP methods retained for simulation test compatibility.
    """

    def __init__(self, persistence: "PersistenceAdapter") -> None:  # type: ignore[name-defined]
        self._persistence = persistence
        self._otps: dict[str, str] = {}  # phone → code (legacy OTP)

    # ------------------------------------------------------------------
    # Username / password (playtesting)
    # ------------------------------------------------------------------

    async def register(
        self, username: str, password: str, display_name: str
    ) -> AuthToken:
        import bcrypt, time, uuid
        username = username.strip()
        display_name = display_name.strip()
        if not username:
            raise ValueError("username required")
        if not display_name:
            raise ValueError("display_name required")
        if not password:
            raise ValueError("password required")

        existing = await self._persistence.get_user_by_username(username)
        if existing is not None:
            raise ValueError("Username already taken")

        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = User(
            id=str(uuid.uuid4()),
            phone_number="",
            display_name=display_name,
            created_at=time.time(),
            username=username,
            password_hash=pw_hash,
        )
        await self._persistence.save_user(user)
        return self._mint_token(user)

    async def login(self, username: str, password: str) -> AuthToken:
        import bcrypt
        username = username.strip()
        user = await self._persistence.get_user_by_username(username)
        if user is None:
            raise ValueError("Invalid username or password")

        if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            raise ValueError("Invalid username or password")

        return self._mint_token(user)

    # ------------------------------------------------------------------
    # Legacy OTP (kept for simulation tests)
    # ------------------------------------------------------------------

    async def request_otp(self, phone_number: str) -> None:
        import random
        code = f"{random.randint(100000, 999999)}"
        self._otps[phone_number] = code
        print(f"[DEV OTP] {phone_number} → {code}")

    async def verify_otp(
        self, phone_number: str, code: str, display_name: Optional[str] = None
    ) -> AuthToken:
        import time, uuid
        expected = self._otps.get(phone_number)
        if not expected or expected != code:
            raise ValueError("Invalid or expired OTP")
        del self._otps[phone_number]

        user = await self._persistence.get_user_by_phone(phone_number)
        if user is None:
            if not display_name:
                raise ValueError("display_name required for new users")
            user = User(
                id=str(uuid.uuid4()),
                phone_number=phone_number,
                display_name=display_name,
                created_at=time.time(),
            )
            await self._persistence.save_user(user)

        token = self._mint_token(user)
        return token

    async def verify_token(self, token: str) -> User:
        if not token.startswith("dev_"):
            raise ValueError("Invalid token")
        user_id = token[4:]
        user = await self._persistence.get_user(user_id)
        if user is None:
            raise ValueError("User not found")
        return user

    def _mint_token(self, user: User) -> AuthToken:
        import time
        return AuthToken(
            user_id=user.id,
            token=f"dev_{user.id}",
            expires_at=time.time() + 86400,
            display_name=user.display_name,
        )
