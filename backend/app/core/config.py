from __future__ import annotations

import json
from pathlib import Path
from typing import List, Union, Any

from pydantic import field_validator, Field, AliasChoices, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        extra="ignore",
        env_file_encoding="utf-8",
    )

    DATABASE_URL: str
    DB_ECHO: bool = False

    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_JWT_SECRET: str
    SUPABASE_JWT_AUDIENCE: str = "authenticated"

    SECRET_KEY: SecretStr
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # Super Admin
    SUPER_ADMIN_USER_ID: str | None = None
    SUPER_ADMIN_EMAIL: str | None = None

    # Sentry
    SENTRY_DSN: str | None = None
    SENTRY_ENVIRONMENT: str = "development"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    CORS_ORIGIN_REGEX: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "CORS_ORIGIN_REGEX",
            "CORS_ALLOW_ORIGIN_REGEX",
            "CORS_REGEX",
            "cors_origin_regex",
        ),
    )

    CORS_ALLOW_ORIGINS: Union[str, List[str]] = Field(
        default='["http://localhost:3000","http://localhost:8081","http://localhost:19006"]',
        validation_alias=AliasChoices(
            "CORS_ALLOW_ORIGINS",
            "CORS_ORIGINS",
            "CORS_ORIGIN",
            "cors_origins",
            "cors_origin",
        ),
    )

    @field_validator("CORS_ALLOW_ORIGINS", mode="before")
    def _parse_cors_allow_origins(cls, v: Any) -> List[str]:
        if isinstance(v, list):
            return v
        if v is None:
            return []
        s = str(v).strip()
        if not s:
            return []
        if s.startswith("["):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                return []
        return [o.strip() for o in s.split(",") if o.strip()]

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """
        SQLAlchemy async driver URL
        postgresql+asyncpg:// -> 그대로 사용
        postgresql:// -> postgresql+asyncpg:// 로 변환
        postgres:// -> postgresql:// 로 변환 후 처리
        """
        url = self.DATABASE_URL
        if url.startswith("postgresql+asyncpg://"):
            return url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def cors_origins(self) -> List[str]:
        v = self.CORS_ALLOW_ORIGINS

        if isinstance(v, list):
            return v

        s = str(v).strip()
        if not s:
            return []

        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass

        parts = [o.strip() for o in s.split(",") if o.strip()]
        return parts

    @property
    def SUPABASE_ISSUER(self) -> str:
        return self.SUPABASE_URL.rstrip("/") + "/auth/v1"

    @property
    def DB_IS_POOLER(self) -> bool:
        return ".pooler.supabase.com" in self.DATABASE_URL


settings = Settings()