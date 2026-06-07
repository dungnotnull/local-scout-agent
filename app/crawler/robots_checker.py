import asyncio
import logging
import time
from collections import defaultdict
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_robots_cache: dict[str, tuple[float, bool]] = {}
ROBOTS_CACHE_TTL = 3600


class RobotsChecker:
    def __init__(self, user_agent: str = "LocalScoutAgent/1.0", cache_ttl: int = ROBOTS_CACHE_TTL):
        self.user_agent = user_agent
        self.cache_ttl = cache_ttl

    async def is_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        domain = parsed.netloc
        cache_key = f"{domain}:{self.user_agent}"
        now = time.time()

        if cache_key in _robots_cache:
            cached_time, cached_result = _robots_cache[cache_key]
            if now - cached_time < self.cache_ttl:
                return cached_result

        robots_url = f"{parsed.scheme}://{domain}/robots.txt"
        result = await self._fetch_and_parse(robots_url, url)
        _robots_cache[cache_key] = (now, result)
        return result

    async def _fetch_and_parse(self, robots_url: str, target_url: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(robots_url, follow_redirects=True)
                if response.status_code != 200:
                    return True

                lines = response.text.split("\n")
                current_agent = None
                disallowed_paths = []
                allowed_paths = []

                for line in lines:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if ":" not in line:
                        continue

                    field, _, value = line.partition(":")
                    field = field.strip().lower()
                    value = value.strip()

                    if field == "user-agent":
                        current_agent = value
                    elif current_agent and current_agent in (self.user_agent, "*"):
                        if field == "disallow":
                            disallowed_paths.append(value)
                        elif field == "allow":
                            allowed_paths.append(value)

                if not disallowed_paths:
                    return True

                target_path = urlparse(target_url).path
                for path in disallowed_paths:
                    if path and target_path.startswith(path):
                        if not any(target_path.startswith(a) for a in allowed_paths):
                            return False
                return True
        except Exception:
            return True


_global_checker = RobotsChecker()


async def check_robots_allowed(url: str, user_agent: str = "LocalScoutAgent/1.0") -> bool:
    checker = RobotsChecker(user_agent=user_agent)
    return await checker.is_allowed(url)
