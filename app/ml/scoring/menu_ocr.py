import io
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import httpx
from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)

NLLB_MODEL_ID = "facebook/nllb-200-distilled-600M"

NLLB_LANG_MAP = {
    "vi": ("vie_Latn", "Vietnamese"),
    "en": ("eng_Latn", "English"),
    "th": ("tha_Thai", "Thai"),
    "zh": ("zho_Hans", "Chinese (Simplified)"),
    "ko": ("kor_Hang", "Korean"),
    "ja": ("jpn_Jpan", "Japanese"),
    "fr": ("fra_Latn", "French"),
    "de": ("deu_Latn", "German"),
    "id": ("ind_Latn", "Indonesian"),
    "km": ("khm_Khmr", "Khmer"),
    "lo": ("lao_Laoo", "Lao"),
    "my": ("mya_Mymr", "Burmese"),
}

MENU_SECTION_KEYWORDS = {
    "appetizers": ["khai vị", "appetizer", "starter", "entrée", "mon khai vi"],
    "mains": ["món chính", "main course", "main dish", "entree", "mon chinh", "đặc biệt", "special"],
    "soups": ["súp", "soup", "canh", "cháo", "porridge"],
    "noodles": ["phở", "bún", "mì", "hủ tiếu", "bánh canh", "noodle", "pho"],
    "rice": ["cơm", "rice", "com"],
    "drinks": ["nước", "drink", "beverage", "coffee", "cà phê", "trà", "tea", "sinh tố", "smoothie"],
    "desserts": ["tráng miệng", "dessert", "chè", "sweet", "kem", "ice cream"],
}


@dataclass
class MenuSection:
    name: str
    items: list[str] = field(default_factory=list)


@dataclass
class MenuItem:
    name_original: str
    name_translated: str
    price: Optional[str] = None
    description: Optional[str] = None
    allergens: list[str] = field(default_factory=list)
    is_popular: bool = False


@dataclass
class ParsedMenu:
    sections: list[MenuSection] = field(default_factory=list)
    language: str = "unknown"
    raw_text: str = ""


class MenuOCRPipeline:
    def __init__(self):
        self._ocr_reader = None
        self._nllb_tokenizer = None
        self._nllb_model = None

    def load_ocr(self):
        if self._ocr_reader is not None:
            return
        try:
            import easyocr
            self._ocr_reader = easyocr.Reader(["vi", "en", "th"], gpu=False)
            logger.info("EasyOCR reader loaded")
        except ImportError:
            logger.warning("EasyOCR not available — menu photo OCR disabled")
        except Exception as e:
            logger.warning(f"EasyOCR init failed: {e}")

    def load_nllb(self):
        if self._nllb_model is not None:
            return
        try:
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
            self._nllb_tokenizer = AutoTokenizer.from_pretrained(
                NLLB_MODEL_ID, cache_dir=settings.model_cache_dir
            )
            self._nllb_model = AutoModelForSeq2SeqLM.from_pretrained(
                NLLB_MODEL_ID, cache_dir=settings.model_cache_dir
            )
            logger.info("NLLB-200 translation model loaded")
        except Exception as e:
            logger.warning(f"NLLB-200 loading failed: {e}")

    def extract_text(self, image: Image.Image) -> str:
        self.load_ocr()
        if self._ocr_reader is None:
            return ""
        try:
            results = self._ocr_reader.readtext(image, detail=0)
            return "\n".join(results)
        except Exception as e:
            logger.warning(f"OCR failed: {e}")
            return ""

    def detect_language(self, text: str) -> str:
        if not text.strip():
            return "unknown"
        vi_chars = len(re.findall(
            r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]',
            text.lower(),
        ))
        if vi_chars > 2:
            return "vi"
        th_chars = len(re.findall(r'[ก-๙]', text))
        if th_chars > 5:
            return "th"
        return "en"

    def parse_sections(self, text: str) -> list[MenuSection]:
        sections = []
        current_section = MenuSection(name="Other")

        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue

            matched_section = None
            for section_name, keywords in MENU_SECTION_KEYWORDS.items():
                if any(kw in line.lower() for kw in keywords):
                    matched_section = section_name
                    break

            if matched_section:
                if current_section.items:
                    sections.append(current_section)
                current_section = MenuSection(name=matched_section)
            else:
                current_section.items.append(line)

        if current_section.items:
            sections.append(current_section)
        return sections

    def translate(self, text: str, source_lang: str, target_lang: str = "en") -> str:
        if source_lang == target_lang:
            return text

        src_code = NLLB_LANG_MAP.get(source_lang, ("eng_Latn",))[0]
        tgt_code = NLLB_LANG_MAP.get(target_lang, ("eng_Latn",))[0]

        self.load_nllb()

        if self._nllb_model is None or self._nllb_tokenizer is None:
            return text

        try:
            self._nllb_tokenizer.src_lang = src_code
            inputs = self._nllb_tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            translated = self._nllb_model.generate(
                **inputs,
                forced_bos_token_id=self._nllb_tokenizer.lang_code_to_id[tgt_code],
                max_length=512,
            )
            return self._nllb_tokenizer.batch_decode(translated, skip_special_tokens=True)[0]
        except Exception as e:
            logger.warning(f"Translation failed: {e}")
            return text

    def translate_menu(self, text: str, source_lang: str, target_lang: str = "en") -> str:
        return self.translate(text, source_lang, target_lang)

    @staticmethod
    def detect_allergens(text: str) -> list[str]:
        found = []
        allergen_map = {
            "shellfish": ["tôm", "cua", "mực", "hải sản", "seafood", "shrimp", "crab", "squid"],
            "eggs": ["trứng", "egg"],
            "dairy": ["sữa", "bơ", "phô mai", "cheese", "milk", "cream", "butter"],
            "peanuts": ["đậu phộng", "lạc", "peanut"],
            "soy": ["đậu nành", "tàu hũ", "đậu hũ", "soy", "tofu"],
            "wheat": ["lúa mì", "bột mì", "wheat", "flour"],
            "fish": ["cá", "fish"],
            "tree_nuts": ["hạt điều", "hạnh nhân", "óc chó", "cashew", "almond", "walnut"],
            "sesame": ["mè", "vừng", "sesame"],
        }
        text_lower = text.lower()
        for allergen, keywords in allergen_map.items():
            if any(kw in text_lower for kw in keywords):
                found.append(allergen)
        return list(set(found))


menu_ocr_pipeline = MenuOCRPipeline()
