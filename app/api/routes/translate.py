import io
import logging
import re
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class TranslateTextRequest(BaseModel):
    text: str
    source_lang: Optional[str] = None
    target_lang: str = "en"


class MenuItem(BaseModel):
    original: str
    translated: str
    cultural_note: Optional[str] = None
    price: Optional[str] = None
    allergens: list[str] = []


class TranslateResponse(BaseModel):
    original_text: str
    translated_text: str
    source_lang_detected: str
    cultural_notes: list[str] = []
    menu_items: list[MenuItem] = []
    is_image: bool = False


NLLB_LANG_MAP = {
    "vi": "vie_Latn",
    "en": "eng_Latn",
    "th": "tha_Thai",
    "zh": "zho_Hans",
    "ko": "kor_Hang",
    "ja": "jpn_Jpan",
    "fr": "fra_Latn",
    "de": "deu_Latn",
}

FOOD_SECTIONS = re.compile(
    r'(?:món\s+khai\s+vị|appetizer|starter|entrée)|'
    r'(?:món\s+chính|main|entree|plat)|'
    r'(?:tráng\s+miệng|dessert|sweet)|'
    r'(?:đồ\s+uống|drink|beverage|nước)',
    re.IGNORECASE,
)

DISH_PATTERN = re.compile(
    r'(.{3,80}?)\s*[-–—]\s*(.{0,40}?)\s*'
    r'(\d{1,3}(?:[,.]\d{3})*\s*(?:k|K|đ|VND|vnd|vnđ|USD|$))?\s*$',
    re.MULTILINE,
)

COMMON_ALLERGENS = {
    "tôm": "shellfish", "cua": "shellfish", "mực": "shellfish",
    "hải sản": "shellfish", "seafood": "shellfish",
    "trứng": "eggs", "egg": "eggs",
    "sữa": "dairy", "milk": "dairy", "bơ": "dairy", "cheese": "dairy",
    "đậu phộng": "peanuts", "peanut": "peanuts", "lạc": "peanuts",
    "đậu nành": "soy", "soy": "soy",
    "lúa mì": "wheat", "wheat": "wheat", "bột mì": "wheat",
    "cá": "fish", "fish": "fish",
    "hạt": "tree nuts", "nuts": "tree nuts",
}


@router.post("/translate-menu", response_model=TranslateResponse)
def translate_menu_text(request: TranslateTextRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text is required")

    source_lang = request.source_lang or detect_language(request.text)
    translated = local_translate(request.text, source_lang, request.target_lang)
    cultural_notes = generate_cultural_notes(request.text, source_lang)
    menu_items = parse_menu_items(request.text, translated)

    return TranslateResponse(
        original_text=request.text,
        translated_text=translated,
        source_lang_detected=source_lang,
        cultural_notes=cultural_notes,
        menu_items=menu_items,
        is_image=False,
    )


@router.post("/translate-menu/image", response_model=TranslateResponse)
async def translate_menu_image(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are accepted")

    contents = await file.read()
    try:
        image = Image.open(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=400, detail="Cannot read image file")

    ocr_text = perform_ocr(image)
    if not ocr_text.strip():
        raise HTTPException(status_code=400, detail="No text detected in image")

    source_lang = detect_language(ocr_text)
    translated = local_translate(ocr_text, source_lang, "en")
    cultural_notes = generate_cultural_notes(ocr_text, source_lang)
    menu_items = parse_menu_items(ocr_text, translated)

    return TranslateResponse(
        original_text=ocr_text,
        translated_text=translated,
        source_lang_detected=source_lang,
        cultural_notes=cultural_notes,
        menu_items=menu_items,
        is_image=True,
    )


def detect_language(text: str) -> str:
    if not text.strip():
        return "unknown"
    vi_chars = len(re.findall(r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]', text.lower()))
    if vi_chars > 2:
        return "vi"
    th_chars = len(re.findall(r'[ก-๙]', text))
    if th_chars > 5:
        return "th"
    zh_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    if zh_chars > 10:
        return "zh"
    return "en"


def perform_ocr(image: Image.Image) -> str:
    try:
        import easyocr
        reader = easyocr.Reader(["vi", "en"], gpu=False)
        results = reader.readtext(image, detail=0)
        return "\n".join(results)
    except ImportError:
        logger.warning("EasyOCR not available")
        return ""


def local_translate(text: str, source_lang: str, target_lang: str) -> str:
    src_code = NLLB_LANG_MAP.get(source_lang, "eng_Latn")
    tgt_code = NLLB_LANG_MAP.get(target_lang, "eng_Latn")
    if src_code == tgt_code:
        return text

    try:
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
        import torch
        model_id = "facebook/nllb-200-distilled-600M"
        tokenizer = AutoTokenizer.from_pretrained(model_id, cache_dir=settings.model_cache_dir)
        model = AutoModelForSeq2SeqLM.from_pretrained(model_id, cache_dir=settings.model_cache_dir)
        tokenizer.src_lang = src_code
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        translated_tokens = model.generate(
            **inputs, forced_bos_token_id=tokenizer.lang_code_to_id[tgt_code], max_length=512
        )
        return tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0]
    except ImportError:
        return text
    except Exception as e:
        logger.warning(f"NLLB translation failed: {e}")
        return text


def generate_cultural_notes(text: str, source_lang: str) -> list[str]:
    notes = []
    text_lower = text.lower()

    cultural_keywords = {
        "phở": "Phở is Vietnam's national dish. The broth is simmered for hours with beef bones, star anise, and cinnamon.",
        "bún bò": "Bún bò Huế originates from Huế, central Vietnam. It features a spicy lemongrass beef broth with thick rice noodles.",
        "cơm tấm": "Cơm tấm (broken rice) is a Saigon specialty originally eaten by poor farmers using fractured rice grains.",
        "bánh mì": "Bánh mì reflects Vietnam's French colonial history, combining French baguette with Vietnamese fillings.",
        "gỏi cuốn": "Gỏi cuốn (spring rolls) are fresh, not fried — a staple of southern Vietnamese cuisine.",
        "chả cá": "Chả cá Lã Vọng is a Hà Nội specialty of grilled fish with turmeric and dill, cooked tableside.",
    }

    for keyword, note in cultural_keywords.items():
        if keyword in text_lower and note not in notes:
            notes.append(note)

    return notes


def parse_menu_items(text: str, translated: str) -> list[MenuItem]:
    items = []
    lines = text.split("\n")
    translated_lines = translated.split("\n") if translated else []

    for i, line in enumerate(lines):
        line = line.strip()
        if not line or len(line) < 3:
            continue
        price_match = re.search(r'(\d{1,3}(?:[,.]\d{3})*\s*(?:k|K|đ|VND|vnd|vnđ|USD|\$))', line)
        price = price_match.group(1) if price_match else None
        translated_line = translated_lines[i] if i < len(translated_lines) else ""
        allergens = [v for k, v in COMMON_ALLERGENS.items() if k in line.lower()]
        items.append(MenuItem(
            original=line[:100],
            translated=translated_line[:100] if translated_line else "",
            price=price,
            allergens=list(set(allergens)),
        ))
        if len(items) >= 30:
            break

    return items
