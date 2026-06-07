from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
from app.utils.crypto import hash_string


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    url_pattern = Column(Text, nullable=False)
    source_type = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    raw_documents = relationship("RawDocument", back_populates="source")


class RawDocument(Base):
    __tablename__ = "raw_documents"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    url = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    title = Column(Text, nullable=True)
    body = Column(Text, nullable=True)
    author_name = Column(String(255), nullable=True)
    author_id_hashed = Column(String(64), nullable=True, index=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
    geo_lat = Column(Float, nullable=True)
    geo_lon = Column(Float, nullable=True)
    geo_radius_km = Column(Float, nullable=True)
    language = Column(String(10), nullable=True)
    raw_json = Column(Text, nullable=True)

    source = relationship("Source", back_populates="raw_documents")
    reviews = relationship("Review", back_populates="raw_document")

    __table_args__ = (
        Index("idx_raw_documents_content_hash", "content_hash"),
    )


class Restaurant(Base):
    __tablename__ = "restaurants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    canonical_name = Column(String(255), nullable=False, index=True)
    address = Column(Text, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    google_place_id = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    website = Column(Text, nullable=True)
    cuisine_type = Column(String(100), nullable=True)
    price_range = Column(String(50), nullable=True)
    gem_score = Column(Float, nullable=True, index=True)
    gem_score_components = Column(Text, nullable=True)
    marketing_signal = Column(Float, default=1.0)
    local_ratio = Column(Float, nullable=True)
    checkin_count = Column(Integer, default=0)
    discovered_at = Column(DateTime(timezone=True), server_default=func.now())
    last_updated = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)

    reviews = relationship("Review", back_populates="restaurant")
    authenticity_scores = relationship("AuthenticityScore", back_populates="restaurant")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    raw_document_id = Column(Integer, ForeignKey("raw_documents.id"), nullable=False)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False, index=True)
    author_id_hashed = Column(String(64), nullable=True, index=True)
    body_text = Column(Text, nullable=True)
    rating = Column(Float, nullable=True)
    likes_count = Column(Integer, default=0)
    published_at = Column(DateTime(timezone=True), nullable=True)
    language = Column(String(10), nullable=True)
    extracted_dish_names = Column(Text, nullable=True)

    raw_document = relationship("RawDocument", back_populates="reviews")
    restaurant = relationship("Restaurant", back_populates="reviews")
    authenticity_scores = relationship("AuthenticityScore", back_populates="review")

    __table_args__ = (
        Index("idx_reviews_restaurant_id", "restaurant_id"),
        Index("idx_reviews_author_hashed", "author_id_hashed"),
    )


class AuthenticityScore(Base):
    __tablename__ = "authenticity_scores"

    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False, index=True)
    authenticity_score = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    sentiment_score = Column(Float, nullable=True)
    classification = Column(String(50), nullable=True)
    flagged_keywords = Column(Text, nullable=True)
    model_version = Column(String(100), nullable=True)
    computed_at = Column(DateTime(timezone=True), server_default=func.now())

    review = relationship("Review", back_populates="authenticity_scores")
    restaurant = relationship("Restaurant", back_populates="authenticity_scores")
