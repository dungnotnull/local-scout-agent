import asyncio
import json
import logging

from app.tasks.celery_app import celery_app
from app.database import SessionLocal
from app.models.models import RawDocument, Review, Restaurant, AuthenticityScore
from app.crawler.area_crawler import AreaCrawlJob

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def crawl_area_task(self, lat: float, lon: float, radius_km: float, force_refresh: bool = False):
    logger.info(f"Crawl task: area ({lat}, {lon}), radius={radius_km}km")
    try:
        job = AreaCrawlJob(lat=lat, lon=lon, radius_km=radius_km)
        stats = asyncio.run(job.run())
        logger.info(f"Crawl task completed: {stats}")
        return {"status": "completed", "stats": stats}
    except Exception as e:
        logger.error(f"Crawl task failed: {e}")
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=1)
def process_document_task(self, document_id: int):
    logger.info(f"Processing document {document_id}")
    db = SessionLocal()
    try:
        doc = db.query(RawDocument).filter(RawDocument.id == document_id).first()
        if not doc:
            return {"status": "skipped", "reason": "not_found"}

        from app.ml.authenticity_scorer import AuthenticityScorer
        from app.ml.sentiment_analyzer import SentimentAnalyzer
        from app.ml.entity_extractor import EntityExtractor
        from app.ml.embedding_pipeline import EmbeddingPipeline
        from app.ml.scoring.hidden_gem_scorer import HiddenGemScorer
        from app.vector_store.chroma_client import chroma_client, VectorDocument

        body = doc.body or ""
        title = doc.title or ""

        scorer = AuthenticityScorer()
        scorer.load()
        auth_result = scorer._score_single(f"{title}\n{body}")

        sentiment = SentimentAnalyzer()
        sentiment.load()
        sent_result = sentiment.analyze(body, doc.language)

        extractor = EntityExtractor()
        extractor.load()
        extraction = extractor.extract(f"{title}\n{body}")

        embedding = EmbeddingPipeline()
        embedding.load()
        emb = embedding.encode(f"{title}\n{body}")

        restaurant = None
        for name in extraction.restaurant_names[:1]:
            restaurant = (
                db.query(Restaurant)
                .filter(Restaurant.canonical_name.ilike(f"%{name}%"))
                .first()
            )
            if restaurant:
                break

        if not restaurant and extraction.restaurant_names:
            restaurant = Restaurant(
                name=extraction.restaurant_names[0],
                canonical_name=extraction.restaurant_names[0].lower().strip(),
                cuisine_type="unknown",
                lat=doc.geo_lat,
                lon=doc.geo_lon,
            )
            db.add(restaurant)
            db.flush()

        if restaurant:
            review = Review(
                raw_document_id=doc.id,
                restaurant_id=restaurant.id,
                author_id_hashed=doc.author_id_hashed,
                body_text=body[:2000],
                language=doc.language or "unknown",
                published_at=doc.published_at,
                extracted_dish_names=json.dumps(extraction.dish_names, ensure_ascii=False),
            )
            db.add(review)
            db.flush()

            auth_score = AuthenticityScore(
                review_id=review.id,
                restaurant_id=restaurant.id,
                authenticity_score=auth_result.authenticity_score,
                confidence=auth_result.confidence,
                sentiment_score=sent_result.sentiment,
                classification=auth_result.classification,
                flagged_keywords=json.dumps(auth_result.flagged_keywords),
                model_version=auth_result.model_version,
            )
            db.add(auth_score)
            db.flush()

            gem_scorer = HiddenGemScorer()
            scores = (
                db.query(AuthenticityScore)
                .filter(AuthenticityScore.restaurant_id == restaurant.id)
                .all()
            )
            auth_avg = sum(s.authenticity_score for s in scores) / len(scores) if scores else 0.5
            existing_meta = {}
            if restaurant.gem_score_components:
                try:
                    existing_meta = json.loads(restaurant.gem_score_components)
                except (json.JSONDecodeError, TypeError):
                    pass
            local_ratio = existing_meta.get("local_ratio", 0.3)
            checkin_count = existing_meta.get("checkin_count", len(scores))
            marketing = existing_meta.get("marketing_signal", 1.0)

            from app.ml.scoring.hidden_gem_scorer import GemScoreComponents
            gem = gem_scorer.compute(GemScoreComponents(
                authenticity_score_avg=auth_avg,
                local_ratio=local_ratio,
                checkin_count=checkin_count,
                marketing_signal=marketing,
            ))
            restaurant.gem_score = round(gem, 2)

            try:
                chroma_client.add([VectorDocument(
                    id=f"review_{review.id}",
                    embedding=emb,
                    metadata={
                        "review_id": review.id,
                        "restaurant_id": restaurant.id,
                        "authenticity_score": auth_result.authenticity_score,
                        "sentiment": sent_result.sentiment,
                        "classification": auth_result.classification,
                    },
                    text=body[:1000],
                )])
            except Exception as e:
                logger.warning(f"ChromaDB add failed: {e}")

        db.commit()
        return {"status": "completed", "document_id": document_id, "restaurant_id": restaurant.id if restaurant else None}
    except Exception as e:
        db.rollback()
        logger.error(f"Document processing failed: {e}")
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def score_reviews_task(self, restaurant_id: int):
    logger.info(f"Scoring reviews for restaurant {restaurant_id}")
    db = SessionLocal()
    try:
        from app.ml.scoring.reviewer_profiler import local_ratio_calculator
        ratio_data = local_ratio_calculator.calculate_for_restaurant(restaurant_id, db)

        from app.ml.scoring.temporal_tracker import temporal_quality_tracker
        temporal_quality_tracker.mark_restaurant_quality_flags(restaurant_id, db)

        restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
        if restaurant:
            existing = {}
            if restaurant.gem_score_components:
                try:
                    existing = json.loads(restaurant.gem_score_components)
                except (json.JSONDecodeError, TypeError):
                    pass
            existing.update(ratio_data)
            restaurant.gem_score_components = json.dumps(existing, ensure_ascii=False)
            restaurant.local_ratio = ratio_data["local_ratio"]
            restaurant.checkin_count = ratio_data["total_count"]
            db.commit()

        return {"status": "completed", "restaurant_id": restaurant_id, "ratio_data": ratio_data}
    except Exception as e:
        db.rollback()
        logger.error(f"Scoring failed for restaurant {restaurant_id}: {e}")
        raise self.retry(exc=e)
    finally:
        db.close()


@celery_app.task
def scheduled_area_refresh():
    logger.info("Running scheduled area refresh")
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        from sqlalchemy import distinct
        areas = db.query(RawDocument.geo_lat, RawDocument.geo_lon).filter(
            RawDocument.geo_lat.isnot(None),
            RawDocument.geo_lon.isnot(None),
        ).distinct().limit(10).all()
        for lat, lon in areas:
            crawl_area_task.delay(lat=lat, lon=lon, radius_km=5.0)
        logger.info(f"Scheduled refresh queued {len(areas)} area crawl tasks")
        return {"status": "completed", "areas_queued": len(areas)}
    except Exception as e:
        logger.error(f"Scheduled refresh failed: {e}")
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()
