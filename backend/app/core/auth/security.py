from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import jwt

from app.core.config import settings

# ---- exported settings (deps.py 등에서 import하는 심볼들) ----
# 운영 기준: 환경변수로만 주입(코드/레포에 하드코딩 금지)
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM

# 기본 24시간(분 단위). 환경변수로 조절 가능.
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

# bcrypt는 비밀번호 앞 72바이트만 사용한다. 넘는 값은 자르지 않고 입력 단계(UserCreate)에서 거부한다.
MAX_PASSWORD_BYTES = 72


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


def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    # 비밀번호 없이 만들어진 계정(Supabase 로그인으로 자동 생성)은 항상 불일치
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        # 72바이트 초과 입력 또는 저장된 해시 형식 오류
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, _require_secret_key(), algorithm=ALGORITHM)
    return encoded_jwt