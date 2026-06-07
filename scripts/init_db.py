"""Initialize database schema and seed data.

Usage: python scripts/init_db.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import engine, Base
from app.models.models import (
    Source,
    RawDocument,
    Restaurant,
    Review,
    AuthenticityScore,
)


def init_db():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)

    print("Seeding source configurations...")
    from app.database import SessionLocal
    db = SessionLocal()

    sources = [
        {"name": "r/VietNam", "url_pattern": "reddit.com/r/VietNam", "source_type": "reddit"},
        {"name": "r/saigon", "url_pattern": "reddit.com/r/saigon", "source_type": "reddit"},
        {"name": "Foody.vn", "url_pattern": "foody.vn/ho-chi-minh", "source_type": "forum"},
        {"name": "r/SoutheastAsia", "url_pattern": "reddit.com/r/SoutheastAsia", "source_type": "reddit"},
    ]

    for src in sources:
        exists = db.query(Source).filter_by(name=src["name"]).first()
        if not exists:
            db.add(Source(**src))

    db.commit()
    db.close()
    print("Database initialized with source configurations.")


if __name__ == "__main__":
    init_db()
