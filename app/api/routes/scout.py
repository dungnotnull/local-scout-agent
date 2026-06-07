import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.crawler.area_crawler import AreaCrawlJob
from app.tasks.crawl_tasks import crawl_area_task

logger = logging.getLogger(__name__)
router = APIRouter()

_jobs: dict[str, dict] = {}


class ScoutRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(default=2.0, ge=0.1, le=50.0)
    force_refresh: bool = False


class ScoutResponse(BaseModel):
    job_id: str
    status: str


class ScoutStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: dict | None = None
    created_at: str | None = None
    completed_at: str | None = None


@router.post("/scout", response_model=ScoutResponse)
def trigger_scout(
    request: ScoutRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "progress": {"lat": request.lat, "lon": request.lon, "radius_km": request.radius_km, "results": 0},
    }

    background_tasks.add_task(
        _run_crawl_job, job_id, request.lat, request.lon, request.radius_km, request.force_refresh
    )

    return ScoutResponse(job_id=job_id, status="queued")


@router.get("/scout/{job_id}", response_model=ScoutStatusResponse)
def get_scout_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return ScoutStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress"),
        created_at=job.get("created_at"),
        completed_at=job.get("completed_at"),
    )


async def _run_crawl_job(job_id: str, lat: float, lon: float, radius_km: float, force_refresh: bool):
    _jobs[job_id]["status"] = "running"
    try:
        job = AreaCrawlJob(lat=lat, lon=lon, radius_km=radius_km)
        stats = await job.run()
        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        _jobs[job_id]["progress"] = stats
    except Exception as e:
        logger.error(f"Crawl job {job_id} failed: {e}")
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        _jobs[job_id]["error"] = str(e)


@router.get("/scout/area/{lat}/{lon}")
def check_area_cache(
    lat: float,
    lon: float,
    db: Session = Depends(get_db),
):
    from app.models.models import RawDocument
    from datetime import timedelta
    from app.config import settings
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.crawl_cache_ttl_hours)
    count = (
        db.query(RawDocument)
        .filter(
            RawDocument.fetched_at >= cutoff,
            RawDocument.geo_lat.isnot(None),
            RawDocument.geo_lon.isnot(None),
        )
        .count()
    )
    return {
        "cached_documents": count,
        "cache_fresh": count > 0,
        "cache_ttl_hours": settings.crawl_cache_ttl_hours,
    }
