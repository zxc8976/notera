"""Broadcast progress events to multiple async subscribers."""
from __future__ import annotations

import asyncio
import itertools
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, Iterable, Optional, Tuple


class ProgressEventBroadcaster:
    """Thread-safe publisher/subscriber helper for streaming task progress events."""

    def __init__(self, history_size: int = 100) -> None:
        self._lock = threading.RLock()
        self._subscribers: Dict[int, asyncio.Queue] = {}
        self._history: Deque[Dict[str, Any]] = deque(maxlen=max(history_size, 10))
        self._id_counter = itertools.count(1)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ------------------------------------------------------------------
    # Event loop management
    # ------------------------------------------------------------------
    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Remember the asyncio loop that should receive thread-safe callbacks."""
        with self._lock:
            if self._loop is loop or (self._loop and self._loop.is_running()):
                return
            self._loop = loop

    def _get_loop(self) -> Optional[asyncio.AbstractEventLoop]:
        with self._lock:
            loop = self._loop
        if loop and not loop.is_closed():
            return loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            self.bind_loop(loop)
        return loop

    # ------------------------------------------------------------------
    # Subscription helpers
    # ------------------------------------------------------------------
    def subscribe(self) -> Tuple[int, asyncio.Queue]:
        """Register a new subscriber and return its id and queue."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        subscriber_id = next(self._id_counter)
        with self._lock:
            self._subscribers[subscriber_id] = queue
        # Push recent history to help Bootstrap UI instantly
        history = list(self._history)
        if history:
            loop = self._get_loop()
            if loop and loop.is_running():
                loop.call_soon_threadsafe(self._prime_queue, queue, history)
            else:
                self._prime_queue(queue, history)
        return subscriber_id, queue

    def _prime_queue(self, queue: asyncio.Queue, history: Iterable[Dict[str, Any]]) -> None:
        for event in history:
            if queue.full():
                break
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                break

    def unsubscribe(self, subscriber_id: int) -> None:
        with self._lock:
            self._subscribers.pop(subscriber_id, None)

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------
    def publish(self, event: Dict[str, Any]) -> None:
        """Broadcast event to all subscribers and cache copy in history."""
        payload = dict(event)
        payload.setdefault("timestamp", time.time())

        with self._lock:
            self._history.append(payload)
            subscribers = list(self._subscribers.items())
            loop = self._loop

        if not subscribers:
            return

        for subscriber_id, queue in subscribers:
            try:
                if loop and loop.is_running():
                    loop.call_soon_threadsafe(self._put_safe, queue, payload, subscriber_id)
                else:
                    self._put_safe(queue, payload, subscriber_id)
            except RuntimeError:
                # Loop might be closed; remove subscriber lazily
                self.unsubscribe(subscriber_id)

    def _put_safe(
        self,
        queue: asyncio.Queue,
        payload: Dict[str, Any],
        subscriber_id: Optional[int] = None,
    ) -> None:
        try:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            # Should be rare due to pop above, fallback to drop oldest implicitly
            pass
        except Exception:
            if subscriber_id is not None:
                self.unsubscribe(subscriber_id)

    # ------------------------------------------------------------------
    # Queries for polling fallback
    # ------------------------------------------------------------------
    def recent(self, limit: int = 20, job_id: Optional[str] = None) -> Iterable[Dict[str, Any]]:
        """Return recent events, optionally filtered by job id."""
        with self._lock:
            items = list(self._history)
        if job_id is None:
            return items[-limit:]
        filtered = [item for item in items if item.get("job_id") == job_id]
        return filtered[-limit:]


__all__ = ["ProgressEventBroadcaster"]
