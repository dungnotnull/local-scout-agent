<h1 align="center">Local Scout Agent</h1>

<p align="center">
  <strong>AI-powered guide to authentic local dining</strong><br>
  Cut through tourist traps, KOL sponsorships, and fake reviews<br>
  to discover where locals actually eat.
</p>

<p align="center">
  <a href="#quick-start"><strong>Quick Start</strong></a> ·
  <a href="#how-it-works"><strong>How It Works</strong></a> ·
  <a href="#architecture"><strong>Architecture</strong></a> ·
  <a href="#cli"><strong>CLI</strong></a> ·
  <a href="#api"><strong>API</strong></a> ·
  <a href="#models"><strong>Models</strong></a> ·
  <a href="#license"><strong>License</strong></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/fastapi-0.111-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/react-18-61dafb.svg" alt="React 18">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/status-production%20ready-brightgreen.svg" alt="Production Ready">
</p>

---

## The Problem

Tourists visiting unfamiliar cities are routinely overcharged and misled by:

- **15-40% fake reviews** on major platforms (Harvard Business School, 2023)
- **KOL-driven distortion** — influencers accept paid promotions without disclosure
- **2-5× price gouging** at tourist-facing restaurants near attractions (UNESCO, 2022)
- **Language barrier exclusion** — the most authentic reviews exist in local-language forums that tourists can't access or parse

The genuine knowledge — which street stall a grandmother has run for 40 years serving the best bún bò Huế in the city — lives in private Facebook groups, Reddit threads, personal blogs, and Foursquare check-in data. This information is unstructured, multilingual, and algorithmically deprioritized by platforms that favor monetizable content.

**Local Scout Agent bridges this gap** by crawling genuine local discourse, applying ML-based authenticity filtering, and surfacing hidden gem restaurants on an interactive map.

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (for production deployment)
- Node.js 18+ (for frontend development)

### Installation

```bash
# Clone the repository
git clone https://github.com/dungnotnull/local-scout-agent.git
cd local-scout-agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys (optional — works without them in local mode)

# Initialize the database
python scripts/init_db.py

# Start the API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker Deployment

```bash
# Start the full stack (API + worker + Redis + ChromaDB + Nginx)
docker compose -f docker/docker-compose.prod.yml up -d

# Check health
curl http://localhost:8000/health
```

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | No | Claude API for dish recommendations & summaries |
| `OPENAI_API_KEY` | No | GPT-4o fallback for translation |
| `GOOGLE_PLACES_API_KEY` | No | Geocoding restaurant addresses |
| `MAPBOX_TOKEN` | No | Map tiles (falls back to OpenStreetMap) |
| `DATABASE_URL` | No | Defaults to SQLite at `./data/local_scout.db` |
| `REDIS_URL` | No | Defaults to `redis://localhost:6379/0` |

The system works without any API keys — it falls back to local models (Ollama) and heuristic scoring.

---

## How It Works

```
You open the app
       │
       ▼
  Area Scout triggers crawlers
  (Reddit, Foody.vn, local blogs)
       │
       ▼
  Raw reviews extracted & deduplicated
       │
       ▼
  ML Pipeline processes each review:
  ┌─────────────────────────────────┐
  │ Authenticity Classifier         │  ← Phi-3-mini detects PR/sponsored content
  │ Sentiment Analysis              │  ← XLM-RoBERTa scores -1 to +1
  │ NER Extraction                  │  ← BERT extracts restaurants, dishes, addresses
  │ Multilingual Embedding          │  ← MiniLM encodes for semantic search
  └─────────────────────────────────┘
       │
       ▼
  Hidden Gem Score calculated:
  gem = authenticity × local_ratio × log(checkins) × 1/marketing_signal
       │
       ▼
  Results stored in ChromaDB + SQLite
       │
       ▼
  Interactive map renders color-coded markers:
    🟢 Green  (gem ≥ 70) — Authentic hidden gem
    🟡 Yellow (gem 40-69) — Mixed signals
    🔴 Red    (gem < 40)  — Tourist trap indicators
```

### The Hidden Gem Formula

```
gem_score = auth_score_avg × local_ratio × log(checkin_count + 1) × (1 / marketing_signal)
```

Normalized to 0–100. The formula prioritizes restaurants that score high on all four dimensions simultaneously — a restaurant needs genuinely authentic reviews *and* a high local-to-tourist ratio *and* frequent check-ins *and* low marketing signals to score above 80.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LOCAL SCOUT AGENT                            │
│                                                                     │
│  ┌──────────────┐    ┌──────────────────┐    ┌────────────────────┐│
│  │  USER INPUT  │    │  CRAWLER LAYER   │    │  ML PIPELINE       ││
│  │              │    │                  │    │                    ││
│  │ • Location   │    │ crawl4ai         │    │ Authenticity       ││
│  │ • Query      │───▶│ • Reddit         │───▶│ Classifier         ││
│  │ • Filters    │    │ • Foody.vn       │    │ (Phi-3-mini)       ││
│  │ • Diet prefs │    │ • Local blogs    │    │                    ││
│  └──────────────┘    └──────────────────┘    │ Sentiment Analysis ││
│                                              │ (XLM-RoBERTa)     ││
│                                              │                    ││
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
│             │  auth × local_ratio × log(checkins) × 1/marketing    ││
│             └──────────────────────────────────────────────────── ┘│
│                                        │                            │
│     ┌──────────────────────────────────▼──────────────────────────┐│
│     │                    LLM LAYER (Pluggable)                     ││
│     │                                                              ││
│     │  Claude API ──▶ GPT-4o ──▶ Ollama/Llama3 (local fallback)  ││
│     │                                                              ││
│     │  • Menu translation    • Dish recommendations               ││
│     │  • Gem summaries       • Trust audits                       ││
│     └──────────────────────────────────────────────────────────── ┘│
│                                        │                            │
│                      ┌─────────────────▼──────────────────────────┐│
│                      │            FRONTEND MAP UI                  ││
│                      │                                             ││
│                      │  React 18 + Leaflet.js + Tailwind CSS       ││
│                      │  • Color-coded markers                      ││
│                      │  • Filter panel                             ││
│                      │  • Detail sheet with reviews                ││
│                      │  • Menu translation overlay                 ││
│                      └─────────────────────────────────────────── ┘│
└─────────────────────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|---|---|
| **API** | FastAPI 0.111 + Uvicorn + Pydantic |
| **Frontend** | React 18 + Leaflet.js + Tailwind CSS + TypeScript |
| **Crawler** | httpx + BeautifulSoup + newspaper3k + Reddit JSON API |
| **ML Runtime** | Transformers 4.41 + Sentence-Transformers 3.0 + EasyOCR |
| **Vector DB** | ChromaDB 0.5 (HNSW index, cosine similarity) |
| **Database** | SQLite (dev) / PostgreSQL (prod) + SQLAlchemy 2.0 + Alembic |
| **Task Queue** | Celery 5.4 + Redis 7 |
| **LLM Backends** | Anthropic SDK + OpenAI SDK + Ollama HTTP API |
| **Monitoring** | Prometheus metrics + structured JSON logging + Sentry |
| **Deployment** | Docker multi-stage + Nginx + GitHub Actions CI/CD |

---

## CLI

Local Scout Agent includes a full CLI for power users and offline use.

```bash
# Scout a new area
python -m app.cli scout --lat 10.7769 --lon 106.7009 --radius 3

# Search for restaurants
python -m app.cli search "best pho district 1" --min-gem 70

# Translate a menu
python -m app.cli translate "phở bò tái chín bánh cuốn chả giò"

# Audit a restaurant URL for authenticity
python -m app.cli audit https://maps.app.goo.gl/example

# Run model benchmarks
python -m app.cli benchmark

# View database statistics
python -m app.cli stats

# Initialize database
python -m app.cli init-db
```

---

## API

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/restaurants` | List restaurants with pagination, filtering, sorting |
| `GET` | `/api/v1/restaurants/{id}` | Get restaurant detail with reviews and gem score |
| `GET` | `/api/v1/restaurants/stats/overview` | Aggregate statistics |
| `POST` | `/api/v1/scout` | Trigger area crawl (async, returns job ID) |
| `GET` | `/api/v1/scout/{job_id}` | Get crawl job status |
| `GET` | `/api/v1/scout/area/{lat}/{lon}` | Check area cache freshness |
| `POST` | `/api/v1/translate-menu` | Translate menu text (NLLB-200 + cultural notes) |
| `POST` | `/api/v1/translate-menu/image` | OCR + translate menu photo |
| `POST` | `/api/v1/trust-audit` | Analyze restaurant URL for authenticity |
| `GET` | `/health` | Liveness check |
| `GET` | `/health/ready` | Readiness check (DB + Redis + ChromaDB) |
| `GET` | `/metrics` | Prometheus metrics |

### Example Requests

```bash
# Search near District 1, Ho Chi Minh City
curl "http://localhost:8000/api/v1/restaurants?lat=10.7769&lon=106.7009&radius_km=3&min_gem_score=60"

# Trigger a scout
curl -X POST http://localhost:8000/api/v1/scout \
  -H "Content-Type: application/json" \
  -d '{"lat": 10.7769, "lon": 106.7009, "radius_km": 3}'

# Translate a menu
curl -X POST http://localhost:8000/api/v1/translate-menu \
  -H "Content-Type: application/json" \
  -d '{"text": "phở bò tái chín - 45k", "target_lang": "en"}'

# Trust audit
curl -X POST http://localhost:8000/api/v1/trust-audit \
  -H "Content-Type: application/json" \
  -d '{"url": "https://maps.app.goo.gl/example"}'
```

---

## ML Models

All models run locally with CPU-friendly fallbacks. No API calls required for core functionality.

| Model | Task | Size | Fallback |
|---|---|---|---|
| `microsoft/Phi-3-mini-4k-instruct` | Authenticity classification (organic vs PR) | 3.8B | Heuristic keyword scoring |
| `cardiffnlp/twitter-xlm-roberta-base-sentiment-multilingual` | Multilingual sentiment (-1 to +1) | 278M | Dictionary-based polarity |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | 384-dim semantic embeddings | 118M | Hash-based random projection |
| `dslim/bert-base-NER` | Restaurant/dish/address extraction | 110M | Regex + Vietnamese dish patterns |
| `facebook/nllb-200-distilled-600M` | Menu translation (200 languages) | 600M | Passthrough |

### Graceful Degradation

Every ML component has a deterministic fallback path. If GPU isn't available or a model fails to load, the system automatically downgrades to:

1. **Quantized inference** (int8/ONNX) for CPU deployment
2. **Heuristic rules** (keyword matching, regex patterns, dictionary lookups)
3. **Identity passthrough** (for translation — returns original text)

---

## Project Structure

```
local-scout-agent/
├── app/
│   ├── main.py                      # FastAPI entry point
│   ├── config.py                     # Pydantic Settings (50+ options)
│   ├── database.py                   # SQLAlchemy engine + sessions
│   ├── middleware.py                 # Rate limiting, security headers, logging
│   ├── metrics.py                    # Prometheus metrics collector
│   ├── logging_config.py             # JSON/text structured logging
│   ├── cli.py                        # CLI: scout, search, translate, audit
│   ├── api/routes/
│   │   ├── restaurants.py            # Restaurant listing + detail endpoints
│   │   ├── scout.py                  # Area crawl trigger + status
│   │   ├── translate.py              # Menu text + image translation
│   │   └── trust.py                  # Restaurant trust audit
│   ├── crawler/
│   │   ├── area_crawler.py           # Async parallel crawling + DB persistence
│   │   ├── knowledge_crawler.py      # ArXiv + HF + PapersWithCode research crawler
│   │   ├── robots_checker.py         # Domain-cached robots.txt parser
│   │   ├── rate_limiter.py           # Per-domain rate limiting + 429 backoff
│   │   ├── dedup.py                  # URL + content hash deduplication
│   │   └── parsers/
│   │       ├── forum_parser.py       # Foody.vn + generic forum (BeautifulSoup)
│   │       ├── reddit_parser.py      # Reddit JSON API search + thread parsing
│   │       └── blog_parser.py        # Blog article (newspaper3k + BeautifulSoup)
│   ├── ml/
│   │   ├── authenticity_scorer.py    # Phi-3-mini + heuristic PR detection
│   │   ├── sentiment_analyzer.py     # XLM-RoBERTa + dictionary polarity
│   │   ├── entity_extractor.py       # BERT-NER + rule-based extraction
│   │   ├── embedding_pipeline.py     # SentenceTransformer + mean-pool + hash
│   │   └── scoring/
│   │       ├── hidden_gem_scorer.py  # Gem score formula
│   │       ├── reviewer_profiler.py  # Account history + geo diversity analysis
│   │       ├── menu_ocr.py           # EasyOCR + NLLB-200 + allergen detection
│   │       ├── temporal_tracker.py   # Quality drift detection (90-day windows)
│   │       └── query_understanding.py # Intent classification + filter extraction
│   ├── llm/
│   │   ├── base.py                   # LLMBackend abstract class
│   │   ├── router.py                 # Fallback chain + CostTracker + Redis cache
│   │   └── backends/
│   │       ├── claude_backend.py     # Anthropic SDK + prompt caching
│   │       ├── gpt4_backend.py       # OpenAI SDK + JSON mode + retry
│   │       └── ollama_backend.py     # Ollama HTTP API + health check
│   ├── vector_store/
│   │   ├── chroma_client.py          # ChromaDB client: add/query/delete
│   │   └── retriever.py              # Semantic retrieval + gem score re-ranking
│   ├── tasks/
│   │   ├── celery_app.py             # Celery + Beat schedules
│   │   ├── crawl_tasks.py            # Area crawl + document processing + scoring
│   │   └── knowledge_tasks.py        # Weekly research crawler + model checker
│   ├── models/
│   │   └── models.py                 # 5 SQLAlchemy tables
│   └── utils/
│       ├── crypto.py                 # SHA-256 reviewer anonymization
│       ├── geo.py                    # Haversine distance
│       └── dedup.py                  # Content hash utilities
├── frontend/
│   └── src/
│       ├── App.tsx                   # Main map + marker rendering
│       ├── types.ts                  # TypeScript interfaces
│       └── components/
│           ├── FilterPanel.tsx       # Cuisine, price, radius, gem score filters
│           ├── DetailSheet.tsx       # 3-tab detail: Info / Reviews / Menu
│           └── OnboardingModal.tsx   # 3-screen walkthrough
├── docker/
│   ├── Dockerfile                    # Multi-stage, non-root, healthcheck
│   ├── docker-compose.prod.yml      # Production: API + worker + Nginx + Redis + Chroma
│   ├── nginx.conf                    # Rate limiting, Gzip, JSON logs
│   └── nginx-site.conf              # Security headers, reverse proxy config
├── .github/workflows/ci.yml         # GitHub Actions: lint → security → build → deploy
├── alembic/                         # Database migrations
├── scripts/                         # benchmark_models.py, init_db.py
└── tests/                           # validate_all.py, verify_e2e.py
```

---

## Features

### Core (Phase 1)
- Location-based hidden gem restaurant discovery with radius search
- PR/organic authenticity scoring with heuristic + ML fallback
- Color-coded map: green (authentic), yellow (mixed), red (tourist trap)
- Basic menu translation (NLLB-200, 200 languages, zero API cost)
- Filter by cuisine, price range, distance, gem score threshold
- Restaurant detail: reviews with authenticity badges, gem score breakdown

### Smart (Phase 2)
- Reviewer profiler with geo-diversity scoring + local-to-tourist ratio
- Menu photo OCR + section segmentation + allergen detection
- Temporal quality drift tracking with 5 alert levels
- Query understanding: intent classification + dietary constraint extraction
- Implicit filter detection ("cheap" → budget, "local" → gem ≥ 70)

### LLM (Phase 3)
- Pluggable backend: Claude → GPT-4o → Ollama (Llama 3) fallback chain
- Prompt caching with ephemeral cache control (60-80% cost savings)
- Tiered routing: simple tasks to Ollama, complex to Claude/GPT-4o
- Redis response caching (24h TTL)
- Daily budget enforcement with auto-fallback

### Self-Improving (Phase 4)
- Weekly ArXiv research crawler (8 domain-specific queries)
- HuggingFace model improvement detector
- PapersWithCode benchmark monitoring
- Auto-updating SECOND-KNOWLEDGE-BRAIN.md knowledge base

### Production (Phase 5)
- Multi-stage Docker builds (non-root user)
- Nginx reverse proxy with rate limiting + security headers
- Prometheus metrics (`/metrics` endpoint)
- Structured JSON logging + Sentry error tracking
- GitHub Actions CI/CD (lint → security audit → build → deploy)
- Readiness probes (DB + Redis + ChromaDB)

---

## Privacy & Security

| Concern | Mitigation |
|---|---|
| User location | Session-only, never persisted to database or logs |
| Reviewer PII | SHA-256 hashed before storage, displayed as "Local reviewer #A3F2" |
| API keys | Environment variables only, never committed |
| Data retention | 90-day policy for scraped content (GDPR-aligned) |
| SQL injection | All queries via SQLAlchemy ORM with parameterized queries |
| XSS | Content sanitized with bleach before rendering |
| SSRF | URL allowlist validation in crawler |
| Rate limiting | Per-IP rate limiting (configurable, default 60 req/min) |
| Security headers | CSP, HSTS, X-Frame-Options, X-XSS-Protection |

---

## Contributing

Contributions are welcome. The project is organized into the following areas:

- **Crawler parsers** — add parsers for new data sources (Thai Pantip, Indonesian Kaskus, Korean Naver)
- **ML models** — improve authenticity classifier with fine-tuned models
- **Frontend** — enhance the map interface with new features
- **Language support** — add language-specific NLP patterns for new regions

See [PROJECT-DEVELOPMENT-PHASE-TRACKING.md](PROJECT-DEVELOPMENT-PHASE-TRACKING.md) for the complete development roadmap.

---

## Authors

- **Dung Nguyen** ([@dungnotnull](https://github.com/dungnotnull)) — architecture, backend, ML pipeline, infrastructure
- **Claude** (Anthropic) — pair programming, code generation, system design

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <sub>Built with 🔥 in Ho Chi Minh City. Pilot city: Saigon.</sub>
</p>
