import logging
import hashlib
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Restaurant
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class TrustAuditRequest(BaseModel):
    url: HttpUrl
    restaurant_name: Optional[str] = None


class TrustAuditResponse(BaseModel):
    url: str
    restaurant_name: Optional[str] = None
    trust_score: float
    red_flags: list[str]
    green_flags: list[str]
    recommendation: str
    review_distribution: dict
    analyzed_at: str


TRUST_RED_FLAGS = re.compile(
    r'\b(all 5[- ]?star|perfect|must visit|best (?:ever|in the world))'
    r'|\b(sponsor|ad|paid|promoted|kol|influencer)\b'
    r'|\b(overpriced|tourist trap|rip[- ]?off|scam)\b',
    re.IGNORECASE,
)

TRUST_GREEN_FLAGS = re.compile(
    r'\b(local|neighborhood|regular|came back|returned|every week|my go[- ]?to)\b'
    r'|\b(grandma|family recipe|decades|old school|authentic recipe)\b',
    re.IGNORECASE,
)


@router.post("/trust-audit", response_model=TrustAuditResponse)
async def audit_trust(request: TrustAuditRequest, db: Session = Depends(get_db)):
    url_str = str(request.url)
    restaurant_name = request.restaurant_name
    red_flags = []
    green_flags = []
    review_distribution = {"5_star": 0, "4_star": 0, "3_star": 0, "2_star": 0, "1_star": 0}

    if not restaurant_name:
        restaurant_name = _extract_restaurant_name_from_url(url_str)

    if restaurant_name:
        restaurant = db.query(Restaurant).filter(Restaurant.canonical_name.ilike(f"%{restaurant_name}%")).first()
    else:
        restaurant = None

    if restaurant:
        trust_score = restaurant.gem_score or 50.0
        if restaurant.gem_score_components:
            import json
            try:
                comps = json.loads(restaurant.gem_score_components)
                red_flags = comps.get("red_flags", [])
                green_flags = comps.get("green_flags", [])
            except (json.JSONDecodeError, TypeError):
                pass
        if restaurant.local_ratio is not None:
            if restaurant.local_ratio > 0.6:
                green_flags.append("High local-to-tourist reviewer ratio")
            elif restaurant.local_ratio < 0.2:
                red_flags.append("Most reviewers appear to be tourists/one-time visitors")
    else:
        page_content = await _try_fetch_page(url_str)
        red_flags = _extract_flags(page_content, TRUST_RED_FLAGS)
        green_flags = _extract_flags(page_content, TRUST_GREEN_FLAGS)
        trust_score = _calculate_heuristic_trust(red_flags, green_flags)
        review_distribution = _estimate_review_distribution(page_content)

    red_flags = list(dict.fromkeys(red_flags))
    green_flags = list(dict.fromkeys(green_flags))

    if trust_score >= 75:
        recommendation = "High trust — strong signals of authentic local reviews. Likely a genuine hidden gem."
    elif trust_score >= 50:
        recommendation = "Moderate trust — some authentic signals but mixed. Verify with local sources."
    elif trust_score >= 25:
        recommendation = "Low trust — multiple tourist trap indicators. Approach with caution."
    else:
        recommendation = "Very low trust — strong PR/tourist trap signals. Consider alternatives."

    return TrustAuditResponse(
        url=url_str,
        restaurant_name=restaurant_name,
        trust_score=round(trust_score, 1),
        red_flags=red_flags,
        green_flags=green_flags,
        recommendation=recommendation,
        review_distribution=review_distribution,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )


def _extract_restaurant_name_from_url(url: str) -> Optional[str]:
    patterns = [
        r'(?:place|restaurant|business)/(?:[^/]+/)?([^/?]+)',
        r'(?:restaurant|venue)/([^/?]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            name = match.group(1).replace("-", " ").replace("+", " ")
            return " ".join(name.split())
    return None


async def _try_fetch_page(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": settings.crawl_user_agent})
            return response.text[:20000]
    except Exception:
        return ""


def _extract_flags(text: str, pattern: re.Pattern) -> list[str]:
    matches = pattern.findall(text)
    flags = []
    for match in matches:
        if isinstance(match, tuple):
            for m in match:
                if m:
                    flags.append(m.strip().lower())
        elif match:
            flags.append(match.strip().lower())
    return list(set(flags))


def _calculate_heuristic_trust(red_flags: list[str], green_flags: list[str]) -> float:
    base_score = 50.0
    base_score -= len(red_flags) * 7.0
    base_score += len(green_flags) * 5.0
    return max(0.0, min(100.0, base_score))


def _estimate_review_distribution(text: str) -> dict:
    stars = re.findall(r'(\d)[\s]*(?:star|sao)', text.lower())
    distribution = {"5_star": 0, "4_star": 0, "3_star": 0, "2_star": 0, "1_star": 0}
    for star in stars:
        key = f"{star}_star"
        if key in distribution:
            distribution[key] += 1
    return distribution
