import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

# ---- exported settings (deps.py 등에서 import하는 심볼들) ----
# 운영 기준: 환경변수로만 주입(코드/레포에 하드코딩 금지)
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM

# 기본 24시간(분 단위). 환경변수로 조절 가능.
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _require_secret_key() -> str:
    """
    SECRET_KEY가 비어있으면 jose가 'Expecting a string- or bytes-formatted key' 같은
    애매한 에러를 내므로, 여기서 명확한 메시지로 실패시킨다.
    """
    key = SECRET_KEY.get_secret_value() if hasattr(SECRET_KEY, "get_secret_value") else str(SECRET_KEY)
    key = key.strip()
    if not key:
        raise RuntimeError("SECRET_KEY is missing. Set SECRET_KEY in backend/.env or deployment secrets.")
    return key


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, _require_secret_key(), algorithm=ALGORITHM)
    return encoded_jwt