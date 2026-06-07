import asyncio
import logging
import time
from collections import defaultdict
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, max_rps: float = 1.0):
        self.max_rps = max_rps
        self.min_interval = 1.0 / max_rps if max_rps > 0 else 0
        self._last_request: defaultdict[str, float] = defaultdict(float)
        self._lock = asyncio.Lock()
        self._consecutive_429: defaultdict[str, int] = defaultdict(int)
        self._backoff_until: defaultdict[str, float] = defaultdict(float)

    async def acquire(self, domain: str = "default"):
        async with self._lock:
            now = time.monotonic()
            if now < self._backoff_until[domain]:
                wait = self._backoff_until[domain] - now
                logger.debug(f"Backing off {domain} for {wait:.1f}s")
                await asyncio.sleep(wait)

            effective_interval = self.min_interval * (2 ** self._consecutive_429[domain])
            elapsed = now - self._last_request[domain]
            if elapsed < effective_interval:
                await asyncio.sleep(effective_interval - elapsed)
            self._last_request[domain] = time.monotonic()

    def report_429(self, domain: str):
        self._consecutive_429[domain] += 1
        backoff = min(60 * (2 ** self._consecutive_429[domain]), 3600)
        self._backoff_until[domain] = time.monotonic() + backoff
        logger.warning(f"Rate limited on {domain}, backing off {backoff}s")

    def report_success(self, domain: str):
        if self._consecutive_429[domain] > 0:
            self._consecutive_429[domain] = max(0, self._consecutive_429[domain] - 1)
