import asyncio
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.crawler.area_crawler import CrawlResult
from app.config import settings

REDDIT_BASE = "https://www.reddit.com"
REDDIT_HEADERS = {"User-Agent": "python:local-scout-agent:v1.0 (by /u/local_scout_bot)"}


async def parse_reddit_search_results(url: str, client: Optional[httpx.AsyncClient] = None) -> CrawlResult:
    if client is None:
        async with httpx.AsyncClient(timeout=settings.crawl_timeout_seconds, headers=REDDIT_HEADERS) as client:
            return await _parse_reddit_search(url, client)
    return await _parse_reddit_search(url, client)


async def _parse_reddit_search(url: str, client: httpx.AsyncClient) -> CrawlResult:
    response = await client.get(url)
    response.raise_for_status()
    data = response.json()
    posts = data.get("data", {}).get("children", [])
    results = []
    for post in posts[:25]:
        post_data = post.get("data", {})
        body = post_data.get("selftext", "")
        title = post_data.get("title", "")
        combined = f"{title}\n{body}"
        content_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        author = post_data.get("author", "")
        author_id = hashlib.sha256(author.encode("utf-8")).hexdigest()[:16] if author else None
        created_utc = post_data.get("created_utc")
        published = datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat() if created_utc else None
        results.append(CrawlResult(
            url=f"{REDDIT_BASE}{post_data.get('permalink', '')}",
            content_hash=content_hash,
            title=title,
            body=body,
            author_name=author,
            author_id=author_id,
            published_at=published,
            source_type="reddit",
            language=_detect_language_simple(combined),
            raw_json=json.dumps(post_data, ensure_ascii=False),
        ))
    if results:
        return results[0]
    return CrawlResult(
        url=url, content_hash=hashlib.sha256(url.encode()).hexdigest(),
        title=None, body=None, author_name=None, author_id=None,
        published_at=None, source_type="reddit", language=None, raw_json=json.dumps(data),
    )


async def parse_reddit_thread(url: str, client: Optional[httpx.AsyncClient] = None) -> list[CrawlResult]:
    json_url = url.rstrip("/") + ".json"
    if client is None:
        async with httpx.AsyncClient(timeout=settings.crawl_timeout_seconds, headers=REDDIT_HEADERS) as client:
            return await _parse_reddit_thread(json_url, client)
    return await _parse_reddit_thread(json_url, client)


async def _parse_reddit_thread(json_url: str, client: httpx.AsyncClient) -> list[CrawlResult]:
    response = await client.get(json_url)
    response.raise_for_status()
    data = response.json()
    results = []
    for listing in data:
        children = listing.get("data", {}).get("children", [])
        for item in children:
            item_data = item.get("data", {})
            body = item_data.get("body", "") or item_data.get("selftext", "")
            if not body.strip():
                continue
            content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
            author = item_data.get("author", "")
            author_id = hashlib.sha256(author.encode("utf-8")).hexdigest()[:16] if author else None
            created_utc = item_data.get("created_utc")
            published = datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat() if created_utc else None
            results.append(CrawlResult(
                url=f"{REDDIT_BASE}{item_data.get('permalink', url)}",
                content_hash=content_hash,
                title=item_data.get("link_title"),
                body=body,
                author_name=author,
                author_id=author_id,
                published_at=published,
                source_type="reddit",
                language=_detect_language_simple(body),
                raw_json=json.dumps(item_data, ensure_ascii=False),
            ))
    return results


def _detect_language_simple(text: str) -> str:
    if not text.strip():
        return "unknown"
    vietnamese_chars = len(re.findall(r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]', text.lower()))
    total_chars = len(text)
    if total_chars > 0 and (vietnamese_chars / total_chars) > 0.02:
        return "vi"
    return "en"
