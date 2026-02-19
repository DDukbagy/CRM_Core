from __future__ import annotations

import json
from pathlib import Path
from typing import List, Union, Any

from pydantic import field_validator, Field, AliasChoices
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

    # ✅ 소문자/기존 키까지 모두 허용
    CORS_ORIGIN_REGEX: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "CORS_ORIGIN_REGEX",
            "CORS_ALLOW_ORIGIN_REGEX",
            "cors_origin_regex",
        ),
    )

    # ✅ 소문자/기존 키까지 모두 허용
    CORS_ALLOW_ORIGINS: Union[str, List[str]] = Field(
        default='["http://localhost:3000"]',
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
        return [o.strip() for o in s.split(",") if o.strip()]

    @property
    def SUPABASE_ISSUER(self) -> str:
        return self.SUPABASE_URL.rstrip("/") + "/auth/v1"

    @property
    def DB_IS_POOLER(self) -> bool:
        return ".pooler.supabase.com" in self.DATABASE_URL


settings = Settings()
