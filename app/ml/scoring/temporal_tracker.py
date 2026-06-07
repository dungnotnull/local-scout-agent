import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.models import Restaurant, Review, AuthenticityScore

logger = logging.getLogger(__name__)


@dataclass
class QualityDriftReport:
    restaurant_id: int
    current_score: float
    recent_90d_avg: Optional[float] = None
    prior_90d_avg: Optional[float] = None
    drift_magnitude: float = 0.0
    alert_level: str = "normal"
    recommendations: list[str] = field(default_factory=list)
    review_count_recent: int = 0
    review_count_prior: int = 0


class TemporalQualityTracker:
    def __init__(self):
        self.drift_threshold_small = 0.10
        self.drift_threshold_large = 0.25

    def analyze_restaurant(self, restaurant_id: int, db: Session) -> QualityDriftReport:
        restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
        current_score = restaurant.gem_score if restaurant and restaurant.gem_score else 50.0

        now = datetime.now(timezone.utc)
        recent_cutoff = now - timedelta(days=90)
        prior_cutoff = now - timedelta(days=360)

        recent_scores = (
            db.query(AuthenticityScore.authenticity_score)
            .join(Review, AuthenticityScore.review_id == Review.id)
            .filter(
                Review.restaurant_id == restaurant_id,
                AuthenticityScore.computed_at >= recent_cutoff,
            )
            .all()
        )

        prior_scores = (
            db.query(AuthenticityScore.authenticity_score)
            .join(Review, AuthenticityScore.review_id == Review.id)
            .filter(
                Review.restaurant_id == restaurant_id,
                AuthenticityScore.computed_at.between(prior_cutoff, recent_cutoff),
            )
            .all()
        )

        report = QualityDriftReport(
            restaurant_id=restaurant_id,
            current_score=round(current_score, 2),
        )

        if recent_scores:
            vals = [s[0] for s in recent_scores if s[0] is not None]
            report.recent_90d_avg = sum(vals) / len(vals) if vals else None
            report.review_count_recent = len(vals)

        if prior_scores:
            vals = [s[0] for s in prior_scores if s[0] is not None]
            report.prior_90d_avg = sum(vals) / len(vals) if vals else None
            report.review_count_prior = len(vals)

        if report.recent_90d_avg is not None and report.prior_90d_avg is not None:
            report.drift_magnitude = report.recent_90d_avg - report.prior_90d_avg

        report.alert_level, report.recommendations = self._assess_drift(report)
        return report

    def _assess_drift(self, report: QualityDriftReport) -> tuple[str, list[str]]:
        recs = []

        if report.drift_magnitude < -self.drift_threshold_large:
            alert = "critical_decline"
            recs.append("Authenticity scores have dropped significantly in the last 90 days.")
            recs.append("Consider re-crawling area for updated data.")
        elif report.drift_magnitude < -self.drift_threshold_small:
            alert = "warning_decline"
            recs.append("Slight authenticity decline detected. Monitor more frequently.")
        elif report.drift_magnitude > self.drift_threshold_large:
            alert = "suspicious_spike"
            recs.append("Unusual spike in authenticity scores — possible review manipulation.")
            recs.append("Investigate recent 5-star review patterns.")
        elif report.drift_magnitude > self.drift_threshold_small:
            alert = "positive_improvement"
            recs.append("Restaurant quality appears to be improving based on recent reviews.")
        else:
            alert = "normal"

        if report.review_count_recent < 3:
            recs.append("Not enough recent reviews for reliable drift analysis.")

        return alert, recs

    def analyze_batch(self, restaurant_ids: list[int], db: Session) -> list[QualityDriftReport]:
        return [self.analyze_restaurant(rid, db) for rid in restaurant_ids]

    def mark_restaurant_quality_flags(self, restaurant_id: int, db: Session):
        report = self.analyze_restaurant(restaurant_id, db)
        restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
        if restaurant:
            import json
            trigger_alerts = {
                "alert_level": report.alert_level,
                "drift_magnitude": report.drift_magnitude,
                "recent_90d_avg": report.recent_90d_avg,
                "prior_90d_avg": report.prior_90d_avg,
                "recommendations": report.recommendations,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            existing = {}
            if restaurant.gem_score_components:
                try:
                    existing = json.loads(restaurant.gem_score_components)
                except (json.JSONDecodeError, TypeError):
                    pass
            existing["quality_drift"] = trigger_alerts
            restaurant.gem_score_components = json.dumps(existing, ensure_ascii=False)
            db.commit()


temporal_quality_tracker = TemporalQualityTracker()
