from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Callable, Awaitable


@dataclass(frozen=True)
class AutoreplyWorkerServices:
    process_unread: Callable[[int], Awaitable[dict[str, Any]]]
    process_lock: asyncio.Lock
    activity: dict[str, Any]
    is_enabled: Callable[[], bool]
    set_enabled: Callable[[bool], None]
    save_enabled: Callable[[bool], None]
    record_admin_log: Callable[[str, str, Any | None], None]
    error_detail: Callable[[Exception], object]
    interval_seconds: int


async def restore_worker_state(
    *,
    live_sync_enabled: bool,
    has_avito_credentials: bool,
    start_worker: Callable[[], None],
    services: AutoreplyWorkerServices,
) -> None:
    if not live_sync_enabled:
        services.save_enabled(False)
        services.activity["last_error"] = "Avito live sync is disabled"
        return
    if not has_avito_credentials:
        services.activity["last_error"] = "AVITO_CLIENT_ID and AVITO_CLIENT_SECRET are required"
        return
    services.set_enabled(True)
    services.activity.update(
        {
            "enabled": True,
            "interval_seconds": services.interval_seconds,
            "last_error": None,
        }
    )
    services.save_enabled(True)
    start_worker()


async def worker_loop(services: AutoreplyWorkerServices) -> None:
    while services.is_enabled():
        started_at = time.time()
        services.activity.update(
            {
                "enabled": True,
                "running": True,
                "last_started_at": started_at,
                "last_error": None,
            }
        )
        try:
            async with services.process_lock:
                result = await services.process_unread(20)
            services.activity["last_result"] = result
        except Exception as exc:  # pragma: no cover - surfaced through status endpoint
            services.activity["last_error"] = services.error_detail(exc)
            services.record_admin_log("error", "autoreply_worker_failed", {"error": services.error_detail(exc)})
        finally:
            services.activity.update(
                {
                    "running": False,
                    "last_finished_at": time.time(),
                    "enabled": services.is_enabled(),
                }
            )
        await asyncio.sleep(services.interval_seconds)


def activity_response(
    *,
    activity: dict[str, Any],
    task: asyncio.Task[None] | None,
) -> dict[str, Any]:
    task_state = "stopped"
    if task is not None and not task.done():
        task_state = "running" if activity["running"] else "waiting"
    return {
        **activity,
        "task_state": task_state,
    }
