"""AT-35: Celery + Redis integration wiring (requires running Redis)."""

from __future__ import annotations

import pytest

from app.worker import health_check_task


@pytest.mark.integration
def test_health_check_task_executes_via_redis() -> None:
    async_result = health_check_task.delay()
    result = async_result.get(timeout=10)
    assert result == {"status": "ok", "worker": "alive"}
