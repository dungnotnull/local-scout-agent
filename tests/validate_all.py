"""Quick end-to-end validation of all layers."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check(name, fn):
    try:
        start = time.time()
        fn()
        ms = (time.time() - start) * 1000
        print(f"  PASS {name} ({ms:.0f}ms)")
        return True
    except Exception as e:
        print(f"  FAIL {name}: {e}")
        return False

results = []
print("\n=== LAYER 1: Config & Utils ===")
results.append(check("config", lambda: __import__('app.config').config.settings))
results.append(check("crypto", lambda: __import__('app.utils.crypto').utils.crypto.hash_string("test")))
results.append(check("geo", lambda: __import__('app.utils.geo').utils.geo.haversine_distance(10,106,10.01,106.01)))

print("\n=== LAYER 2: Database & Models ===")
from app.database import engine, Base, SessionLocal
from app.models.models import Source, RawDocument, Restaurant, Review, AuthenticityScore
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
print("  PASS tables recreated")

db = SessionLocal()
s = Source(name='test', url_pattern='test.com', source_type='reddit')
db.add(s); db.flush()
r = Restaurant(name='Test', canonical_name='test', lat=10.7, lon=106.7, cuisine_type='vn', gem_score=80)
db.add(r); db.flush()
d = RawDocument(source_id=s.id, url='http://x.com/1', content_hash='abc', body='great food')
db.add(d); db.flush()
rev = Review(raw_document_id=d.id, restaurant_id=r.id, body_text='great', language='en')
db.add(rev); db.flush()
asc = AuthenticityScore(review_id=rev.id, restaurant_id=r.id, authenticity_score=0.9, confidence=0.9)
db.add(asc)
db.commit()
count = db.query(Restaurant).count()
db.close()
print(f"  PASS CRUD ({count} restaurant)")

print("\n=== LAYER 3: ML Pipeline ===")
results.append(check("authenticity_scorer", lambda: __import__('app.ml.authenticity_scorer').ml.authenticity_scorer.AuthenticityScorer()))
results.append(check("sentiment_analyzer", lambda: __import__('app.ml.sentiment_analyzer').ml.sentiment_analyzer.SentimentAnalyzer()))
results.append(check("entity_extractor", lambda: __import__('app.ml.entity_extractor').ml.entity_extractor.EntityExtractor()))
results.append(check("embedding_pipeline", lambda: __import__('app.ml.embedding_pipeline').ml.embedding_pipeline.EmbeddingPipeline()))
results.append(check("hidden_gem_scorer", lambda: __import__('app.ml.scoring.hidden_gem_scorer').ml.scoring.hidden_gem_scorer.HiddenGemScorer()))
def _init_reviewer_profiler(): from app.ml.scoring.reviewer_profiler import ReviewerProfiler; return ReviewerProfiler()
results.append(check("reviewer_profiler", _init_reviewer_profiler))
results.append(check("menu_ocr", lambda: __import__('app.ml.scoring.menu_ocr').ml.scoring.menu_ocr.MenuOCRPipeline()))
results.append(check("temporal_tracker", lambda: __import__('app.ml.scoring.temporal_tracker').ml.scoring.temporal_tracker.TemporalQualityTracker()))
results.append(check("query_understanding", lambda: __import__('app.ml.scoring.query_understanding').ml.scoring.query_understanding.QueryUnderstandingEngine()))

print("\n=== LAYER 4: LLM Backends ===")
results.append(check("llm_base", lambda: __import__('app.llm.base', fromlist=['LLMBackend'])))
results.append(check("llm_router", lambda: __import__('app.llm.router', fromlist=['LLMRouter'])))
# Backends need API keys to init, skip full init but verify import
results.append(check("claude_import", lambda: __import__('app.llm.backends.claude_backend')))
results.append(check("gpt4_import", lambda: __import__('app.llm.backends.gpt4_backend')))
results.append(check("ollama_import", lambda: __import__('app.llm.backends.ollama_backend')))

print("\n=== LAYER 5: Crawler ===")
results.append(check("robots_checker", lambda: __import__('app.crawler.robots_checker').crawler.robots_checker.RobotsChecker()))
results.append(check("rate_limiter", lambda: __import__('app.crawler.rate_limiter').crawler.rate_limiter.RateLimiter()))
results.append(check("forum_parser", lambda: __import__('app.crawler.parsers.forum_parser')))
results.append(check("reddit_parser", lambda: __import__('app.crawler.parsers.reddit_parser')))
results.append(check("blog_parser", lambda: __import__('app.crawler.parsers.blog_parser')))
results.append(check("knowledge_crawler", lambda: __import__('app.crawler.knowledge_crawler').crawler.knowledge_crawler.KnowledgeCrawler()))

print("\n=== LAYER 6: Vector Store ===")
def _init_chroma(): from app.vector_store.chroma_client import ChromaClient; return ChromaClient()
results.append(check("chroma_client", _init_chroma))
results.append(check("retriever", lambda: __import__('app.vector_store.retriever').vector_store.retriever.SemanticRetriever()))

print("\n=== LAYER 7: Tasks (Celery) ===")
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/0')
results.append(check("celery_app", lambda: __import__('app.tasks.celery_app')))
results.append(check("crawl_tasks", lambda: __import__('app.tasks.crawl_tasks')))
results.append(check("knowledge_tasks", lambda: __import__('app.tasks.knowledge_tasks')))

print("\n=== LAYER 8: API Routes ===")
results.append(check("restaurants_route", lambda: __import__('app.api.routes.restaurants')))
results.append(check("scout_route", lambda: __import__('app.api.routes.scout')))
results.append(check("translate_route", lambda: __import__('app.api.routes.translate')))
results.append(check("trust_route", lambda: __import__('app.api.routes.trust')))

print("\n=== LAYER 9: Middleware & Logging ===")
results.append(check("middleware", lambda: __import__('app.middleware')))
results.append(check("metrics", lambda: __import__('app.metrics')))
results.append(check("logging_config", lambda: __import__('app.logging_config')))

print("\n=== LAYER 10: FastAPI App ===")
results.append(check("main_app", lambda: __import__('app.main').main.app))

print("\n=== LAYER 11: CLI ===")
results.append(check("cli_import", lambda: __import__('app.cli')))

passed = sum(1 for r in results if r)
failed = len(results) - passed
print(f"\n{'='*50}")
print(f"RESULTS: {passed} passed, {failed} failed out of {len(results)} checks")
print(f"{'='*50}")
