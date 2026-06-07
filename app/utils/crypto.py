import hashlib


def hash_string(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]
