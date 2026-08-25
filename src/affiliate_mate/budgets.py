"""In-process source call budgets that prevent accidental unbounded collection."""

import threading
from collections.abc import Mapping
from dataclasses import dataclass, field


class BudgetExceededError(RuntimeError):
    pass


@dataclass(slots=True)
class SourceCallBudget:
    """Atomically reserve named provider calls against explicit process-local limits."""

    limits: Mapping[str, int]
    _used: dict[str, int] = field(default_factory=dict, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        for operation, limit in self.limits.items():
            if not operation.strip():
                raise ValueError("budget operation names must not be empty")
            if limit < 0:
                raise ValueError(f"budget for {operation!r} must be >= 0")

    def reserve(self, calls: Mapping[str, int]) -> None:
        """Reserve a group atomically; either every operation fits or none are charged."""

        for operation, count in calls.items():
            if count < 0:
                raise ValueError("reserved call counts must be >= 0")
            if operation not in self.limits:
                raise ValueError(f"no call budget configured for {operation!r}")
        with self._lock:
            for operation, count in calls.items():
                used = self._used.get(operation, 0)
                if used + count > self.limits[operation]:
                    raise BudgetExceededError(
                        f"call budget exceeded for {operation}: "
                        f"requested {count}, used {used}, limit {self.limits[operation]}"
                    )
            for operation, count in calls.items():
                self._used[operation] = self._used.get(operation, 0) + count

    def used(self, operation: str) -> int:
        with self._lock:
            return self._used.get(operation, 0)

    def remaining(self, operation: str) -> int:
        if operation not in self.limits:
            raise ValueError(f"no call budget configured for {operation!r}")
        with self._lock:
            return self.limits[operation] - self._used.get(operation, 0)

    def to_dict(self) -> dict[str, dict[str, int]]:
        with self._lock:
            return {
                operation: {
                    "limit": limit,
                    "used": self._used.get(operation, 0),
                    "remaining": limit - self._used.get(operation, 0),
                }
                for operation, limit in sorted(self.limits.items())
            }
