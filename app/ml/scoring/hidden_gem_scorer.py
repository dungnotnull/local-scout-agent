import math
from dataclasses import dataclass


@dataclass
class GemScoreComponents:
    authenticity_score_avg: float
    local_ratio: float
    checkin_count: int
    marketing_signal: float


class HiddenGemScorer:
    def compute(self, components: GemScoreComponents) -> float:
        auth = components.authenticity_score_avg
        local_ratio = components.local_ratio
        checkin = math.log(components.checkin_count + 1)
        marketing = max(components.marketing_signal, 0.01)

        raw = auth * local_ratio * checkin * (1.0 / marketing)
        return min(max(raw * 100, 0), 100)

    def compute_for_restaurant(self, reviews_data: list[dict], metadata: dict) -> float:
        if not reviews_data:
            return 0.0

        auth_scores = [r.get("authenticity_score", 0.5) for r in reviews_data]
        auth_avg = sum(auth_scores) / len(auth_scores)

        local_ratio = metadata.get("local_ratio", 0.3)
        checkin_count = metadata.get("checkin_count", 0)
        marketing_signal = metadata.get("marketing_signal", 1.0)

        return self.compute(GemScoreComponents(
            authenticity_score_avg=auth_avg,
            local_ratio=local_ratio,
            checkin_count=checkin_count,
            marketing_signal=marketing_signal,
        ))
