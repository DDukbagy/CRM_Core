from __future__ import annotations

import json
from pathlib import Path
from typing import List, Union

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

    CORS_ALLOW_ORIGINS: Union[str, List[str]] = '["*"]'

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
        try:
            return json.loads(v)
        except Exception:
            return ["*"]

    @property
    def SUPABASE_ISSUER(self) -> str:
        return self.SUPABASE_URL.rstrip("/") + "/auth/v1"

    @property
    def DB_IS_POOLER(self) -> bool:
        return ".pooler.supabase.com" in self.DATABASE_URL


settings = Settings()
