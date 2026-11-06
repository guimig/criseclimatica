"""Limit server-side PED calls across collectors within one GitHub Actions build.

The PED portal states that external accounts are allowed at most twelve
requests/minute. We use a conservative nine calls / sixty-one seconds to
leave room for SGAA authentication and token-retry calls.
"""
from __future__ import annotations

import time
from collections import deque
from threading import Lock
from typing import Callable


class PedRateLimiter:
    def __init__(self, *, limit: int = 9, window: float = 61.0,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        if not 1 <= limit <= 11 or window < 60:
            raise ValueError("Invalid PED rate limit")
        self._limit = limit
        self._window = window
        self._clock = clock
        self._sleep = sleep
        self._history: deque[float] = deque()
        self._lock = Lock()

    def acquire(self) -> None:
        """Reserve a request slot before making a PED HTTP call."""
        with self._lock:
            now = self._clock()
            while True:
                while self._history and now - self._history[0] >= self._window:
                    self._history.popleft()
                if len(self._history) < self._limit:
                    self._history.append(now)
                    return
                self._sleep(max(self._window - (now - self._history[0]), 0.01))
                now = self._clock()
