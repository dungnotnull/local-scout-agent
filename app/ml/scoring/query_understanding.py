import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class QueryIntent(str, Enum):
    DISH_SEARCH = "dish_search"
    VENUE_SEARCH = "venue_search"
    TRUST_AUDIT = "trust_audit"
    AREA_SCOUT = "area_scout"


@dataclass
class ParsedQuery:
    original: str
    intent: QueryIntent = QueryIntent.VENUE_SEARCH
    dishes: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    dietary_constraints: list[str] = field(default_factory=list)
    implicit_filters: dict = field(default_factory=dict)
    price_max_vnd: Optional[int] = None
    min_gem_score: Optional[int] = None
    expanded_queries: list[str] = field(default_factory=list)


DISH_PATTERNS = re.compile(
    r'\b(phở|pho|bánh mì|banh mi|bún|bun|bún bò|bun bo|bánh xèo|banh xeo|'
    r'cơm tấm|com tam|gỏi cuốn|goi cuon|chả giò|cha gio|bò kho|bo kho|'
    r'hủ tiếu|hu tieu|cơm|com|cháo|chao|bánh cuốn|banh cuon|nem|chả|'
    r'lẩu|lau|hotpot|bánh canh|banh canh|mì quảng|mi quang)\b',
    re.IGNORECASE,
)

LOCATION_PATTERNS = re.compile(
    r'\b(district\s*\d+|d\.\s*\d+|quận\s*\d+|quan\s*\d+|'
    r'bình thạnh|binh thanh|tân bình|tan binh|phú nhuận|phu nhuan|'
    r'gò vấp|go vap|thủ đức|thu duc|nhà bè|nha be|'
    r'q\.?\s*\d+|d\.?\s*\d+)\b',
    re.IGNORECASE,
)

DIETARY_PATTERNS = re.compile(
    r'\b(vegetarian|vegan|chay|gluten[- ]?free|halal|'
    r'no pork|không thịt heo|kosher|dairy[- ]?free|'
    r'ăn chay|thuần chay)\b',
    re.IGNORECASE,
)

PRICE_PATTERNS = re.compile(
    r'\b(cheap|budget|affordable|rẻ|bình dân|under\s*(\d+)[kK]?|'
    r'dưới\s*(\d+)[kK]?|(\d+)[kK]\b|'
    r'expensive|fine dining|sang|cao cấp|luxury)\b',
    re.IGNORECASE,
)

IMPLICIT_FILTER_RULES = {
    "cheap": {"price_range": "budget", "price_max_vnd": 50000},
    "bình dân": {"price_range": "budget", "price_max_vnd": 50000},
    "affordable": {"price_range": "budget"},
    "rẻ": {"price_range": "budget"},
    "local": {"min_gem_score": 70},
    "authentic": {"min_gem_score": 60},
    "tourist trap": {"max_gem_score": 30},
    "ngon": {"min_gem_score": 50},
    "best": {"min_gem_score": 70},
    "nhất": {"min_gem_score": 60},
}


class QueryUnderstandingEngine:
    def __init__(self, embedding_pipeline=None):
        self._embedding_pipeline = embedding_pipeline

    def parse(self, query: str) -> ParsedQuery:
        parsed = ParsedQuery(original=query)

        parsed.dishes = [m.strip() for m in DISH_PATTERNS.findall(query.lower()) if m.strip()]
        parsed.dishes = list(dict.fromkeys(parsed.dishes))

        parsed.locations = [m.strip() for m in LOCATION_PATTERNS.findall(query.lower()) if m.strip()]
        parsed.locations = list(dict.fromkeys(parsed.locations))

        dietary = [m.strip() for m in DIETARY_PATTERNS.findall(query.lower()) if m.strip()]
        parsed.dietary_constraints = list(dict.fromkeys(dietary))

        price_matches = PRICE_PATTERNS.findall(query.lower())
        for match in price_matches:
            if isinstance(match, tuple):
                for m in match:
                    if m and m.isdigit():
                        parsed.price_max_vnd = int(m) * 1000
                        parsed.implicit_filters["price_max_vnd"] = parsed.price_max_vnd
            elif match:
                parsed.implicit_filters[f"price_{match}"] = True

        for keyword, filter_rules in IMPLICIT_FILTER_RULES.items():
            if keyword in query.lower():
                parsed.implicit_filters.update(filter_rules)

        if "min_gem_score" in parsed.implicit_filters:
            parsed.min_gem_score = parsed.implicit_filters["min_gem_score"]

        parsed.intent = self._classify_intent(query)
        parsed.expanded_queries = self._expand_query(query, parsed)

        return parsed

    def _classify_intent(self, query: str) -> QueryIntent:
        query_lower = query.lower()

        audit_signals = ["trust", "audit", "check if", "verify", "scam", "fake", "kiểm tra"]
        if any(s in query_lower for s in audit_signals):
            return QueryIntent.TRUST_AUDIT

        dish_signals = ["find me", "show me", "i want", "looking for", "tìm", "muốn ăn"]
        if any(s in query_lower for s in dish_signals) and DISH_PATTERNS.search(query_lower):
            return QueryIntent.DISH_SEARCH

        area_signals = ["area", "near", "nearby", "around here", "close to", "gần đây", "xung quanh"]
        if any(s in query_lower for s in area_signals):
            return QueryIntent.AREA_SCOUT

        return QueryIntent.VENUE_SEARCH

    def _expand_query(self, query: str, parsed: ParsedQuery) -> list[str]:
        expansions = [query]

        en_terms = ["best", "delicious", "authentic", "local", "hidden gem", "must try"]
        vi_terms = ["ngon nhất", "ngon", "quán ngon", "ăn ngon", "địa phương"]

        has_en = any(t in query.lower() for t in en_terms)
        has_vi = any(t in query.lower() for t in vi_terms)

        if has_en and not has_vi:
            base = query
            for vi_term in vi_terms[:2]:
                expansions.append(f"{base} {vi_term}")
        elif has_vi and not has_en:
            base = query
            for en_term in en_terms[:2]:
                expansions.append(f"{base} {en_term}")

        if parsed.dishes:
            for dish in parsed.dishes:
                expansions.append(f"{dish} authentic local best")
                expansions.append(f"{dish} ngon nhất quán")

        return list(dict.fromkeys(expansions))

    def to_search_filters(self, parsed: ParsedQuery) -> dict:
        filters = {}
        if parsed.min_gem_score:
            filters["min_gem_score"] = parsed.min_gem_score
        if parsed.implicit_filters.get("max_gem_score"):
            filters["max_gem_score"] = parsed.implicit_filters["max_gem_score"]
        if parsed.implicit_filters.get("price_range"):
            filters["price_range"] = parsed.implicit_filters["price_range"]
        if parsed.implicit_filters.get("price_max_vnd"):
            filters["max_price_vnd"] = parsed.implicit_filters["price_max_vnd"]
        if parsed.dishes:
            filters["query"] = " ".join(parsed.dishes)
        return filters


query_engine = QueryUnderstandingEngine()
