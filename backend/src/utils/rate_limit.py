from __future__ import annotations

from time import sleep, time


class SimpleRateLimiter:
    def __init__(self, calls_per_second: float):
        self.min_gap = 1.0 / max(calls_per_second, 0.001)
        self.last = 0.0

    def wait(self) -> None:
        now = time()
        gap = now - self.last
        if gap < self.min_gap:
            sleep(self.min_gap - gap)
        self.last = time()
