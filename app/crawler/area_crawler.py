import asyncio
import hashlib
import json
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Optional
from dataclasses import dataclass, field

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.crawler.rate_limiter import RateLimiter
from app.crawler.robots_checker import check_robots_allowed
from app.database import SessionLocal
from app.models.models import Source, RawDocument

GEO_QUERY_TEMPLATES = {
    "reddit": {
        "r/VietNam": "https://www.reddit.com/r/VietNam/search.json?q=food+recommend+district&restrict_sr=on&sort=relevance&limit=25",
        "r/saigon": "https://www.reddit.com/r/saigon/search.json?q=restaurant+best+eat&restrict_sr=on&sort=new&limit=25",
        "r/SoutheastAsia": "https://www.reddit.com/r/SoutheastAsia/search.json?q=saigon+food+local&restrict_sr=on&sort=relevance&limit=25",
        "r/VietNam_food": "https://www.reddit.com/r/VietNam/search.json?q=%E1%BB%91c+best+local&restrict_sr=on&sort=top&t=year&limit=25",
    },
    "forum": {
        "foody_vn": "https://www.foody.vn/ho-chi-minh/dia-diem",
    },
    "blog": {},
}

REDDIT_USER_AGENT = "python:local-scout-agent:v1.0 (by /u/local_scout_bot)"
FOOD_KEYWORDS = [
    "restaurant", "food", "eat", "best", "delicious", "ngon", "quán",
    "phở", "bánh mì", "cơm", "bún", "chả", "nem", "gỏi", "hủ tiếu",
    "cơm tấm", "bò kho", "bánh xèo", "bánh cuốn", "chè", "ốc",
    "recommend", "favorite", "hidden gem", "local", "must try",
]


@dataclass
class CrawlResult:
    url: str
    content_hash: str
    title: Optional[str]
    body: Optional[str]
    author_name: Optional[str]
    author_id: Optional[str]
    published_at: Optional[str]
    source_type: str
    language: Optional[str]
    raw_json: Optional[str]


@dataclass
class AreaCrawlJob:
    lat: float
    lon: float
    radius_km: float
    max_results_per_source: int = 50
    results: list[CrawlResult] = field(default_factory=list)
    stats: dict = field(default_factory=lambda: {"fetched": 0, "skipped_duplicate": 0, "blocked_robots": 0,
                                                  "errors": 0, "new_documents": 0})

    async def run(self) -> dict:
        start_time = time.monotonic()
        queries = self._build_queries()
        semaphore = asyncio.Semaphore(settings.crawl_concurrency_limit)
        rate_limiter = RateLimiter(settings.crawl_rate_limit_rps)

        async def crawl_source(source_name: str, url: str) -> Optional[CrawlResult]:
            async with semaphore:
                domain = self._extract_domain(url)
                await rate_limiter.acquire(domain)
                try:
                    allowed = await check_robots_allowed(
                        url, user_agent=settings.crawl_user_agent
                    )
                    if not allowed:
                        self.stats["blocked_robots"] += 1
                        return None
                except Exception:
                    pass

                try:
                    result = await self._fetch_and_parse(source_name, url)
                    if result is None:
                        self.stats["errors"] += 1
                    else:
                        self.stats["fetched"] += 1
                        self.results.append(result)
                    return result
                except Exception:
                    self.stats["errors"] += 1
                    return None

        tasks = []
        for source_name, urls in queries.items():
            for url in urls[:self.max_results_per_source]:
                tasks.append(asyncio.create_task(crawl_source(source_name, url)))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self._save_to_database()
        elapsed = time.monotonic() - start_time
        self.stats["elapsed_seconds"] = round(elapsed, 2)
        self.stats["total_results"] = len(self.results)
        return self.stats

    def _build_queries(self) -> dict[str, list[str]]:
        queries: dict[str, list[str]] = {}
        for source_type, source_map in GEO_QUERY_TEMPLATES.items():
            for source_name, base_url in source_map.items():
                if base_url:
                    queries.setdefault(source_type, []).append(base_url)
        return queries

    def _extract_domain(self, url: str) -> str:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or "unknown"

    async def _fetch_and_parse(self, source_name: str, url: str) -> Optional[CrawlResult]:
        from app.crawler.parsers.forum_parser import parse_foody_page
        from app.crawler.parsers.reddit_parser import parse_reddit_search_results
        from app.crawler.parsers.blog_parser import parse_blog_article

        parsers = {
            "reddit": parse_reddit_search_results,
            "forum": parse_foody_page,
            "blog": parse_blog_article,
        }
        source_type = self._determine_source_type(url)
        parser = parsers.get(source_type, parse_blog_article)
        return await parser(url)

    def _determine_source_type(self, url: str) -> str:
        if "reddit.com" in url:
            return "reddit"
        if "foody.vn" in url:
            return "forum"
        if any(d in url for d in ["blogspot.com", "wordpress.com", "vietnamcoracle.com",
                                   "saigoneseats.com", "migrationology.com", "legalnomads.com",
                                   "therantingpanda.com"]):
            return "blog"
        return "forum"

    def _is_food_related(self, text: str) -> bool:
        text_lower = text.lower()
        return any(kw in text_lower for kw in FOOD_KEYWORDS)

    def _save_to_database(self):
        db: Session = SessionLocal()
        try:
            for result in self.results:
                existing = db.query(RawDocument).filter_by(
                    content_hash=result.content_hash
                ).first()
                if existing:
                    self.stats["skipped_duplicate"] += 1
                    continue

                source = db.query(Source).filter_by(
                    source_type=result.source_type
                ).first()
                if not source:
                    source = Source(
                        name=result.source_type,
                        url_pattern="",
                        source_type=result.source_type,
                    )
                    db.add(source)
                    db.flush()

                doc = RawDocument(
                    source_id=source.id,
                    url=result.url,
                    content_hash=result.content_hash,
                    title=result.title,
                    body=result.body,
                    author_name=result.author_name,
                    author_id_hashed=result.author_id,
                    published_at=self._parse_datetime(result.published_at),
                    geo_lat=self.lat,
                    geo_lon=self.lon,
                    geo_radius_km=self.radius_km,
                    language=result.language or "unknown",
                    raw_json=result.raw_json,
                )
                db.add(doc)
                self.stats["new_documents"] += 1
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        for fmt in [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]:
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None
