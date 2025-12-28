from __future__ import annotations

import time
from typing import Any, Dict, Optional
from uuid import UUID

import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session

security = HTTPBearer(auto_error=False)

_JWKS_CACHE: Optional[Dict[str, Any]] = None
_JWKS_CACHE_EXPIRES_AT: float = 0.0
_JWKS_TTL_SECONDS: int = 60 * 60  # 1시간


def _issuer() -> str:
    # SUPABASE_URL 끝의 / 유무에 안전하게
    base = settings.SUPABASE_URL.rstrip("/")
    return f"{base}/auth/v1"


def _jwks_url() -> str:
    """Supabase 표준 JWKS 엔드포인트 URL (RS256용)"""
    return f"{_issuer()}/.well-known/jwks.json"


def get_supabase_jwks() -> Dict[str, Any]:
    """
    Supabase의 JWKS(JSON Web Key Set)를 가져온다.
    - RS256 서명 검증에 필요한 공개키들이 들어있다.
    - TTL 캐싱을 적용해서 외부 호출을 최소화한다.
    """
    global _JWKS_CACHE, _JWKS_CACHE_EXPIRES_AT

    now = time.time()
    if _JWKS_CACHE is not None and now < _JWKS_CACHE_EXPIRES_AT:
        return _JWKS_CACHE

    try:
        resp = requests.get(_jwks_url(), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if "keys" not in data or not isinstance(data["keys"], list):
            raise ValueError("JWKS 형식이 올바르지 않습니다.")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase JWKS를 가져오지 못했습니다.",
        ) from e

    _JWKS_CACHE = data
    _JWKS_CACHE_EXPIRES_AT = now + _JWKS_TTL_SECONDS
    return data


def _get_public_key_pem_from_token(token: str) -> bytes:
    """
    JWT 헤더의 kid(key id)를 이용해 JWKS에서 해당 공개키를 찾아 PEM(bytes)로 변환한다. (RS256용)
    """
    try:
        header = jwt.get_unverified_header(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰 헤더가 올바르지 않습니다.",
        ) from e

    kid = header.get("kid")
    if not kid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰에 kid가 없습니다.",
        )

    jwks = get_supabase_jwks()
    key_dict = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if not key_dict:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰 kid에 해당하는 공개키를 찾지 못했습니다.",
        )

    try:
        key = jwk.construct(key_dict)
        return key.to_pem()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="공개키 변환에 실패했습니다.",
        ) from e


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Dict[str, Any]:
    """
    Supabase JWT를 검증하고 현재 유저 정보를 반환한다.

    반환 형태(프로젝트 표준):
    {
      "id": "<uuid-string>",   # sub
      "email": "<str|None>",
      "role": "<str|None>"
    }
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization 헤더가 없습니다.",
        )

    # scheme(Bearer) 엄격 체크 (혼란 방지)
    if (credentials.scheme or "").lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰 헤더가 올바르지 않습니다.",
        )

    token = credentials.credentials

    # alg에 따라 HS256/RS256 분기
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰 헤더가 올바르지 않습니다.",
        )

    issuer = _issuer()

    try:
        if alg == "HS256":
            # Supabase 기본(대칭키): JWT Secret으로 검증 (JWKS 필요 없음)
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience=settings.SUPABASE_JWT_AUDIENCE,
                issuer=issuer,
            )

        elif alg == "RS256":
            # 공개키(JWKS) 방식
            public_pem = _get_public_key_pem_from_token(token)
            payload = jwt.decode(
                token,
                public_pem,
                algorithms=["RS256"],
                audience=settings.SUPABASE_JWT_AUDIENCE,
                issuer=issuer,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"지원하지 않는 JWT 알고리즘: {alg}",
            )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않거나 만료된 토큰입니다.",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰에 sub(user id)가 없습니다.",
        )

    # UUID 형식 검증만 수행(반환은 string 유지)
    try:
        UUID(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰의 user id 형식이 올바르지 않습니다.",
        )

    return {
        "id": user_id,
        "email": payload.get("email"),
        "role": payload.get("role"),
    }


async def get_current_host(
    current_user: Dict[str, Any] = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    호스트(강사) 전용 API에서 사용한다.
    - Supabase 토큰 검증(get_current_user)
    - 우리 서비스 DB(users.is_host)로 권한 확인
    """
    result = await session.execute(
        text("SELECT is_host FROM users WHERE id = :id"),
        {"id": current_user["id"]},
    )
    row = result.mappings().first()

    if not row or not row.get("is_host"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="호스트 권한이 필요합니다.",
        )

    return current_user
