from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import settings
from app.logging_config import setup_logging
from app.middleware import RateLimitMiddleware, SecurityHeadersMiddleware, RequestLoggingMiddleware
from app.metrics import setup_metrics
from app.api.routes import restaurants, scout, translate, trust

logger = setup_logging()

app = FastAPI(
    title="Local Scout Agent",
    description="AI-powered guide to authentic local dining — cut through tourist traps and fake KOL reviews",
    version="0.1.0",
    docs_url="/api/docs" if settings.env != "production" else None,
    redoc_url="/api/redoc" if settings.env != "production" else None,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.env == "development" else [],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

setup_metrics(app)

app.include_router(restaurants.router, prefix="/api/v1", tags=["restaurants"])
app.include_router(scout.router, prefix="/api/v1", tags=["scout"])
app.include_router(translate.router, prefix="/api/v1", tags=["translate"])
app.include_router(trust.router, prefix="/api/v1", tags=["trust"])

static_dir = Path(__file__).resolve().parent.parent / "frontend" / "build"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

logger.info(f"Local Scout Agent starting in {settings.env} mode")


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "version": "0.1.0",
        "env": settings.env,
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }


@app.get("/health/ready")
def readiness_check():
    checks = {"api": "ok"}
    try:
        import redis
        r = redis.from_url(settings.redis_url)
        r.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"

    try:
        from app.database import engine
        engine.connect().close()
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"

    try:
        from app.vector_store.chroma_client import chroma_client
        count = chroma_client.count()
        checks["chromadb"] = f"ok ({count} documents)"
    except Exception:
        checks["chromadb"] = "unavailable"

    all_ok = all(v == "ok" or v.startswith("ok") for v in checks.values())
    return {"status": "ready" if all_ok else "degraded", "checks": checks}
