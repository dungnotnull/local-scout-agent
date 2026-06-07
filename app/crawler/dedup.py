import hashlib
import logging
import time
from collections import OrderedDict
from typing import Optional

logger = logging.getLogger(__name__)


class Deduplicator:
    def __init__(self, max_entries: int = 100000):
        self._seen_hashes: OrderedDict[str, float] = OrderedDict()
        self._seen_urls: OrderedDict[str, float] = OrderedDict()
        self.max_entries = max_entries

    def compute_content_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def is_duplicate(self, url: str, content: Optional[str]) -> bool:
        now = time.time()
        self._evict_old(now)

        if url in self._seen_urls:
            self._seen_urls[url] = now
            self._seen_urls.move_to_end(url)
            return True

        if content:
            h = self.compute_content_hash(content)
            if h in self._seen_hashes:
                self._seen_hashes[h] = now
                self._seen_hashes.move_to_end(h)
                return True

        if content:
            h = self.compute_content_hash(content)
            self._seen_hashes[h] = now
            self._seen_hashes.move_to_end(h)
            self._trim(self._seen_hashes)

        self._seen_urls[url] = now
        self._seen_urls.move_to_end(url)
        self._trim(self._seen_urls)
        return False

    def _evict_old(self, now: float):
        cutoff = now - 86400
        while self._seen_hashes and next(reversed(self._seen_hashes.values())) < cutoff:
            self._seen_hashes.popitem(last=True)
        while self._seen_urls and next(reversed(self._seen_urls.values())) < cutoff:
            self._seen_urls.popitem(last=True)

    def _trim(self, d: OrderedDict):
        while len(d) > self.max_entries:
            d.popitem(last=True)


_global_dedup = Deduplicator()


def compute_content_hash(body: str) -> str:
    return _global_dedup.compute_content_hash(body)


def is_duplicate(url: str, content: Optional[str]) -> bool:
    return _global_dedup.is_duplicate(url, content)
