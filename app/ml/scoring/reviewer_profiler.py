import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.models import Review, RawDocument

logger = logging.getLogger(__name__)


@dataclass
class ReviewerProfile:
    author_id_hashed: str
    account_age_days: Optional[int] = None
    post_count: int = 0
    review_count: int = 0
    geo_diversity: float = 0.0
    avg_review_length: float = 0.0
    local_regular_score: float = 0.5
    language_mix: dict = field(default_factory=dict)
    first_seen: Optional[datetime] = None
    last_active: Optional[datetime] = None


class ReviewerProfiler:
    def __init__(self):
        self._profile_cache: dict[str, ReviewerProfile] = {}

    def profile_reviewer(self, author_id_hashed: str, db: Session) -> ReviewerProfile:
        if author_id_hashed in self._profile_cache:
            return self._profile_cache[author_id_hashed]

        profile = ReviewerProfile(author_id_hashed=author_id_hashed)
        documents = (
            db.query(RawDocument)
            .filter(RawDocument.author_id_hashed == author_id_hashed)
            .order_by(RawDocument.fetched_at.asc())
            .limit(100)
            .all()
        )

        reviews = (
            db.query(Review)
            .filter(Review.author_id_hashed == author_id_hashed)
            .order_by(Review.published_at.asc())
            .limit(100)
            .all()
        )

        if documents:
            timestamps = [d.fetched_at for d in documents if d.fetched_at]
            if timestamps:
                profile.first_seen = min(timestamps)
                profile.last_active = max(timestamps)
                if profile.first_seen:
                    profile.account_age_days = (datetime.now(timezone.utc) - profile.first_seen).days
            profile.post_count = len(documents)

            geo_coords = [(d.geo_lat, d.geo_lon) for d in documents if d.geo_lat and d.geo_lon]
            if geo_coords:
                profile.geo_diversity = self._compute_geo_diversity(geo_coords)

            lang_counts = Counter((d.language or "unknown") for d in documents)
            profile.language_mix = dict(lang_counts.most_common(5))

        if reviews:
            profile.review_count = len(reviews)
            lengths = [len(r.body_text or "") for r in reviews if r.body_text]
            profile.avg_review_length = sum(lengths) / len(lengths) if lengths else 0.0

        profile.local_regular_score = self._compute_local_score(profile)
        self._profile_cache[author_id_hashed] = profile
        return profile

    def _compute_geo_diversity(self, coords: list[tuple[float, float]]) -> float:
        if len(coords) < 2:
            return 0.0
        from app.utils.geo import haversine_distance
        distances = []
        for i in range(len(coords)):
            for j in range(i + 1, len(coords)):
                d = haversine_distance(coords[i][0], coords[i][1], coords[j][0], coords[j][1])
                distances.append(d)
        return sum(distances) / len(distances) if distances else 0.0

    def _compute_local_score(self, profile: ReviewerProfile) -> float:
        score = 0.5

        if profile.account_age_days is not None:
            if profile.account_age_days > 365:
                score += 0.15
            elif profile.account_age_days > 180:
                score += 0.10
            elif profile.account_age_days < 30:
                score -= 0.1

        if profile.post_count > 20:
            score += 0.10

        if profile.geo_diversity < 5.0:
            score += 0.15
        elif profile.geo_diversity > 50.0:
            score -= 0.1

        if profile.avg_review_length > 200:
            score += 0.05
        elif profile.avg_review_length < 30:
            score -= 0.05

        return max(0.0, min(1.0, score))

    def classify_reviewer(self, profile: ReviewerProfile) -> str:
        if profile.local_regular_score >= 0.7:
            return "local_regular"
        if profile.local_regular_score >= 0.4:
            return "mixed_user"
        if profile.geo_diversity > 50.0:
            return "tourist_traveler"
        return "one_time_visitor"


class LocalRatioCalculator:
    def __init__(self, profiler: ReviewerProfiler):
        self.profiler = profiler

    def calculate_for_restaurant(self, restaurant_id: int, db: Session) -> dict:
        reviews = (
            db.query(Review)
            .filter(Review.restaurant_id == restaurant_id)
            .all()
        )

        if not reviews:
            return {"local_ratio": 0.0, "local_count": 0, "total_count": 0, "classifications": {}}

        classifications = {}
        local_count = 0

        for review in reviews:
            if not review.author_id_hashed:
                continue
            profile = self.profiler.profile_reviewer(review.author_id_hashed, db)
            reviewer_type = self.profiler.classify_reviewer(profile)
            classifications[reviewer_type] = classifications.get(reviewer_type, 0) + 1
            if reviewer_type == "local_regular":
                local_count += 1

        total = len(reviews)
        local_ratio = local_count / total if total > 0 else 0.0

        return {
            "local_ratio": round(local_ratio, 3),
            "local_count": local_count,
            "total_count": total,
            "classifications": classifications,
        }


reviewer_profiler = ReviewerProfiler()
local_ratio_calculator = LocalRatioCalculator(reviewer_profiler)
