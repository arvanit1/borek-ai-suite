"""Supabase JWT authentication (AT-39)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError

from app.config import settings

_bearer = HTTPBearer(auto_error=False)
_JWT_SECRET_PLACEHOLDER = "your-jwt-secret-from-supabase-dashboard"
_JWT_DECODE_OPTIONS = {"require": ["sub", "exp"]}
_ASYMMETRIC_ALGORITHMS = ["ES256", "RS256"]


@dataclass(frozen=True)
class AuthUser:
    id: UUID
    email: str


def _unauthorized(message: str = "Authentication required") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "UNAUTHORIZED",
            "message": message,
        },
    )


def _legacy_jwt_secret() -> str | None:
    secret = settings.SUPABASE_JWT_SECRET.strip()
    if not secret or secret == _JWT_SECRET_PLACEHOLDER:
        return None
    return secret


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    jwks_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
    return PyJWKClient(jwks_url, cache_keys=True)


def _token_algorithm(token: str) -> str | None:
    try:
        return jwt.get_unverified_header(token).get("alg")
    except InvalidTokenError:
        return None


def _payload_from_token(token: str) -> dict:
    """Verify Supabase JWT via legacy HS256 secret or project JWKS."""
    algorithm = _token_algorithm(token)

    if algorithm == "HS256":
        legacy_secret = _legacy_jwt_secret()
        if legacy_secret is None:
            raise _unauthorized("Invalid or expired access token")
        try:
            return jwt.decode(
                token,
                legacy_secret,
                algorithms=["HS256"],
                audience="authenticated",
                options=_JWT_DECODE_OPTIONS,
            )
        except InvalidTokenError as exc:
            raise _unauthorized("Invalid or expired access token") from exc

    if algorithm in _ASYMMETRIC_ALGORITHMS:
        try:
            signing_key = _jwks_client().get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=_ASYMMETRIC_ALGORITHMS,
                audience="authenticated",
                options=_JWT_DECODE_OPTIONS,
            )
        except InvalidTokenError as exc:
            raise _unauthorized("Invalid or expired access token") from exc

    raise _unauthorized("Invalid or expired access token")


def _auth_user_from_payload(payload: dict) -> AuthUser:
    sub = payload.get("sub")
    email = payload.get("email")
    if not sub or not email:
        raise _unauthorized("Access token missing required user claims")

    try:
        user_id = UUID(str(sub))
    except ValueError as exc:
        raise _unauthorized("Access token subject is not a valid user id") from exc

    return AuthUser(id=user_id, email=str(email))


def decode_access_token(token: str) -> AuthUser:
    """Verify Supabase access JWT using legacy secret or JWKS."""
    return _auth_user_from_payload(_payload_from_token(token))


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthUser:
    """Require a valid Supabase JWT on protected routes."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    return decode_access_token(credentials.credentials)


def get_optional_auth_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthUser | None:
    """Return authenticated user when a valid token is supplied."""
    if credentials is None:
        return None
    if credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    return decode_access_token(credentials.credentials)


def create_test_access_token(
    *,
    user_id: UUID,
    email: str,
    secret: str,
    expires_in_seconds: int = 3600,
    expired: bool = False,
) -> str:
    """Build HS256 JWTs for unit/integration tests."""
    now = datetime.now(UTC)
    exp = now + timedelta(seconds=-60 if expired else expires_in_seconds)
    payload = {
        "sub": str(user_id),
        "email": email,
        "aud": "authenticated",
        "iat": now,
        "exp": exp,
    }
    return jwt.encode(payload, secret, algorithm="HS256")
