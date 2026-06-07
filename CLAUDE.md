# CLAUDE.md — Local Scout Agent

## Project Identity
- **Name:** local-scout-agent
- **Tagline:** Your AI-powered guide to authentic local dining — cut through tourist traps and fake KOL reviews
- **Current Status:** Phase 0 — Research & Environment Setup
- **Phase:** Pre-Development

## Core Problem
Tourists visiting unfamiliar areas are routinely overcharged and misled by inflated Google/TripAdvisor ratings, KOL-sponsored content, and coordinated fake review campaigns. Authentic local eateries — the ones serving genuinely good food at fair prices — are buried in local-language forums, obscure Facebook groups, and personal blogs that tourists never discover. Local Scout Agent solves this by crawling genuine local discourse, applying ML-based authenticity filtering, and surfacing hidden gem restaurants on a live map with translated menus and dish recommendations. The system specifically targets the mismatch between tourist-facing review platforms (curated, gameable) and authentic local information channels (unstructured, unmonetized, trustworthy).

## Architecture Summary
- **Platform:** Python backend (FastAPI) + React/Leaflet.js frontend map
- **ML Stack:** Sentence-transformers for semantic embeddings, multilingual sentiment classifier for PR/marketing detection, NER for location and dish name extraction
- **Local SLM:** Phi-3-mini-4k-instruct for on-device text scoring, authenticity classification, and lightweight menu translation (privacy-preserving, no API call required)
- **Vector DB:** ChromaDB (local dev) / Qdrant (production)
- **Crawler:** crawl4ai for forum and blog scraping; Playwright-based scraper for dynamic content; Apify actors for Facebook group data extraction
- **Optional External APIs:** Claude API for advanced menu translation and dish recommendations; Google Places API for geocoding; Mapbox for map tiles

## Key Technical Decisions
1. **Authenticity Score** — Each scraped post is assigned a 0–1 "local authenticity" score using a fine-tuned classifier that detects PR language, sponsored hashtags, affiliate link patterns, and KOL disclosure markers
2. **Temporal weighting** — Recent check-in data and posts from recurring local accounts weighted higher than one-time tourist reviews; accounts with history in the area score higher
3. **Local-first language processing** — All Vietnamese, Thai, Indonesian, and other local-language text is processed locally using multilingual models before any cloud API call, ensuring zero PII leakage
4. **Hidden gem scoring formula** — Combines: (review authenticity score) × (local-to-tourist reviewer ratio) × (check-in frequency by locals) × (inverse of Google rating prominence / marketing spend signals)
5. **Pluggable LLM backend** — Claude API → GPT-4o → local Ollama (Llama 3) fallback chain for menu translation and dish recommendations; graceful degradation at each tier
6. **Privacy by design** — No persistent user location stored; all crawled reviewer data anonymized before storage; GDPR-aligned data retention policies
7. **RAG over local forum data** — Vector embeddings of authentic posts enable semantic search ("best pho that locals actually eat") rather than keyword matching

## External LLM API Integrations
| Service | Purpose | Config Key | Model |
|---------|---------|------------|-------|
| Claude API (Anthropic) | Menu translation, dish recommendations, hidden gem summary generation | `ANTHROPIC_API_KEY` | claude-sonnet-4-6 |
| OpenAI GPT-4o | Fallback translation and structured data extraction | `OPENAI_API_KEY` | gpt-4o |
| Google Places API | Geocoding restaurant addresses, hours enrichment | `GOOGLE_PLACES_API_KEY` | — |
| Mapbox | Map tile rendering and routing | `MAPBOX_TOKEN` | — |

## HuggingFace Models
| Model ID | Purpose | Link |
|----------|---------|------|
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Multilingual semantic embeddings for RAG retrieval | [HF](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) |
| `cardiffnlp/twitter-xlm-roberta-base-sentiment-multilingual` | Multilingual sentiment analysis for review authenticity scoring | [HF](https://huggingface.co/cardiffnlp/twitter-xlm-roberta-base-sentiment-multilingual) |
| `microsoft/Phi-3-mini-4k-instruct` | Local SLM for PR/marketing pattern detection and light text classification | [HF](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct) |
| `facebook/nllb-200-distilled-600M` | Local menu translation across 200 languages without API dependency | [HF](https://huggingface.co/facebook/nllb-200-distilled-600M) |
| `dslim/bert-base-NER` | Named entity recognition for restaurant names, dish names, street addresses | [HF](https://huggingface.co/dslim/bert-base-NER) |
| `typeform/distilbert-base-uncased-mnli` | Zero-shot classification for PR vs. organic content detection | [HF](https://huggingface.co/typeform/distilbert-base-uncased-mnli) |

## Current Active Development Tasks
- [ ] Set up project repository structure and virtual environment
- [ ] Configure crawl4ai for target sources (Foody.vn forums, Facebook groups, Reddit r/Vietnam, local travel blogs)
- [ ] Build authenticity scoring pipeline (PR keyword detection + account history analysis)
- [ ] Implement ChromaDB vector store with multilingual embeddings
- [ ] Build React + Leaflet.js map frontend with hidden gem markers
- [ ] Integrate NLLB-200 for local menu translation pipeline
- [ ] Connect Claude API for dish recommendation and summary generation
- [ ] Implement hidden gem scoring formula with configurable weights
- [ ] End-to-end integration test with Ho Chi Minh City pilot dataset
- [ ] Build self-update crawler using crawl4ai scheduled tasks

## Related Documentation
- [PROJECT-detail.md](PROJECT-detail.md) — Full technical specification and architecture
- [PROJECT-DEVELOPMENT-PHASE-TRACKING.md](PROJECT-DEVELOPMENT-PHASE-TRACKING.md) — Phase-by-phase development roadmap
- [SECOND-KNOWLEDGE-BRAIN.md](SECOND-KNOWLEDGE-BRAIN.md) — Research knowledge base and self-update protocol
