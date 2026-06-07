import logging
import re
from dataclasses import dataclass
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

MODEL_ID = "cardiffnlp/twitter-xlm-roberta-base-sentiment-multilingual"

POSITIVE_WORDS_VI = [
    "ngon", "tuyệt", "xuất sắc", "đỉnh", "thích", "tuyệt vời", "hài lòng",
    "ăn hoài", "quay lại", "ghiền", "nghiện", "best", "delicious", "yummy",
]
NEGATIVE_WORDS_VI = [
    "dở", "tệ", "thất vọng", "chán", "không ngon", "mắc", "đắt", "lâu",
    "không đáng", "poor", "bad", "terrible", "overrated", "tourist trap",
]
NEGATION_PATTERNS_VI = re.compile(r"\b(không|chẳng|chưa|đừng|chả)\s+(\w+)", re.IGNORECASE)
NEGATION_PATTERNS_EN = re.compile(r"\b(not|no|never|hardly)\s+(\w+)", re.IGNORECASE)


@dataclass
class SentimentResult:
    sentiment: float
    language_code: str


class SentimentAnalyzer:
    def __init__(self, model_id: str = MODEL_ID, device: str = "cpu"):
        self.model_id = model_id
        self.device = device or settings.model_device
        self._pipeline = None
        self._loaded = False

    def load(self):
        if self._loaded:
            return
        if settings.model_quantization in ("int8", "onnx"):
            self._load_heuristic()
        else:
            self._load_transformers()
        self._loaded = True

    def _load_heuristic(self):
        logger.info("SentimentAnalyzer using heuristic mode (fast CPU path)")

    def _load_transformers(self):
        try:
            from transformers import pipeline
            logger.info("Loading XLM-RoBERTa sentiment model...")
            self._pipeline = pipeline(
                "sentiment-analysis",
                model=self.model_id,
                tokenizer=self.model_id,
                device=-1,
                top_k=None,
            )
            logger.info("XLM-RoBERTa sentiment model loaded")
        except Exception as e:
            logger.warning(f"Could not load sentiment model: {e}. Falling back to heuristic.")
            self._load_heuristic()

    def analyze(self, text: str, language: str = None) -> SentimentResult:
        if not text or not text.strip():
            return SentimentResult(sentiment=0.0, language_code=language or "unknown")

        lang = language or self._detect_language(text)
        if self._pipeline is not None:
            return self._analyze_with_model(text, lang)
        return self._analyze_heuristic(text, lang)

    def analyze_batch(self, texts: list[str]) -> list[SentimentResult]:
        return [self.analyze(t) for t in texts]

    def _analyze_with_model(self, text: str, language: str) -> SentimentResult:
        try:
            results = self._pipeline(text[:512], truncation=True)
            if isinstance(results, list) and results:
                scores = results[0] if isinstance(results[0], list) else results
                label_map = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}
                weighted = 0.0
                total = 0.0
                for item in scores:
                    lbl = item.get("label", "").lower()
                    score = item.get("score", 0.0)
                    mapped = label_map.get(lbl, 0.0)
                    weighted += mapped * score
                    total += score
                sentiment = weighted / total if total > 0 else 0.0
                return SentimentResult(sentiment=round(sentiment, 3), language_code=language)
        except Exception as e:
            logger.warning(f"Model sentiment failed: {e}")
        return self._analyze_heuristic(text, language)

    def _analyze_heuristic(self, text: str, language: str) -> SentimentResult:
        text_lower = text.lower()
        if "vi" in language:
            pos = [w for w in POSITIVE_WORDS_VI if w in text_lower]
            neg = [w for w in NEGATIVE_WORDS_VI if w in text_lower]
        else:
            pos = [w for w in POSITIVE_WORDS_VI if w in text_lower]
            neg = [w for w in NEGATIVE_WORDS_VI if w in text_lower]

        pos_count = len(pos)
        neg_count = len(neg)
        negations = NEGATION_PATTERNS_VI.findall(text_lower) + NEGATION_PATTERNS_EN.findall(text_lower)
        if negations:
            pos_count, neg_count = neg_count, pos_count

        total = pos_count + neg_count
        if total == 0:
            sentiment = 0.0
        else:
            sentiment = (pos_count - neg_count) / total
        return SentimentResult(sentiment=round(sentiment, 3), language_code=language)

    def _detect_language(self, text: str) -> str:
        if not text.strip():
            return "unknown"
        vi_chars = len(re.findall(r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]', text.lower()))
        if vi_chars > 2:
            return "vi"
        return "en"
