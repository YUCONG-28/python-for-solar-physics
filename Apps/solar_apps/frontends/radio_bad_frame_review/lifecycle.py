"""Browser-client lifecycle tracking for the standalone review server."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any


class ClientLifecycle:
    """Request server shutdown after the final browser client disappears."""

    def __init__(
        self,
        *,
        stop_on_client_close: bool,
        shutdown_callback: Callable[[], None] | None,
        close_grace_seconds: float = 2.0,
        heartbeat_timeout_seconds: float = 20.0,
        heartbeat_interval_seconds: float = 5.0,
    ) -> None:
        self.stop_on_client_close = stop_on_client_close
        self.shutdown_callback = shutdown_callback
        self.close_grace_seconds = close_grace_seconds
        self.heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self._clients: dict[str, float] = {}
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self.shutdown_requested = False

    def config(self) -> dict[str, Any]:
        return {
            "ok": True,
            "stop_on_close": self.stop_on_client_close,
            "heartbeat_interval_ms": int(self.heartbeat_interval_seconds * 1000),
            "close_grace_ms": int(self.close_grace_seconds * 1000),
        }

    def heartbeat(self, client_id: str) -> dict[str, Any]:
        if not client_id:
            return {"ok": False, "error": "client_id is required"}
        with self._lock:
            self._clients[client_id] = time.monotonic()
            if (
                self.stop_on_client_close
                and self.shutdown_callback is not None
                and not self.shutdown_requested
                and not (self._timer and self._timer.is_alive())
            ):
                self._start_timer_locked(
                    self.heartbeat_timeout_seconds + self.close_grace_seconds
                )
        return {"ok": True}

    def close(
        self, client_id: str, *, client_requests_stop: bool = True
    ) -> dict[str, Any]:
        if client_id:
            with self._lock:
                self._clients.pop(client_id, None)
        if client_requests_stop and self.stop_on_client_close:
            self.schedule_shutdown_check()
        return {
            "ok": True,
            "shutdown_scheduled": client_requests_stop and self.stop_on_client_close,
        }

    def schedule_shutdown_check(self) -> None:
        if self.shutdown_callback is None:
            return
        with self._lock:
            if self.shutdown_requested:
                return
            if self._timer and self._timer.is_alive():
                self._timer.cancel()
            self._start_timer_locked(self.close_grace_seconds)

    def _start_timer_locked(self, delay_seconds: float) -> None:
        self._timer = threading.Timer(
            max(float(delay_seconds), 0.001), self._maybe_shutdown
        )
        self._timer.daemon = True
        self._timer.start()

    def _maybe_shutdown(self) -> None:
        callback: Callable[[], None] | None = None
        now = time.monotonic()
        with self._lock:
            self._timer = None
            self._clients = {
                client_id: seen_at
                for client_id, seen_at in self._clients.items()
                if now - seen_at <= self.heartbeat_timeout_seconds
            }
            if self.shutdown_requested:
                return
            if self._clients:
                remaining = max(
                    self.heartbeat_timeout_seconds - (now - seen_at)
                    for seen_at in self._clients.values()
                )
                self._start_timer_locked(remaining + self.close_grace_seconds)
                return
            self.shutdown_requested = True
            callback = self.shutdown_callback
        if callback is not None:
            callback()


__all__ = ["ClientLifecycle"]
