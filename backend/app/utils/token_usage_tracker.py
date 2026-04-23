from __future__ import annotations

from dataclasses import dataclass, asdict
from threading import Lock
from time import time
from typing import Any, Dict, List


@dataclass(frozen=True)
class TokenUsageRecord:
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    duration_seconds: float
    timestamp_unix: float


class TokenUsageTracker:
    """Process-wide tracker for LLM token consumption and timing."""

    _lock: Lock = Lock()
    _totals: Dict[str, Any] = {
        "calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "total_duration_seconds": 0.0,
    }
    _per_model: Dict[str, Dict[str, Any]] = {}
    _recent_records: List[TokenUsageRecord] = []
    _max_recent_records: int = 200

    @classmethod
    def record(
        cls,
        *,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        duration_seconds: float,
    ) -> TokenUsageRecord:
        prompt_tokens = max(int(prompt_tokens or 0), 0)
        completion_tokens = max(int(completion_tokens or 0), 0)
        total_tokens = prompt_tokens + completion_tokens
        duration_seconds = max(float(duration_seconds or 0.0), 0.0)

        record = TokenUsageRecord(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            duration_seconds=duration_seconds,
            timestamp_unix=time(),
        )

        with cls._lock:
            cls._totals["calls"] += 1
            cls._totals["prompt_tokens"] += prompt_tokens
            cls._totals["completion_tokens"] += completion_tokens
            cls._totals["total_tokens"] += total_tokens
            cls._totals["total_duration_seconds"] += duration_seconds

            if model not in cls._per_model:
                cls._per_model[model] = {
                    "calls": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "total_duration_seconds": 0.0,
                }

            model_totals = cls._per_model[model]
            model_totals["calls"] += 1
            model_totals["prompt_tokens"] += prompt_tokens
            model_totals["completion_tokens"] += completion_tokens
            model_totals["total_tokens"] += total_tokens
            model_totals["total_duration_seconds"] += duration_seconds

            cls._recent_records.append(record)
            if len(cls._recent_records) > cls._max_recent_records:
                cls._recent_records = cls._recent_records[-cls._max_recent_records :]

        return record

    @classmethod
    def get_totals(cls) -> Dict[str, Any]:
        with cls._lock:
            return dict(cls._totals)

    @classmethod
    def get_model_totals(cls, model: str) -> Dict[str, Any]:
        with cls._lock:
            if model not in cls._per_model:
                return {
                    "calls": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "total_duration_seconds": 0.0,
                }
            return dict(cls._per_model[model])

    @classmethod
    def get_recent_records(cls, limit: int = 20) -> List[Dict[str, Any]]:
        limit = max(int(limit or 0), 0)
        with cls._lock:
            if limit == 0:
                records = cls._recent_records
            else:
                records = cls._recent_records[-limit:]
            return [asdict(record) for record in records]

    @classmethod
    def snapshot(cls, recent_limit: int = 20) -> Dict[str, Any]:
        with cls._lock:
            totals = dict(cls._totals)
            per_model = {k: dict(v) for k, v in cls._per_model.items()}
            if recent_limit <= 0:
                recent_records = cls._recent_records
            else:
                recent_records = cls._recent_records[-recent_limit:]

        return {
            "totals": totals,
            "per_model": per_model,
            "recent_records": [asdict(record) for record in recent_records],
        }

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._totals = {
                "calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "total_duration_seconds": 0.0,
            }
            cls._per_model = {}
            cls._recent_records = []
