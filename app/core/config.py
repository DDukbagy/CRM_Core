from __future__ import annotations

import json
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    DATABASE_URL: str
    DB_ECHO: bool = False

    SUPABASE_URL: str
    SUPABASE_JWT_AUDIENCE: str = "authenticated"

    CORS_ALLOW_ORIGINS: str = '["*"]'

    class Config:
        env_file = BASE_DIR / ".env"
        extra = "ignore"

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """
        SQLAlchemy async driver URL
        postgresql+asyncpg:// -> 그대로 사용
        postgresql:// -> postgresql+asyncpg:// 로 변환
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
        try:
            return json.loads(self.CORS_ALLOW_ORIGINS)
        except Exception:
            return ["*"]


settings = Settings()
