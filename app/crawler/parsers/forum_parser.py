import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from app.crawler.area_crawler import CrawlResult
from app.config import settings

FOODY_HEADERS = {
    "User-Agent": settings.crawl_user_agent,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi,en;q=0.9",
}


async def parse_foody_page(url: str, client: Optional[httpx.AsyncClient] = None) -> CrawlResult:
    if client is None:
        async with httpx.AsyncClient(timeout=settings.crawl_timeout_seconds, headers=FOODY_HEADERS, follow_redirects=True) as client:
            return await _parse_foody(url, client)
    return await _parse_foody(url, client)


async def _parse_foody(url: str, client: httpx.AsyncClient) -> CrawlResult:
    try:
        response = await client.get(url)
        response.raise_for_status()
    except Exception:
        return _empty_result(url, "forum")

    soup = BeautifulSoup(response.text, "html.parser")
    title_el = soup.find("h1") or soup.find("title")
    title = title_el.get_text(strip=True) if title_el else None

    body_parts = []
    for tag in soup.find_all(["p", "div", "span", "article"]):
        text = tag.get_text(strip=True)
        if text and len(text) > 20:
            body_parts.append(text)

    body = "\n".join(body_parts[:20])
    combined = f"{title or ''}\n{body}"
    content_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()

    author_el = soup.find("a", class_=re.compile(r"user|author|profile|nguoi-dung", re.I))
    author_name = author_el.get_text(strip=True) if author_el else None
    author_id = hashlib.sha256(author_name.encode("utf-8")).hexdigest()[:16] if author_name else None

    time_el = soup.find(["time", "span"], class_=re.compile(r"time|date|ngay", re.I))
    published = None
    if time_el:
        published = time_el.get_text(strip=True) or time_el.get("datetime")

    return CrawlResult(
        url=url,
        content_hash=content_hash,
        title=title,
        body=body,
        author_name=author_name,
        author_id=author_id,
        published_at=published,
        source_type="forum",
        language=_detect_vi_en(combined),
        raw_json=None,
    )


async def parse_generic_forum(url: str, client: Optional[httpx.AsyncClient] = None) -> CrawlResult:
    return await parse_foody_page(url, client)


def _detect_vi_en(text: str) -> str:
    if not text.strip():
        return "unknown"
    vi_pattern = re.compile(r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]', re.IGNORECASE)
    vi_count = len(vi_pattern.findall(text))
    if vi_count > 2:
        return "vi"
    return "en"


def _empty_result(url: str, source_type: str) -> CrawlResult:
    return CrawlResult(
        url=url,
        content_hash=hashlib.sha256(url.encode()).hexdigest(),
        title=None, body=None, author_name=None, author_id=None,
        published_at=None, source_type=source_type, language=None, raw_json=None,
    )
