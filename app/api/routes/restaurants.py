import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, text

from app.database import get_db
from app.models.models import Restaurant, Review, AuthenticityScore, RawDocument
from app.utils.geo import haversine_distance, is_within_radius

logger = logging.getLogger(__name__)
router = APIRouter()


class RestaurantOut(BaseModel):
    id: int
    name: str
    address: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    cuisine_type: Optional[str] = None
    price_range: Optional[str] = None
    gem_score: Optional[float] = None
    local_ratio: Optional[float] = None
    marketing_signal: Optional[float] = None
    distance_km: Optional[float] = None

    class Config:
        from_attributes = True


class PaginatedRestaurants(BaseModel):
    restaurants: list[RestaurantOut]
    total: int
    page: int
    page_size: int
    query_lat: float
    query_lon: float


class ReviewOut(BaseModel):
    id: int
    body_text: Optional[str] = None
    rating: Optional[float] = None
    likes_count: int
    published_at: Optional[str] = None
    language: Optional[str] = None
    author_id_hashed: Optional[str] = None
    authenticity_score: Optional[float] = None
    classification: Optional[str] = None

    class Config:
        from_attributes = True


class RestaurantDetail(BaseModel):
    id: int
    name: str
    address: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    google_place_id: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    cuisine_type: Optional[str] = None
    price_range: Optional[str] = None
    gem_score: Optional[float] = None
    gem_score_components: Optional[dict] = None
    local_ratio: Optional[float] = None
    marketing_signal: Optional[float] = None
    checkin_count: int
    discovered_at: Optional[str] = None
    top_reviews: list[ReviewOut] = []
    dish_recommendations: Optional[str] = None
    hidden_gem_summary: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/restaurants", response_model=PaginatedRestaurants)
def list_restaurants(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    radius_km: float = Query(default=2.0, ge=0.1, le=50.0),
    min_gem_score: Optional[float] = Query(default=None, ge=0, le=100),
    max_gem_score: Optional[float] = Query(default=None, ge=0, le=100),
    cuisine_type: Optional[str] = None,
    price_range: Optional[str] = None,
    query: Optional[str] = Query(default=None, description="Natural language search query"),
    sort_by: str = Query(default="gem_score", pattern="^(gem_score|distance|name)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    restaurant_query = db.query(Restaurant).filter(Restaurant.is_active == True)

    if min_gem_score is not None:
        restaurant_query = restaurant_query.filter(Restaurant.gem_score >= min_gem_score)
    if max_gem_score is not None:
        restaurant_query = restaurant_query.filter(Restaurant.gem_score <= max_gem_score)
    if cuisine_type:
        restaurant_query = restaurant_query.filter(Restaurant.cuisine_type == cuisine_type)
    if price_range:
        restaurant_query = restaurant_query.filter(Restaurant.price_range == price_range)

    if query:
        restaurant_query = restaurant_query.filter(
            (Restaurant.name.ilike(f"%{query}%")) |
            (Restaurant.cuisine_type.ilike(f"%{query}%")) |
            (Restaurant.address.ilike(f"%{query}%"))
        )

    all_active = restaurant_query.all()
    filtered = []
    for r in all_active:
        if r.lat is not None and r.lon is not None:
            dist = haversine_distance(lat, lon, r.lat, r.lon)
            if dist <= radius_km:
                filtered.append((r, dist))
        else:
            filtered.append((r, 999.0))

    if sort_by == "distance":
        filtered.sort(key=lambda x: x[1])
    elif sort_by == "gem_score":
        filtered.sort(key=lambda x: x[0].gem_score or 0, reverse=True)
    elif sort_by == "name":
        filtered.sort(key=lambda x: x[0].name.lower())

    total = len(filtered)
    offset = (page - 1) * page_size
    page_items = filtered[offset:offset + page_size]

    restaurants = []
    for r, dist in page_items:
        restaurants.append(RestaurantOut(
            id=r.id,
            name=r.name,
            address=r.address,
            lat=r.lat,
            lon=r.lon,
            cuisine_type=r.cuisine_type,
            price_range=r.price_range,
            gem_score=r.gem_score,
            local_ratio=r.local_ratio,
            marketing_signal=r.marketing_signal,
            distance_km=round(dist, 2),
        ))

    return PaginatedRestaurants(
        restaurants=restaurants,
        total=total,
        page=page,
        page_size=page_size,
        query_lat=lat,
        query_lon=lon,
    )


@router.get("/restaurants/{restaurant_id}", response_model=RestaurantDetail)
def get_restaurant(
    restaurant_id: int,
    db: Session = Depends(get_db),
):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    top_reviews = (
        db.query(Review, AuthenticityScore)
        .join(AuthenticityScore, Review.id == AuthenticityScore.review_id, isouter=True)
        .filter(Review.restaurant_id == restaurant_id)
        .order_by(AuthenticityScore.authenticity_score.desc().nullslast())
        .limit(5)
        .all()
    )

    review_outs = []
    for review, score in top_reviews:
        published = review.published_at.isoformat() if review.published_at else None
        review_outs.append(ReviewOut(
            id=review.id,
            body_text=review.body_text,
            rating=review.rating,
            likes_count=review.likes_count or 0,
            published_at=published,
            language=review.language,
            author_id_hashed=review.author_id_hashed,
            authenticity_score=score.authenticity_score if score else None,
            classification=score.classification if score else None,
        ))

    components = None
    if restaurant.gem_score_components:
        try:
            components = json.loads(restaurant.gem_score_components)
        except (json.JSONDecodeError, TypeError):
            pass

    return RestaurantDetail(
        id=restaurant.id,
        name=restaurant.name,
        address=restaurant.address,
        lat=restaurant.lat,
        lon=restaurant.lon,
        google_place_id=restaurant.google_place_id,
        phone=restaurant.phone,
        website=restaurant.website,
        cuisine_type=restaurant.cuisine_type,
        price_range=restaurant.price_range,
        gem_score=restaurant.gem_score,
        gem_score_components=components,
        local_ratio=restaurant.local_ratio,
        marketing_signal=restaurant.marketing_signal,
        checkin_count=restaurant.checkin_count or 0,
        discovered_at=restaurant.discovered_at.isoformat() if restaurant.discovered_at else None,
        top_reviews=review_outs,
        dish_recommendations=None,
        hidden_gem_summary=None,
    )


@router.get("/restaurants/stats/overview")
def get_stats(db: Session = Depends(get_db)):
    total_restaurants = db.query(func.count(Restaurant.id)).scalar()
    total_reviews = db.query(func.count(Review.id)).scalar()
    avg_gem_score = db.query(func.avg(Restaurant.gem_score)).filter(Restaurant.gem_score.isnot(None)).scalar()
    cuisine_counts = (
        db.query(Restaurant.cuisine_type, func.count(Restaurant.id))
        .filter(Restaurant.is_active == True)
        .group_by(Restaurant.cuisine_type)
        .all()
    )
    return {
        "total_restaurants": total_restaurants,
        "total_reviews": total_reviews,
        "average_gem_score": round(avg_gem_score, 2) if avg_gem_score else None,
        "cuisine_distribution": {c[0] or "unknown": c[1] for c in cuisine_counts},
    }
