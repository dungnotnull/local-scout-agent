#!/usr/bin/env python3
"""Local Scout Agent — CLI Interface

Usage:
    python -m app.cli scout --lat 10.7769 --lon 106.7009 --radius 3
    python -m app.cli search "best pho local district 1"
    python -m app.cli translate "phở bò tái chín"
    python -m app.cli audit https://maps.app.goo.gl/example
    python -m app.cli benchmark
    python -m app.cli stats
    python -m app.cli init-db
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))


def main():
    parser = argparse.ArgumentParser(
        description="Local Scout Agent — AI-powered guide to authentic local dining",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    scout_parser = subparsers.add_parser("scout", help="Trigger area crawl")
    scout_parser.add_argument("--lat", type=float, required=True, help="Latitude")
    scout_parser.add_argument("--lon", type=float, required=True, help="Longitude")
    scout_parser.add_argument("--radius", type=float, default=3.0, help="Radius in km (default: 3)")
    scout_parser.add_argument("--force", action="store_true", help="Force refresh")

    subparsers.add_parser("search", help="Search restaurants").add_argument(
        "query", nargs="?", default="", help="Search query"
    )
    subparsers.add_parser("search").add_argument("--lat", type=float, default=10.7769)
    subparsers.add_parser("search").add_argument("--lon", type=float, default=106.7009)
    subparsers.add_parser("search").add_argument("--radius", type=float, default=3.0)
    subparsers.add_parser("search").add_argument("--min-gem", type=int, default=0)

    translate_parser = subparsers.add_parser("translate", help="Translate menu text")
    translate_parser.add_argument("text", nargs="+", help="Text to translate")
    translate_parser.add_argument("--from", dest="source_lang", default=None)
    translate_parser.add_argument("--to", dest="target_lang", default="en")

    audit_parser = subparsers.add_parser("audit", help="Trust audit for a restaurant URL")
    audit_parser.add_argument("url", help="Restaurant URL to audit")

    subparsers.add_parser("benchmark", help="Run model benchmarks")
    subparsers.add_parser("stats", help="Show database statistics")
    subparsers.add_parser("init-db", help="Initialize database")

    args = parser.parse_args()

    if args.command == "scout":
        asyncio.run(cmd_scout(args.lat, args.lon, args.radius, args.force))
    elif args.command == "search":
        asyncio.run(cmd_search(args.query, args.lat, args.lon, args.radius, args.min_gem))
    elif args.command == "translate":
        asyncio.run(cmd_translate(" ".join(args.text), args.source_lang, args.target_lang))
    elif args.command == "audit":
        asyncio.run(cmd_audit(args.url))
    elif args.command == "benchmark":
        cmd_benchmark()
    elif args.command == "stats":
        cmd_stats()
    elif args.command == "init-db":
        from scripts.init_db import init_db
        init_db()
        print("Database initialized.")
    else:
        parser.print_help()


async def cmd_scout(lat: float, lon: float, radius: float, force: bool):
    print(f"\n\U0001f50d Scouting area: ({lat}, {lon}) within {radius}km...\n")
    from app.crawler.area_crawler import AreaCrawlJob

    job = AreaCrawlJob(lat=lat, lon=lon, radius_km=radius)
    stats = await job.run()

    print(f"{'='*60}")
    print(f"  Results: {stats.get('fetched', 0)} fetched, {stats.get('new_documents', 0)} new")
    print(f"  Skipped: {stats.get('skipped_duplicate', 0)} duplicates, "
          f"{stats.get('blocked_robots', 0)} blocked by robots.txt")
    print(f"  Errors:  {stats.get('errors', 0)}")
    print(f"  Time:    {stats.get('elapsed_seconds', 0):.1f}s")
    print(f"{'='*60}\n")


async def cmd_search(query: str, lat: float, lon: float, radius: float, min_gem: int):
    from app.api.routes.restaurants import list_restaurants
    from app.database import SessionLocal

    print(f"\n\U0001f50d Searching: \"{query or 'all restaurants'}\" near ({lat}, {lon})\n")

    db = SessionLocal()
    try:
        result = list_restaurants(
            lat=lat, lon=lon, radius_km=radius, min_gem_score=min_gem if min_gem > 0 else None,
            query=query, page=1, page_size=20, db=db,
        )
        restaurants = result.restaurants

        if not restaurants:
            print("  No restaurants found. Try scouting the area first with: scout --lat {} --lon {}".format(lat, lon))
            return

        print(f"  Found {result.total} restaurant(s)\n")
        print(f"  {'Name':<30} {'Gem':>6} {'Dist':>6} {'Cuisine':<15} {'Price':<10}")
        print(f"  {'-'*30} {'-'*6} {'-'*6} {'-'*15} {'-'*10}")

        for r in restaurants:
            gem = f"{r.gem_score:.0f}" if r.gem_score is not None else "--"
            dist = f"{r.distance_km:.1f}km" if r.distance_km is not None else "--"
            cuisine = r.cuisine_type or "--"
            price = r.price_range or "--"
            print(f"  {r.name[:28]:<30} {gem:>6} {dist:>6} {cuisine[:13]:<15} {price[:8]:<10}")
    finally:
        db.close()
    print()


async def cmd_translate(text: str, source_lang: Optional[str], target_lang: str):
    print(f"\n\U0001f310 Translating...\n")
    from app.api.routes.translate import local_translate, detect_language, generate_cultural_notes

    lang = source_lang or detect_language(text)
    print(f"  Detected language: {lang}")
    translated = local_translate(text, lang, target_lang)
    print(f"\n  Original:   {text}")
    print(f"  Translated: {translated}")

    notes = generate_cultural_notes(text, lang)
    if notes:
        print(f"\n  \U0001f4d6 Cultural Notes:")
        for note in notes:
            print(f"    • {note}")
    print()


async def cmd_audit(url: str):
    print(f"\n\U0001f50e Auditing: {url}\n")
    import httpx
    from app.api.routes.trust import TrustAuditRequest

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "http://localhost:8000/api/v1/trust-audit",
                json={"url": url},
            )
            if response.status_code == 200:
                data = response.json()
                print(f"  Trust Score: {data['trust_score']}/100")
                print(f"  Recommendation: {data['recommendation']}")
                if data.get("red_flags"):
                    print(f"\n  \U0001f6a9 Red Flags:")
                    for flag in data["red_flags"]:
                        print(f"    • {flag}")
                if data.get("green_flags"):
                    print(f"\n  \u2705 Green Flags:")
                    for flag in data["green_flags"]:
                        print(f"    • {flag}")
            else:
                print(f"  Error: {response.status_code} — {response.text}")
    except Exception as e:
        print(f"  Error connecting to server: {e}")
        print(f"  (Make sure the API server is running: uvicorn app.main:app)")
    print()


def cmd_benchmark():
    print("\n\U0001f4ca Running model benchmarks...\n")
    from scripts.benchmark_models import run_benchmarks
    run_benchmarks()


def cmd_stats():
    print("\n\U0001f4ca Database Statistics\n")
    from app.database import SessionLocal
    from app.models.models import Restaurant, Review, RawDocument, AuthenticityScore, Source
    from sqlalchemy import func

    db = SessionLocal()
    try:
        stats = {
            "Sources": db.query(func.count(Source.id)).scalar(),
            "Raw Documents": db.query(func.count(RawDocument.id)).scalar(),
            "Restaurants": db.query(func.count(Restaurant.id)).scalar(),
            "Reviews": db.query(func.count(Review.id)).scalar(),
            "Authenticity Scores": db.query(func.count(AuthenticityScore.id)).scalar(),
        }
        print(f"  {'Metric':<25} {'Count':>8}")
        print(f"  {'-'*25} {'-'*8}")
        for label, count in stats.items():
            print(f"  {label:<25} {count or 0:>8}")

        avg_gem = db.query(func.avg(Restaurant.gem_score)).filter(Restaurant.gem_score.isnot(None)).scalar()
        print(f"\n  Average Gem Score: {avg_gem:.1f}" if avg_gem else "\n  Average Gem Score: --")

        active_sources = db.query(Source).filter(Source.is_active == True).all()
        if active_sources:
            print(f"\n  Active Sources:")
            for s in active_sources:
                print(f"    • {s.name} ({s.source_type})")
    finally:
        db.close()
    print()


if __name__ == "__main__":
    main()
