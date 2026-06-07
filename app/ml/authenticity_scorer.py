import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

MODEL_ID = "microsoft/Phi-3-mini-4k-instruct"
PR_KEYWORDS = [
    "quảng cáo", "tài trợ", "sponsored", "ad", "advertisement",
    "#ad", "#sponsored", "#gifted", "#ambassador", "#kol", "#pr",
    "invited", "free meal", "complimentary", "comped",
    "best restaurant ever", "must visit", "hidden gem",
    "absolutely amazing", "highly recommend",
]
EXCESSIVE_PUNCTUATION = re.compile(r"[!]{3,}|[.]{4,}|[\?]{3,}")
BURST_CAPITALIZATION = re.compile(r"\b[A-Z]{4,}\b")
SPONSORED_PATTERNS = re.compile(
    r"\b(sponsor|tài trợ|ad|quảng cáo|paid|trả tiền|hợp tác)\b",
    re.IGNORECASE,
)
LINK_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)


@dataclass
class AuthenticityResult:
    authenticity_score: float
    confidence: float
    classification: str
    flagged_keywords: list[str]
    model_version: str


class AuthenticityScorer:
    def __init__(self, model_id: str = MODEL_ID, device: str = "cpu"):
        self.model_id = model_id
        self.device = device or settings.model_device
        self._pipeline = None
        self._tokenizer = None
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
        logger.info("AuthenticityScorer using heuristic mode (fast CPU path)")

    def _load_transformers(self):
        try:
            from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
            import torch
            logger.info("Loading Phi-3-mini for authenticity scoring...")
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_id, cache_dir=settings.model_cache_dir, trust_remote_code=True
            )
            model_kwargs = {}
            if self.device == "cuda":
                model_kwargs["device_map"] = "auto"
                model_kwargs["torch_dtype"] = torch.float16
            self._pipeline = pipeline(
                "text-generation",
                model=self.model_id,
                tokenizer=self._tokenizer,
                device=self.device if self.device == "cuda" else -1,
                model_kwargs=model_kwargs,
            )
            logger.info("Phi-3-mini loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load Phi-3-mini: {e}. Falling back to heuristic.")
            self._load_heuristic()

    def score_batch(self, texts: list[str], batch_size: int = 32) -> list[AuthenticityResult]:
        results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            results.extend([self._score_single(t) for t in batch])
        return results

    def _score_single(self, text: str) -> AuthenticityResult:
        if not text or not text.strip():
            return AuthenticityResult(
                authenticity_score=0.5, confidence=0.0,
                classification="unknown", flagged_keywords=[],
                model_version=self.model_id,
            )

        if self._pipeline is not None and self._tokenizer is not None:
            return self._score_with_model(text)
        return self._score_heuristic(text)

    def _score_with_model(self, text: str) -> AuthenticityResult:
        try:
            prompt = f"""<|user|>
Classify this restaurant review as ORGANIC (written by a genuine local diner) or PROMOTIONAL (written for money or business promotion). Reply with one word only.

Review: {text[:500]}

Classification: <|assistant|>"""
            output = self._pipeline(
                prompt, max_new_tokens=4, temperature=0.1, do_sample=False
            )
            generated = output[0]["generated_text"].split("<|assistant|>")[-1].strip().upper()
            if "PROMOTIONAL" in generated:
                return AuthenticityResult(
                    authenticity_score=0.1, confidence=0.85,
                    classification="promotional", flagged_keywords=[],
                    model_version=self.model_id,
                )
            return AuthenticityResult(
                authenticity_score=0.85, confidence=0.85,
                classification="organic", flagged_keywords=[],
                model_version=self.model_id,
            )
        except Exception as e:
            logger.warning(f"Model inference failed: {e}, falling back to heuristic")
            return self._score_heuristic(text)

    def _score_heuristic(self, text: str) -> AuthenticityResult:
        text_lower = text.lower()
        flags = []
        pr_signal = 0.0

        sponsored_matches = SPONSORED_PATTERNS.findall(text_lower)
        if sponsored_matches:
            flags.extend(sponsored_matches)
            pr_signal += 0.3 * len(sponsored_matches)

        pr_kw_found = [kw for kw in PR_KEYWORDS if kw in text_lower]
        if pr_kw_found:
            flags.extend(pr_kw_found)
            pr_signal += 0.15 * len(pr_kw_found)

        if EXCESSIVE_PUNCTUATION.search(text):
            pr_signal += 0.1
            flags.append("excessive_punctuation")

        caps = BURST_CAPITALIZATION.findall(text)
        if caps:
            pr_signal += 0.1
            flags.extend(caps)

        link_count = len(LINK_PATTERN.findall(text))
        if link_count > 2:
            pr_signal += 0.1
            flags.append(f"{link_count}_links")

        has_price = bool(re.search(r"\b\d{1,3}(,\d{3})*k\b|\b\d{1,3}(,\d{3})*K\b|\$\d+", text))
        has_dish = bool(re.search(r"\b(phở|bánh|bún|cơm|cháo|gỏi|nem|chả|canh)\b", text_lower))
        has_location = bool(re.search(r"\b(đường|phố|quận|district|street|ngõ|hẻm)\b", text_lower))
        organic_signals = sum([has_price, has_dish, has_location])
        pr_signal -= 0.1 * organic_signals

        pr_signal = max(0.0, min(1.0, pr_signal))
        auth_score = 1.0 - pr_signal

        confidence = 0.7 + (0.1 * len(flags))
        confidence = min(confidence, 0.95)

        classification = "promotional" if auth_score < 0.4 else "organic"

        return AuthenticityResult(
            authenticity_score=round(auth_score, 3),
            confidence=round(confidence, 3),
            classification=classification,
            flagged_keywords=flags[:10],
            model_version=f"{self.model_id}-heuristic",
        )
