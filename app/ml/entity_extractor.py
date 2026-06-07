import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

MODEL_ID = "dslim/bert-base-NER"

DISH_KEYWORDS_VI = [
    "phở", "bánh mì", "bún", "cơm", "cháo", "gỏi", "nem", "chả giò",
    "bò kho", "bánh xèo", "bánh cuốn", "bánh bột lộc", "bún bò", "cơm tấm",
    "hủ tiếu", "bánh canh", "mì quảng", "cao lầu", "bún chả", "bánh khọt",
    "bánh tráng", "chè", "ốc", "hải sản", "lẩu", "bò né", "bò bít tết",
    "gà", "vịt", "heo", "bò", "tôm", "cua", "cá", "mực",
]
ADDRESS_PATTERNS_VI = re.compile(
    r'\b(\d+[A-Za-z]?\s+(đường|phố|street|st)\s+\w+)'
    r'|\b(quận\s+\d+|district\s+\d+)'
    r'|\b(phường\s+\d+|ward\s+\d+)'
    r'|\b(hẻm|ngõ|alley)\s+\d+'
    r'|\b(\d+/\d+/\d+)\b',
    re.IGNORECASE,
)
NEIGHBORHOOD_PATTERNS = re.compile(
    r'\b(D\.\s*\d+|District\s+\d+|Quận\s+\d+|Bình\s+(?:Thạnh|Tân|Chánh)|'
    r'Tân\s+(?:Bình|Phú|Định)|Phú\s+(?:Nhuận|Mỹ Hưng)|Thủ\s+Đức|'
    r'Gò\s+Vấp|Nhà\s+Bè|Bình\s+Tân|Hóc\s+Môn|Củ\s+Chi|Cần\s+Giờ)\b',
    re.IGNORECASE,
)


@dataclass
class ExtractedEntity:
    text: str
    entity_type: str
    start: int
    end: int
    confidence: float


@dataclass
class ExtractionResult:
    restaurant_names: list[str] = field(default_factory=list)
    dish_names: list[str] = field(default_factory=list)
    addresses: list[str] = field(default_factory=list)
    neighborhoods: list[str] = field(default_factory=list)
    raw_entities: list[ExtractedEntity] = field(default_factory=list)


class EntityExtractor:
    def __init__(self, model_id: str = MODEL_ID, device: str = "cpu"):
        self.model_id = model_id
        self.device = device or settings.model_device
        self._pipeline = None
        self._loaded = False

    def load(self):
        if self._loaded:
            return
        try:
            from transformers import pipeline
            logger.info("Loading BERT-NER model...")
            self._pipeline = pipeline(
                "ner",
                model=self.model_id,
                tokenizer=self.model_id,
                device=-1,
                aggregation_strategy="simple",
            )
            logger.info("BERT-NER loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load NER model: {e}. Using rule-based extraction.")
        self._loaded = True

    def extract(self, text: str) -> ExtractionResult:
        if not text or not text.strip():
            return ExtractionResult()

        result = ExtractionResult()

        if self._pipeline is not None:
            self._extract_with_model(text, result)

        self._extract_dishes_rules(text, result)
        self._extract_addresses_rules(text, result)
        self._extract_neighborhoods_rules(text, result)
        self._extract_restaurant_names_rules(text, result)

        result.dish_names = list(dict.fromkeys(result.dish_names))
        result.addresses = list(dict.fromkeys(result.addresses))
        result.neighborhoods = list(dict.fromkeys(result.neighborhoods))
        result.restaurant_names = list(dict.fromkeys(result.restaurant_names))
        return result

    def extract_batch(self, texts: list[str]) -> list[ExtractionResult]:
        return [self.extract(t) for t in texts]

    def _extract_with_model(self, text: str, result: ExtractionResult):
        try:
            entities = self._pipeline(text[:512])
            for entity in entities:
                ent = ExtractedEntity(
                    text=entity.get("word", ""),
                    entity_type=entity.get("entity_group", entity.get("entity", "MISC")),
                    start=entity.get("start", 0),
                    end=entity.get("end", 0),
                    confidence=round(entity.get("score", 0.0), 3),
                )
                result.raw_entities.append(ent)
                ent_type = ent.entity_type.upper()
                if ent_type in ("ORG", "LOC", "FAC", "GPE"):
                    if any(kw in ent.text.lower() for kw in ["nhà hàng", "quán", "restaurant", "eatery"]):
                        result.restaurant_names.append(ent.text)
                    elif re.search(r'\d+\s+\w+', ent.text):
                        result.addresses.append(ent.text)
                elif ent_type == "PER":
                    pass
        except Exception as e:
            logger.warning(f"NER model error: {e}")

    def _extract_dishes_rules(self, text: str, result: ExtractionResult):
        text_lower = text.lower()
        for dish in DISH_KEYWORDS_VI:
            if dish in text_lower:
                result.dish_names.append(dish)

    def _extract_addresses_rules(self, text: str, result: ExtractionResult):
        matches = ADDRESS_PATTERNS_VI.findall(text)
        for match in matches:
            addr = match[0] or match[1] or match[2] or match[3] or match[4]
            if addr and len(addr) > 3:
                result.addresses.append(addr.strip())

    def _extract_neighborhoods_rules(self, text: str, result: ExtractionResult):
        matches = NEIGHBORHOOD_PATTERNS.findall(text)
        result.neighborhoods.extend([m.strip() for m in matches if m.strip()])

    def _extract_restaurant_names_rules(self, text: str, result: ExtractionResult):
        patterns = [
            r'(?:quán|nhà hàng|tiệm|restaurant|quán ăn)\s+["\']?([A-ZÀ-Ỹ][\w\sÀ-Ỹà-ỹ-]{2,40})["\']?',
            r'\b([A-Z][\w\s]{3,30})\s+(?:quán|restaurant)',
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                name = match.group(1).strip()
                if len(name) > 3 and not re.match(r'^[\d\s]+$', name):
                    result.restaurant_names.append(name)


async def geocode_address(address: str) -> Optional[tuple[float, float]]:
    if not settings.google_places_api_key:
        return None
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params={
                    "address": f"{address}, Ho Chi Minh City, Vietnam",
                    "key": settings.google_places_api_key,
                },
            )
            data = response.json()
            if data.get("results"):
                location = data["results"][0]["geometry"]["location"]
                return location["lat"], location["lng"]
    except Exception as e:
        logger.warning(f"Geocoding failed for '{address}': {e}")
    return None
