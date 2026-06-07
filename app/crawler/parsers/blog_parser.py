import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.crawler.area_crawler import CrawlResult
from app.config import settings

BLOG_HEADERS = {
    "User-Agent": settings.crawl_user_agent,
    "Accept": "text/html,application/xhtml+xml,*/*",
}


async def parse_blog_article(url: str, client: Optional[httpx.AsyncClient] = None) -> CrawlResult:
    if client is None:
        async with httpx.AsyncClient(timeout=settings.crawl_timeout_seconds, headers=BLOG_HEADERS, follow_redirects=True) as client:
            return await _parse_blog(url, client)
    return await _parse_blog(url, client)


async def _parse_blog(url: str, client: httpx.AsyncClient) -> CrawlResult:
    try:
        response = await client.get(url)
        response.raise_for_status()
    except Exception:
        return _empty_blog(url)

    html = response.text
    title, body = _extract_with_newspaper_fallback(html, url)
    if not body:
        body = _extract_from_html(html)
    combined = f"{title or ''}\n{body}"
    content_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()

    author_match = re.search(r'<meta\s+name=["\']author["\']\s+content=["\']([^"\']+)["\']', html, re.I)
    author_name = author_match.group(1) if author_match else None
    author_id = hashlib.sha256(author_name.encode("utf-8")).hexdigest()[:16] if author_name else None

    date_match = re.search(
        r'<meta\s+(?:name=["\'](?:date|pubdate|article:published_time)["\']|property=["\']article:published_time["\'])\s+content=["\']([^"\']+)["\']',
        html, re.I,
    )
    published = date_match.group(1) if date_match else None
    lang = _detect_language(combined)
    return CrawlResult(
        url=url, content_hash=content_hash, title=title, body=body,
        author_name=author_name, author_id=author_id, published_at=published,
        source_type="blog", language=lang, raw_json=None,
    )


def _extract_with_newspaper_fallback(html: str, url: str) -> tuple[Optional[str], Optional[str]]:
    try:
        from newspaper import Article
        article = Article(url)
        article.download(input_html=html)
        article.parse()
        return article.title, article.text
    except Exception:
        return None, None


def _extract_from_html(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()
        article = soup.find("article") or soup.find("main") or soup.find("body")
        if article:
            paragraphs = article.find_all("p")
            return "\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)
    except Exception:
        pass

    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()[:10000]


def _detect_language(text: str) -> str:
    if not text.strip():
        return "unknown"
    vi_pattern = re.compile(r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]', re.IGNORECASE)
    vi_count = len(vi_pattern.findall(text))
    if vi_count > 2:
        return "vi"
    th_pattern = re.compile(r'[ก-๙]')
    if len(th_pattern.findall(text)) > 5:
        return "th"
    zh_pattern = re.compile(r'[\u4e00-\u9fff]')
    if len(zh_pattern.findall(text)) > 10:
        return "zh"
    return "en"


def _empty_blog(url: str) -> CrawlResult:
    return CrawlResult(
        url=url,
        content_hash=hashlib.sha256(url.encode()).hexdigest(),
        title=None, body=None, author_name=None, author_id=None,
        published_at=None, source_type="blog", language=None, raw_json=None,
    )
