import hashlib


def compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def url_to_cache_key(url: str) -> str:
    return f"crawl:{hashlib.md5(url.encode('utf-8')).hexdigest()[:16]}"
