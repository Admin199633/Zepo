"""
POST /auth/register
POST /auth/login
POST /auth/request-otp   (legacy — used by simulation tests)
POST /auth/verify-otp    (legacy — used by simulation tests)
"""
from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator

from ..auth.service import AuthService
from ..dependencies import get_auth_service, http_error

router = APIRouter(prefix="/auth", tags=["auth"])

_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class RegisterBody(BaseModel):
    username: str
    password: str
    display_name: str


class LoginBody(BaseModel):
    username: str
    password: str


class OtpRequestBody(BaseModel):
    phone_number: str

    @field_validator("phone_number")
    @classmethod
    def validate_e164(cls, v: str) -> str:
        if not _E164_RE.match(v):
            raise ValueError("Phone number must be in E.164 format (e.g. +972501234567)")
        return v


class OtpVerifyBody(BaseModel):
    phone_number: str
    code: str
    display_name: Optional[str] = None

    @field_validator("phone_number")
    @classmethod
    def validate_e164(cls, v: str) -> str:
        if not _E164_RE.match(v):
            raise ValueError("Phone number must be in E.164 format")
        return v


class TokenResponse(BaseModel):
    token: str
    user_id: str
    expires_at: float
    display_name: str = ""


# ---------------------------------------------------------------------------
# Routes — username/password
# ---------------------------------------------------------------------------

@router.post("/register", response_model=TokenResponse)
async def register(
    body: RegisterBody,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    try:
        auth_token = await auth_service.register(
            body.username, body.password, body.display_name
        )
    except ValueError as exc:
        raise http_error("REGISTER_ERROR", str(exc))
    return TokenResponse(
        token=auth_token.token,
        user_id=auth_token.user_id,
        expires_at=auth_token.expires_at,
        display_name=auth_token.display_name,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginBody,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    try:
        auth_token = await auth_service.login(body.username, body.password)
    except ValueError as exc:
        raise http_error("LOGIN_ERROR", str(exc))
    return TokenResponse(
        token=auth_token.token,
        user_id=auth_token.user_id,
        expires_at=auth_token.expires_at,
        display_name=auth_token.display_name,
    )


# ---------------------------------------------------------------------------
# Routes — legacy OTP (simulation tests)
# ---------------------------------------------------------------------------

@router.post("/request-otp", status_code=200)
async def request_otp(
    body: OtpRequestBody,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    try:
        await auth_service.request_otp(body.phone_number)
    except ValueError as exc:
        raise http_error("INVALID_PHONE", str(exc))
    return {}


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(
    body: OtpVerifyBody,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    try:
        auth_token = await auth_service.verify_otp(
            body.phone_number, body.code, body.display_name
        )
    except ValueError as exc:
        raise http_error("INVALID_OTP", str(exc))
    return TokenResponse(
        token=auth_token.token,
        user_id=auth_token.user_id,
        expires_at=auth_token.expires_at,
        display_name=auth_token.display_name,
    )
