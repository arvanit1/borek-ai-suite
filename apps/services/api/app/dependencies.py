"""Shared FastAPI dependency injection helpers (AT-34 / AT-39 / AT-40)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import AuthUser, get_current_user, get_optional_auth_user
from app.services.data import DataStore, build_data_store

_bearer = HTTPBearer(auto_error=False)

__all__ = [
    "AuthUser",
    "AuthUserDep",
    "CurrentUserDep",
    "DataStoreDep",
    "DbSessionDep",
    "OptionalAuthUserDep",
    "get_auth_user",
    "get_current_user",
    "get_data_store",
    "get_optional_auth_user",
    "get_db_session",
]


def get_data_store(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> DataStore:
    """Return memory or Supabase-backed store for the current request."""
    token = credentials.credentials if credentials and credentials.scheme.lower() == "bearer" else None
    return build_data_store(token)


async def get_db_session() -> Any:
    """Legacy SQLAlchemy hook — use get_data_store() for AT-40 routes."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "code": "NOT_IMPLEMENTED",
            "message": "Direct SQLAlchemy sessions are not configured; use Supabase REST store",
        },
    )


get_auth_user = get_current_user

DataStoreDep = Annotated[DataStore, Depends(get_data_store)]
DbSessionDep = Annotated[Any, Depends(get_db_session)]
AuthUserDep = Annotated[AuthUser, Depends(get_auth_user)]
OptionalAuthUserDep = Annotated[AuthUser | None, Depends(get_optional_auth_user)]
CurrentUserDep = AuthUserDep
