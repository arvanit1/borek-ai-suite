"""Data store factory (AT-40 / AT-41)."""

from __future__ import annotations

from typing import Union

from app.config import settings
from app.services.data.memory_store import MemoryDataStore, get_memory_store
from app.services.data.supabase_store import SupabaseDataStore

DataStore = Union[MemoryDataStore, SupabaseDataStore]


def build_data_store(access_token: str | None) -> DataStore:
    if settings.API_DATA_BACKEND == "memory":
        return get_memory_store()
    if not access_token:
        raise ValueError("Supabase data backend requires a bearer access token")
    return SupabaseDataStore(access_token)


def build_worker_data_store() -> DataStore:
    """Build the worker store without putting user JWTs on the broker."""
    if settings.API_DATA_BACKEND == "memory":
        return get_memory_store()
    return SupabaseDataStore(settings.SUPABASE_SERVICE_ROLE_KEY)
