from __future__ import annotations

import time
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError
from jose.utils import base64url_decode


class SupabaseJWTError(Exception):
    pass


class SupabaseJWTExpired(SupabaseJWTError):
    pass


@dataclass
class JWKSCache:
    jwks: Optional[dict] = None
    fetched_at: float = 0.0
    ttl_seconds: int = 600  # 10분 캐시


_jwks_cache = JWKSCache()


def _rstrip(url: str) -> str:
    return url.rstrip("/")


def issuer_from_supabase_url(supabase_url: str, override: Optional[str] = None) -> str:
    return _rstrip(override) if override else f"{_rstrip(supabase_url)}/auth/v1"


def jwks_url_from_issuer(issuer: str) -> str:
    # Supabase JWT docs: iss + "/.well-known/jwks.json"
    return f"{_rstrip(issuer)}/.well-known/jwks.json"  # :contentReference[oaicite:5]{index=5}


def _peek_header(token: str) -> dict:
    header_b64 = token.split(".")[0].encode("utf-8")
    header_json = base64url_decode(header_b64)
    return json.loads(header_json)


async def _fetch_jwks(jwks_url: str) -> dict:
    now = time.time()
    if _jwks_cache.jwks and (now - _jwks_cache.fetched_at) < _jwks_cache.ttl_seconds:
        return _jwks_cache.jwks

    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(jwks_url)
        r.raise_for_status()
        jwks = r.json()

    _jwks_cache.jwks = jwks
    _jwks_cache.fetched_at = now
    return jwks


def _select_jwk(jwks: dict, kid: str) -> dict:
    for k in jwks.get("keys", []):
        if k.get("kid") == kid:
            return k
    raise SupabaseJWTError(f"JWKS key not found for kid={kid}")


async def verify_supabase_access_token(
    *,
    token: str,
    supabase_url: str,
    jwt_secret: Optional[str],
    issuer_override: Optional[str] = None,
    audience: str = "authenticated",
) -> Dict[str, Any]:
    """
    운영형 검증:
    - 토큰 헤더 alg가 HS256이 아니면 JWKS로 검증
    - HS256이면 jwt_secret로 검증(전환/레거시 대응)
    """
    issuer = issuer_from_supabase_url(supabase_url, issuer_override)
    header = _peek_header(token)
    alg = header.get("alg")
    kid = header.get("kid")

    try:
        # 1) 비대칭(권장) : RS256/ES256 등 -> JWKS
        if alg and alg != "HS256":
            jwks = await _fetch_jwks(jwks_url_from_issuer(issuer))
            if not kid:
                raise SupabaseJWTError("Missing kid in JWT header")
            jwk = _select_jwk(jwks, kid)

            return jwt.decode(
                token,
                key=jwk,
                algorithms=[alg],
                issuer=issuer,
                audience=audience,
                options={"verify_exp": True, "verify_iss": True, "verify_aud": True},
            )

        # 2) HS256(legacy/shared secret)
        if not jwt_secret:
            raise SupabaseJWTError("JWT secret is required for HS256 verification")

        return jwt.decode(
            token,
            key=jwt_secret,
            algorithms=["HS256"],
            issuer=issuer,
            audience=audience,
            options={"verify_exp": True, "verify_iss": True, "verify_aud": True},
        )

    except ExpiredSignatureError as e:
        raise SupabaseJWTExpired("Token expired") from e
    except JWTError as e:
        raise SupabaseJWTError("Invalid token") from e
