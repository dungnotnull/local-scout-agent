# PROJECT-detail.md — Local Scout Agent
## Comprehensive Technical Specification

---

## Executive Summary

Local Scout Agent is an AI-powered travel companion that helps tourists discover authentic, locally-beloved restaurants while actively filtering out tourist traps, paid placements, and KOL-sponsored fake reviews. The system employs Agentic RAG (Retrieval-Augmented Generation) powered by crawl4ai to harvest genuine reviews from local forums, Facebook groups, and personal blogs — sources that are rich in authentic signal but inaccessible to casual tourists due to language barriers and platform opacity. A local SLM-based authenticity scoring pipeline classifies each review's organic vs. promotional nature, and a hidden gem scoring formula surfaces the best matches on an interactive map. The system auto-translates local-language menus and provides AI-generated dish recommendations tailored to the user's profile and dietary constraints.

---

## Problem Statement

### The Tourist Trap Crisis
Tourism fraud through restaurant manipulation is a global and growing problem:
- **Fake review prevalence:** A 2023 Harvard Business School study estimated that 15–30% of online restaurant reviews on major platforms are inauthentic, with rates reaching 40%+ in high-traffic tourist destinations
- **KOL-driven distortion:** Micro and macro influencers routinely accept paid promotions without disclosure, flooding platforms like Instagram, TikTok, and Google Maps with misleading "organic" recommendations
- **Price gouging at tourist-facing restaurants:** A 2022 UNESCO report on heritage tourism found tourists routinely pay 2–5× the local price at "trap" establishments clustered near attractions
- **Language barrier exclusion:** The most authentic reviews exist in local-language forums (Vietnamese Foody groups, Thai Pantip forums, Indonesian Kaskus threads) that tourists cannot access or parse

### The Discovery Gap
Genuine local knowledge — the kind that tells you which street stall a grandmother has run for 40 years serving the best bun bo Hue in the city — lives in:
- Private Facebook groups with thousands of local members
- Reddit subreddits like r/VietNam, r/Bangkok, r/Bali
- Personal blogs from local food writers (not monetized, not SEO-optimized)
- Foursquare/Swarm check-in data with high local-to-tourist ratio
- Geocoded Instagram posts using hyper-local hashtags

This information is unstructured, multilingual, and algorithmically deprioritized by mainstream platforms that favor monetizable, high-engagement content.

---

## Target Users & Use Cases

### Primary Users
| User Type | Need | Pain Point |
|-----------|------|------------|
| Independent backpackers | Authentic cheap eats, local experience | Can't read local reviews, don't trust Google |
| Food tourism travelers | Hidden gem restaurants, authentic cuisine | Overwhelmed by fake reviews and KOL noise |
| Business travelers in new cities | Quick, trustworthy lunch/dinner options | No time to research, don't know local signals |
| Digital nomads (long-stay) | Build a local eating routine | Mainstream apps skew toward tourist-facing venues |
| Travel bloggers/writers | Discover genuinely undiscovered places | Need differentiated content beyond mainstream recommendations |

### Core Use Cases
1. **Area scout:** "I just arrived in District 3, Ho Chi Minh City — show me where locals actually eat"
2. **Dish search:** "Find me banh mi that's been reviewed by actual locals, not tourists"
3. **Budget filter:** "Hidden gems under 50,000 VND per person"
4. **Trust audit:** "Check if this restaurant I found on TripAdvisor has authentic reviews or is a tourist trap"
5. **Menu decoder:** "Translate this menu from Vietnamese and tell me what to order"

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LOCAL SCOUT AGENT                            │
│                                                                     │
│  ┌──────────────┐    ┌──────────────────┐    ┌────────────────────┐│
│  │  USER INPUT  │    │  CRAWLER LAYER   │    │  ML PIPELINE       ││
│  │              │    │                  │    │                    ││
│  │ • Location   │    │ crawl4ai         │    │ Authenticity       ││
│  │ • Query      │───▶│ • FB Groups      │───▶│ Classifier         ││
│  │ • Filters    │    │ • Reddit/Forums  │    │ (Phi-3-mini)       ││
│  │ • Diet prefs │    │ • Local blogs    │    │                    ││
│  └──────────────┘    │ • Foody.vn       │    │ Sentiment Analysis ││
│                      │ • Swarm/Foursq.  │    │ (XLM-RoBERTa)     ││
│                      └──────────────────┘    │                    ││
│                                              │ NER Extraction     ││
│                                              │ (BERT-NER)         ││
│                                              └────────────────────┘│
│                                                        │            │
│                      ┌─────────────────────────────────▼──────────┐│
│                      │           VECTOR STORE (ChromaDB)          ││
│                      │                                            ││
│                      │  Authentic reviews + metadata + scores     ││
│                      │  Multilingual embeddings (MiniLM)          ││
│                      └─────────────────────────────────────────── ┘│
│                                        │                            │
│             ┌──────────────────────────▼──────────────────────────┐│
│             │               SCORING ENGINE                         ││
│             │                                                      ││
│             │  Hidden Gem Score =                                  ││
│             │  (authenticity) × (local_ratio) ×                   ││
│             │  (checkin_frequency) × (1/marketing_prominence)      ││
│             └──────────────────────────────────────────────────── ┘│
│                                        │                            │
│     ┌──────────────────────────────────▼──────────────────────────┐│
│     │                    LLM LAYER (Pluggable)                     ││
│     │                                                              ││
│     │  Claude API ──▶ GPT-4o ──▶ Ollama/Llama3 (local fallback)  ││
│     │                                                              ││
│     │  • Menu translation (NLLB-200 local, Claude for nuance)     ││
│     │  • Dish recommendations                                      ││
│     │  • Restaurant summary generation                             ││
│     └──────────────────────────────────────────────────────────── ┘│
│                                        │                            │
│                      ┌─────────────────▼──────────────────────────┐│
│                      │            FRONTEND MAP UI                  ││
│                      │                                             ││
│                      │  React + Leaflet.js + Mapbox tiles          ││
│                      │  • Hidden gem markers (color-coded)         ││
│                      │  • Filter panel                             ││
│                      │  • Menu translation overlay                 ││
│                      │  • Review authenticity badges               ││
│                      └─────────────────────────────────────────── ┘│
└─────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Component | Technology | Source |
|-----------|-----------|--------|
| Backend API | FastAPI 0.111+ | PyPI |
| Frontend Map | React 18 + Leaflet.js 1.9 | npm |
| Map Tiles | Mapbox GL JS | Mapbox |
| Web Crawler | crawl4ai 0.4+ | PyPI / GitHub |
| Dynamic scraping | Playwright 1.44+ | PyPI |
| Vector Database | ChromaDB 0.5+ (dev), Qdrant (prod) | PyPI |
| Embeddings | sentence-transformers 3.0+ | PyPI / HuggingFace |
| Local SLM runtime | llama.cpp / transformers 4.41+ | PyPI |
| Menu translation | facebook/nllb-200-distilled-600M | HuggingFace |
| Sentiment analysis | cardiffnlp/twitter-xlm-roberta | HuggingFace |
| NER | dslim/bert-base-NER | HuggingFace |
| PR detection | Phi-3-mini-4k-instruct | HuggingFace |
| Geocoding | Google Places API | Google Cloud |
| Primary LLM | Claude API (claude-sonnet-4-6) | Anthropic |
| Fallback LLM | GPT-4o | OpenAI |
| Local LLM fallback | Ollama + Llama 3 8B | ollama.ai |
| Database | SQLite (dev), PostgreSQL (prod) | Built-in / OSS |
| Caching | Redis 7+ | OSS |
| Task queue | Celery + Redis | PyPI |
| Containerization | Docker + Docker Compose | Docker |
| Config management | python-dotenv + Pydantic Settings | PyPI |

---

## ML/DL Models Section

### 1. Authenticity Classifier (Core Innovation)
- **Base model:** `microsoft/Phi-3-mini-4k-instruct` (local SLM, 3.8B params, runs on CPU/GPU)
- **Task:** Binary classification — PR/sponsored content vs. organic local review
- **Fine-tuning plan:** Collect 5,000 labeled examples (labeled PR posts from known sponsored accounts, labeled organic posts from verified local accounts). Fine-tune with LoRA (rank=16, alpha=32) using PEFT library
- **Training data sources:**
  - Positive (organic): Archive of Foody.vn veteran user posts, r/Vietnam food threads from 2015–2020
  - Negative (PR): Disclosed sponsored posts on Facebook, posts with #ad #sponsored #gifted tags
- **Inference:** ONNX-quantized for CPU deployment, <200ms per post

### 2. Multilingual Sentiment Analysis
- **Model:** `cardiffnlp/twitter-xlm-roberta-base-sentiment-multilingual`
- **Task:** Positive/negative/neutral sentiment on restaurant reviews in Vietnamese, Thai, Indonesian, English, Chinese
- **No fine-tuning needed:** Model is already trained on social media multilingual content
- **Output:** Sentiment score used as one signal in authenticity scoring (genuine negative reviews are also authentic)

### 3. Named Entity Recognition
- **Model:** `dslim/bert-base-NER` + `flair/ner-multi` for multilingual NER
- **Task:** Extract restaurant names, dish names, street addresses, neighborhood names from unstructured text
- **Pipeline:** Text → NER → geocoding via Google Places → coordinates stored in SQLite

### 4. Semantic Embeddings (RAG)
- **Model:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- **Task:** Encode all scraped reviews into 384-dim vectors for semantic retrieval
- **Index:** HNSW index in ChromaDB for sub-50ms retrieval
- **Query expansion:** User query translated to local language before embedding to improve cross-lingual retrieval

### 5. Menu Translation
- **Primary (local):** `facebook/nllb-200-distilled-600M` — supports 200 languages, runs offline, 0 API cost
- **Secondary (cloud):** Claude API with structured output for nuanced dish descriptions and ordering tips
- **Pipeline:** OCR (Tesseract / EasyOCR for menu photos) → language detection → NLLB translation → Claude enrichment

---

## External LLM API Integration

### Pluggable LLM Backend Design
```python
class LLMBackend:
    def __init__(self, config: LLMConfig):
        self.chain = [
            ClaudeBackend(api_key=config.anthropic_key),
            GPT4Backend(api_key=config.openai_key),
            OllamaBackend(model="llama3:8b", base_url=config.ollama_url),
        ]

    async def complete(self, prompt: str, **kwargs) -> str:
        for backend in self.chain:
            try:
                return await backend.complete(prompt, **kwargs)
            except (APIError, RateLimitError, ConnectionError):
                continue
        raise AllBackendsExhaustedError()
```

### Claude API Usage
- **Menu translation with context:** Translate menu items with cultural context, explain ingredients, flag allergens
- **Dish recommendation:** Given user dietary preferences + local seasonal availability + authenticity-scored reviews, recommend 2–3 must-try dishes
- **Hidden gem summaries:** Generate 2–3 sentence summaries of why a restaurant is a hidden gem, citing specific authentic reviews
- **Trust audit reports:** Given a restaurant URL, analyze its review patterns and produce a trust score report

### Prompt Caching Strategy
- Cache system prompt (crawling context, local knowledge, scoring rubrics) with `cache_control: {"type": "ephemeral"}` to reduce Claude API costs by 60–80% on repeated queries

---

## Feature Specification

### MVP Features
- [ ] Location-based hidden gem restaurant discovery (radius search)
- [ ] Authenticity scoring for scraped reviews (PR vs. organic classifier)
- [ ] Hidden gem map with color-coded markers (green=highly authentic, yellow=mixed, red=tourist trap signals)
- [ ] Basic menu translation (NLLB-200 local model)
- [ ] Review source display (shows which forum/group the review came from)
- [ ] Filter by: cuisine type, price range, distance, authenticity score threshold
- [ ] Restaurant detail page: name, address, hours, hidden gem score, top authentic quotes
- [ ] Dish recommendation (Claude API, 2–3 must-try items per restaurant)
- [ ] CLI interface for power users / offline use

### Advanced Features
- [ ] Real-time crawl triggers (user arrives in new area → auto-crawl fires)
- [ ] Multi-language menu photo OCR + translation overlay (point camera at menu)
- [ ] Account history analyzer (determines if reviewer is local regular vs. one-time visitor)
- [ ] Trust audit tool (paste a TripAdvisor/Google Maps URL → get trust report)
- [ ] Seasonal dish alerts (local forums mentioning seasonal specialties this month)
- [ ] User-contributed authentic reviews (with cryptographic provenance for anti-gaming)
- [ ] Offline mode (pre-cached city data for top 50 tourist cities)
- [ ] Social sharing of hidden gems (with attribution to original authentic sources)
- [ ] Price comparison (tourist menu price vs. local menu price detection)
- [ ] Review timeline analysis (restaurant quality drift over time)

---

## Full E2E Data Flow

1. **User opens app** and grants location permission (session-only, never stored persistently)
2. **Location context** triggers `AreaScoutAgent.run(lat, lon, radius_km=2)`
3. **Crawler layer** checks cache freshness (TTL: 72 hours per area grid cell):
   - If stale or new area: `crawl4ai` spiders configured sources for this geographic cluster
   - Sources: Facebook groups matching area keywords, Reddit threads, Foody.vn area pages, local blog aggregator
   - Raw HTML/JSON stored in staging table with source URL, timestamp, geographic tag
4. **ML Pipeline** processes each raw document:
   - Language detection → multilingual embedding via MiniLM → stored in ChromaDB
   - NER extraction → restaurant entities → geocoded → stored in SQLite `restaurants` table
   - Authenticity classifier (Phi-3-mini) assigns 0–1 PR score; inverted to authenticity score
   - Sentiment analysis assigns polarity per review
5. **Hidden gem scoring** aggregates per restaurant:
   - `gem_score = auth_score_avg × local_ratio × log(checkin_count + 1) × (1 / marketing_signal)`
   - Score normalized to 0–100 for display
6. **Semantic retrieval** (if user typed a query): query embedded, nearest neighbors retrieved from ChromaDB, re-ranked by gem_score
7. **Map rendering:** Restaurant GeoJSON with gem scores sent to React frontend; Leaflet renders markers with color coding
8. **Detail view:** User clicks marker → FastAPI fetches restaurant details, top authentic review quotes, triggers Claude API for dish recommendations + summary
9. **Menu translation:** User photographs menu or pastes text → EasyOCR → NLLB-200 translation → Claude API enrichment → translated menu displayed as overlay
10. **Feedback loop:** User marks restaurant as "authentic" or "tourist trap" → feedback stored, used to recalibrate local scoring weights

---

## Privacy & Security

| Concern | Mitigation |
|---------|-----------|
| User location tracking | Location used only in-session, never stored to database or logs |
| Scraped PII (reviewer names) | Reviewer names hashed (SHA-256) before storage; display shows "Local reviewer #A3F2" |
| GDPR compliance | Data retention: 90 days for scraped content; user can request deletion via API |
| API key security | Keys loaded from environment variables only; never committed to repo |
| Scraping legality | Respect robots.txt; rate-limit crawlers to <1 req/sec per domain; only scrape publicly visible content |
| XSS in user-generated content | All restaurant/review text sanitized with bleach before rendering |
| SQL injection | All DB queries via SQLAlchemy ORM with parameterized queries |
| SSRF via user-submitted URLs | URL allowlist validation; no internal network access from crawler |

---

## Key Python Dependencies

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
crawl4ai==0.4.0
playwright==1.44.0
chromadb==0.5.0
sentence-transformers==3.0.0
transformers==4.41.0
torch==2.3.0
peft==0.11.0
onnxruntime==1.18.0
anthropic==0.28.0
openai==1.30.0
sqlalchemy==2.0.30
alembic==1.13.1
redis==5.0.4
celery==5.4.0
pydantic==2.7.1
pydantic-settings==2.2.1
python-dotenv==1.0.1
easyocr==1.7.1
pytesseract==0.3.10
bleach==6.1.0
geopy==2.4.1
shapely==2.0.4
geopandas==0.14.4
```

---

## Improvement Suggestions (Beyond Original Idea)

1. **Price intelligence layer:** Scrape menu prices from tourist-facing vs. local-facing sources for the same restaurant to automatically detect and flag pricing inconsistency (tourist trap signal)
2. **Temporal freshness decay:** Weight reviews from the past 6 months 3× higher than older reviews, since restaurant quality changes; alert users when a previously-authentic venue shows declining authenticity signals
3. **Crowd-sourced provenance chain:** Allow verified local residents (verified via phone number + check-in history) to submit and cryptographically sign reviews, creating a trusted-contributor network immune to coordinated fake review campaigns
4. **Local food event integration:** Crawl local Facebook events and community calendars to surface temporary food stalls, night markets, and seasonal pop-ups that never appear on mainstream platforms
5. **Dietary restriction cross-referencing:** Extract and index ingredient mentions from authentic reviews so users can find, e.g., "vegetarian pho that locals recommend" even if no official vegetarian tag exists
6. **Business owner deception detection:** Flag restaurants that have recently started buying followers, posting coordinated 5-star reviews, or using review-gating tactics (inviting only satisfied customers to review)
7. **Language-specific forum specialization:** Build domain-specific scrapers for high-signal sources per country — Pantip for Thailand, Kaskus for Indonesia, Naver Café for Korea — each requiring different parsing logic and authentication handling
8. **Offline city packs:** Pre-compute and package hidden gem databases for top 100 tourist cities as downloadable SQLite files (~50MB each), enabling fully offline operation in areas with poor connectivity
