"""Thread-safe task status manager."""
from __future__ import annotations

import threading
from copy import deepcopy
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Tuple


class StatusManager:
    """Coordinate access to background task statuses in a thread-safe manner."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._meta: Dict[str, Any] = {}
        self._listeners: List[Callable[[str, Dict[str, Any], str], None]] = []

    # ------------------------------------------------------------------
    # Task lifecycle helpers
    # ------------------------------------------------------------------
    def create(self, task_id: str, initial: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            snapshot = dict(initial or {})
            self._tasks[task_id] = snapshot
        snapshot_copy = deepcopy(snapshot)
        self._notify_listeners(task_id, snapshot_copy, event_type="create")
        return snapshot_copy

    def update(self, task_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            task = self._tasks.setdefault(task_id, {})
            task.update(updates)
            snapshot = deepcopy(task)
        self._notify_listeners(task_id, snapshot, event_type="update")
        return snapshot

    def ensure(self, task_id: str) -> Dict[str, Any]:
        return self.update(task_id, {})

    def remove(self, task_id: str) -> bool:
        removed = False
        snapshot: Dict[str, Any] = {}
        with self._lock:
            if task_id in self._tasks:
                snapshot = deepcopy(self._tasks.pop(task_id))
                removed = True
        if removed:
            self._notify_listeners(task_id, snapshot, event_type="remove")
        return removed

    def clear(self) -> None:
        with self._lock:
            self._tasks.clear()
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener("__all__", {}, "clear")
            except Exception:
                continue

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def get(self, task_id: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            if task_id in self._tasks:
                return deepcopy(self._tasks[task_id])
            return deepcopy(default) if default is not None else {}

    def contains(self, task_id: str) -> bool:
        with self._lock:
            return task_id in self._tasks

    def items(self) -> Iterator[Tuple[str, Dict[str, Any]]]:
        with self._lock:
            snapshot = [(key, deepcopy(value)) for key, value in self._tasks.items()]
        return iter(snapshot)

    def values(self) -> Iterable[Dict[str, Any]]:
        with self._lock:
            snapshot = [deepcopy(value) for value in self._tasks.values()]
        return snapshot

    def keys(self) -> Iterable[str]:
        with self._lock:
            return list(self._tasks.keys())

    def find_similar(self, task_id: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Return a task with matching basename (without extension)."""
        base = task_id.rsplit(".", 1)[0]
        with self._lock:
            if task_id in self._tasks:
                return task_id, deepcopy(self._tasks[task_id])
            if base in self._tasks:
                return base, deepcopy(self._tasks[base])
            for key, value in self._tasks.items():
                if key.startswith(base):
                    return key, deepcopy(value)
        return None

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return deepcopy(self._tasks)

    def latest_metrics(self) -> Optional[Dict[str, Any]]:
        latest: Optional[Dict[str, Any]] = None
        latest_ts = 0.0
        with self._lock:
            for value in self._tasks.values():
                metrics = value.get("metrics")
                if not isinstance(metrics, dict):
                    continue
                try:
                    ts_raw = metrics.get("ts") or metrics.get("timestamp") or 0
                    ts = float(ts_raw)
                except Exception:
                    ts = 0.0
                if metrics and ts >= latest_ts:
                    latest = deepcopy(metrics)
                    latest_ts = ts
        return latest

    # ------------------------------------------------------------------
    # Metadata helpers (non task-specific)
    # ------------------------------------------------------------------
    def set_meta(self, key: str, value: Any) -> None:
        with self._lock:
            self._meta[key] = value

    def get_meta(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._meta.get(key, default)

    def clear_meta(self, key: str) -> None:
        with self._lock:
            self._meta.pop(key, None)

    def meta_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return deepcopy(self._meta)

    # ------------------------------------------------------------------
    # Task cancellation helpers
    # ------------------------------------------------------------------
    def mark_cancelled(self, task_id: str) -> bool:
        """Mark a task as cancelled. Returns True if task exists."""
        with self._lock:
            if task_id not in self._tasks:
                return False
            self._tasks[task_id]["cancelled"] = True
            self._tasks[task_id]["status"] = "已取消"
            self._tasks[task_id]["status_code"] = "cancelled"
            snapshot = deepcopy(self._tasks[task_id])
        self._notify_listeners(task_id, snapshot, event_type="cancel")
        return True

    def is_cancelled(self, task_id: str) -> bool:
        """Check if a task has been cancelled."""
        with self._lock:
            if task_id not in self._tasks:
                return False
            return self._tasks[task_id].get("cancelled", False)

    # ------------------------------------------------------------------
    # Listener management
    # ------------------------------------------------------------------
    def add_listener(self, listener: Callable[[str, Dict[str, Any], str], None]) -> None:
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[str, Dict[str, Any], str], None]) -> None:
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def _notify_listeners(self, task_id: str, snapshot: Dict[str, Any], event_type: str) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(task_id, deepcopy(snapshot), event_type)
            except Exception:
                continue


__all__ = ["StatusManager"]
