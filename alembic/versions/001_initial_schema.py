"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-07
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url_pattern", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sources_id", "sources", ["id"])

    op.create_table(
        "raw_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("author_name", sa.String(255), nullable=True),
        sa.Column("author_id_hashed", sa.String(64), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("geo_lat", sa.Float(), nullable=True),
        sa.Column("geo_lon", sa.Float(), nullable=True),
        sa.Column("geo_radius_km", sa.Float(), nullable=True),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_raw_documents_id", "raw_documents", ["id"])
    op.create_index("idx_raw_documents_content_hash", "raw_documents", ["content_hash"])
    op.create_index("ix_raw_documents_author_id_hashed", "raw_documents", ["author_id_hashed"])

    op.create_table(
        "restaurants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("canonical_name", sa.String(255), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("google_place_id", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("cuisine_type", sa.String(100), nullable=True),
        sa.Column("price_range", sa.String(50), nullable=True),
        sa.Column("gem_score", sa.Float(), nullable=True),
        sa.Column("gem_score_components", sa.Text(), nullable=True),
        sa.Column("marketing_signal", sa.Float(), nullable=True),
        sa.Column("local_ratio", sa.Float(), nullable=True),
        sa.Column("checkin_count", sa.Integer(), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_updated", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_restaurants_id", "restaurants", ["id"])
    op.create_index("ix_restaurants_canonical_name", "restaurants", ["canonical_name"])
    op.create_index("ix_restaurants_gem_score", "restaurants", ["gem_score"])
    op.create_index("ix_restaurants_google_place_id", "restaurants", ["google_place_id"])

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("raw_document_id", sa.Integer(), nullable=False),
        sa.Column("restaurant_id", sa.Integer(), nullable=False),
        sa.Column("author_id_hashed", sa.String(64), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("likes_count", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("extracted_dish_names", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["raw_document_id"], ["raw_documents.id"]),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reviews_id", "reviews", ["id"])
    op.create_index("idx_reviews_restaurant_id", "reviews", ["restaurant_id"])
    op.create_index("idx_reviews_author_hashed", "reviews", ["author_id_hashed"])

    op.create_table(
        "authenticity_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("restaurant_id", sa.Integer(), nullable=False),
        sa.Column("authenticity_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("classification", sa.String(50), nullable=True),
        sa.Column("flagged_keywords", sa.Text(), nullable=True),
        sa.Column("model_version", sa.String(100), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"]),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_authenticity_scores_id", "authenticity_scores", ["id"])
    op.create_index("ix_authenticity_scores_review_id", "authenticity_scores", ["review_id"])
    op.create_index("ix_authenticity_scores_restaurant_id", "authenticity_scores", ["restaurant_id"])


def downgrade() -> None:
    op.drop_table("authenticity_scores")
    op.drop_table("reviews")
    op.drop_table("restaurants")
    op.drop_table("raw_documents")
    op.drop_table("sources")
