"""Utilities to enforce and record OCR → verification → synthesis pipeline stages."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PipelineStage:
    name: str
    status: str = "pending"
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    detail: Optional[str] = None
    error: Optional[str] = None

    def mark_started(self, detail: Optional[str] = None) -> None:
        self.started_at = time.time()
        self.status = "running"
        if detail:
            self.detail = detail

    def mark_completed(self, detail: Optional[str] = None) -> None:
        self.completed_at = time.time()
        self.status = "completed"
        if detail:
            self.detail = detail

    def mark_failed(self, error: str) -> None:
        self.completed_at = time.time()
        self.status = "failed"
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "detail": self.detail,
            "error": self.error,
        }


class PipelineTrace:
    """Track sequential execution of OCR → verification → synthesis stages."""

    def __init__(self) -> None:
        self._stages: Dict[str, PipelineStage] = {
            "ocr": PipelineStage(name="ocr"),
            "verification": PipelineStage(name="verification"),
            "synthesis": PipelineStage(name="synthesis"),
        }
        self._history: List[str] = []

    def stage(self, name: str) -> PipelineStage:
        if name not in self._stages:
            raise KeyError(f"Unknown pipeline stage: {name}")
        return self._stages[name]

    def mark_started(self, name: str, detail: Optional[str] = None) -> None:
        stage = self.stage(name)
        stage.mark_started(detail=detail)
        self._history.append(f"{name}:started")

    def mark_completed(self, name: str, detail: Optional[str] = None) -> None:
        stage = self.stage(name)
        stage.mark_completed(detail=detail)
        self._history.append(f"{name}:completed")

    def mark_failed(self, name: str, error: str) -> None:
        stage = self.stage(name)
        stage.mark_failed(error)
        self._history.append(f"{name}:failed")

    def assert_sequence(self) -> None:
        required = ["ocr:completed", "verification:completed", "synthesis:completed"]
        history = ":".join(self._history)
        missing = [sig for sig in required if sig not in self._history]
        if missing:
            raise RuntimeError(
                f"Pipeline stages missing or out of order: {missing}; history={history}"
            )
        if self._history.index("verification:completed") < self._history.index("ocr:completed"):
            raise RuntimeError("Verification completed before OCR stage")
        if self._history.index("synthesis:completed") < self._history.index("verification:completed"):
            raise RuntimeError("Synthesis completed before verification stage")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stages": {name: stage.to_dict() for name, stage in self._stages.items()},
            "history": list(self._history),
        }


__all__ = ["PipelineTrace", "PipelineStage"]
