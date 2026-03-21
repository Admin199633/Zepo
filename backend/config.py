"""
Application configuration.
All values are read from environment variables with sane defaults.
Import the singleton `settings` object throughout the backend.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- App ---
    app_env: str = Field("development", alias="APP_ENV")
    debug: bool = Field(False, alias="DEBUG")

    # --- Database ---
    database_url: str = Field("sqlite+aiosqlite:///./poker.db", alias="DATABASE_URL")

    # --- Cache / Redis ---
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")
    use_redis: bool = Field(False, alias="USE_REDIS")   # False = in-memory cache for dev
    use_sqlite: bool = Field(False, alias="USE_SQLITE") # True = SqlitePersistenceAdapter

    # --- Auth ---
    jwt_secret: str = Field("CHANGE_ME_IN_PRODUCTION", alias="JWT_SECRET")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    jwt_expire_hours: int = Field(24, alias="JWT_EXPIRE_HOURS")

    # --- SMS ---
    sms_provider: str = Field("console", alias="SMS_PROVIDER")   # "console" | "twilio"
    sms_from_number: str = Field("", alias="SMS_FROM_NUMBER")
    twilio_account_sid: str = Field("", alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field("", alias="TWILIO_AUTH_TOKEN")

    # --- Game ---
    disconnect_timeout_seconds: int = Field(60, alias="DISCONNECT_TIMEOUT_SECONDS")
    between_hands_delay_seconds: float = Field(3.0, alias="BETWEEN_HANDS_DELAY_SECONDS")
    request_id_ttl_seconds: int = Field(60, alias="REQUEST_ID_TTL_SECONDS")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "populate_by_name": True,
    }


settings = Settings()
