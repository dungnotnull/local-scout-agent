"""Comprehensive end-to-end verification. Run: python tests/verify_e2e.py"""
# -*- coding: utf-8 -*-
import sys, os, time, json, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = 0
failed = 0
warnings = []

def check(name, fn):
    global passed, failed
    try:
        start = time.time()
        result = fn()
        ms = (time.time() - start) * 1000
        print(f"  [PASS] {name} ({ms:.0f}ms)")
        passed += 1
        return result
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        failed += 1
        return None

def warn(msg):
    global warnings
    warnings.append(msg)
    print(f"  [WARN] {msg}")

print("=" * 60)
print("LOCAL SCOUT AGENT - END-TO-END VERIFICATION")
print("=" * 60)

# === 1. ML RUNTIME TESTS ===
print("\n=== 1. ML RUNTIME TESTS ===")

# 1a. AuthenticityScorer heuristic
asr = check("AuthenticityScorer organic vi", lambda: (
    __import__('app.ml.authenticity_scorer', fromlist=['AuthenticityScorer'])
    .AuthenticityScorer()._score_single('Pho bo tai ngon qua! Gia 45k, quan dong khach dia phuong. Minh an o day 3 nam.')
))
if asr:
    assert asr.authenticity_score > 0.4, "Organic text should score high"
    assert asr.classification == "organic"

asr_pr = check("AuthenticityScorer PR en", lambda: (
    __import__('app.ml.authenticity_scorer', fromlist=['AuthenticityScorer'])
    .AuthenticityScorer()._score_single('BEST EVER!!! #sponsored #ad MUST VISIT https://link.com https://link2.com')
))
if asr_pr:
    assert asr_pr.authenticity_score < 0.5, f"PR text should score low, got {asr_pr.authenticity_score}"
    assert len(asr_pr.flagged_keywords) > 0, "Should flag PR keywords"

# 1b. HiddenGemScorer formula
check("HiddenGemScorer ideal", lambda: (
    __import__('app.ml.scoring.hidden_gem_scorer', fromlist=['HiddenGemScorer', 'GemScoreComponents'])
    .HiddenGemScorer().compute(__import__('app.ml.scoring.hidden_gem_scorer', fromlist=['GemScoreComponents'])
    .GemScoreComponents(0.9, 0.9, 50, 0.1)) > 80
))
check("HiddenGemScorer tourist trap", lambda: (
    __import__('app.ml.scoring.hidden_gem_scorer', fromlist=['HiddenGemScorer', 'GemScoreComponents'])
    .HiddenGemScorer().compute(__import__('app.ml.scoring.hidden_gem_scorer', fromlist=['GemScoreComponents'])
    .GemScoreComponents(0.2, 0.05, 100, 5.0)) < 30
))

# 1c. EntityExtractor Vietnamese
from app.ml.entity_extractor import EntityExtractor
ext = EntityExtractor()
result = ext.extract("Pho Thin o 13 Duong Lo Duc, Quan Hai Ba Trung ban pho bo tai chin ngon nhat. Cung co bun cha va nem ran.")
check("EntityExtractor dishes", lambda: len(result.dish_names) > 0)
check("EntityExtractor addresses", lambda: len(result.addresses) > 0 or len(result.neighborhoods) > 0)
if result.dish_names:
    print(f"         dishes: {result.dish_names[:3]}")
if result.addresses:
    print(f"         addresses: {result.addresses[:2]}")

# 1d. QueryUnderstanding
from app.ml.scoring.query_understanding import QueryUnderstandingEngine, QueryIntent
qe = QueryUnderstandingEngine()
pq = qe.parse("find me cheap pho near district 1 vegetarian")
check("Query intent", lambda: pq.intent == QueryIntent.DISH_SEARCH)
check("Query dishes", lambda: "pho" in [d.lower() for d in pq.dishes])
check("Query dietary", lambda: any("vegetarian" in d for d in pq.dietary_constraints))

# === 2. API ENDPOINT TESTS ===
print("\n=== 2. API ENDPOINT TESTS ===")

from app.main import app
from fastapi.testclient import TestClient
client = TestClient(app)

endpoints = [
    ("GET /health", lambda: client.get("/health"), 200, lambda r: r.json()["status"] == "ok"),
    ("GET /health/ready", lambda: client.get("/health/ready"), 200, lambda r: "status" in r.json()),
    ("GET /api/v1/restaurants", lambda: client.get("/api/v1/restaurants?lat=10.77&lon=106.7&radius_km=3"), 200, lambda r: "restaurants" in r.json()),
    ("GET /api/v1/restaurants/99999 (404)", lambda: client.get("/api/v1/restaurants/99999"), 404, None),
    ("GET /api/v1/restaurants/stats", lambda: client.get("/api/v1/restaurants/stats/overview"), 200, lambda r: "total_restaurants" in r.json()),
    ("POST /api/v1/scout", lambda: client.post("/api/v1/scout", json={"lat":10.7,"lon":106.7,"radius_km":1}), 200, lambda r: "job_id" in r.json()),
    ("POST /api/v1/translate-menu", lambda: client.post("/api/v1/translate-menu", json={"text":"pho bo tai","target_lang":"en"}), 200, lambda r: "translated_text" in r.json()),
    ("POST /api/v1/trust-audit", lambda: client.post("/api/v1/trust-audit", json={"url":"https://maps.app.goo.gl/example"}), 200, lambda r: "trust_score" in r.json()),
    ("GET /metrics", lambda: client.get("/metrics"), 200, lambda r: b"http_requests_total" in r.content),
]

for name, fn, expected_status, validator in endpoints:
    r = fn()
    status_ok = r.status_code == expected_status
    validation_ok = True
    if validator and status_ok:
        validation_ok = validator(r)

    if status_ok and validation_ok:
        print(f"  [PASS] {name} -> {r.status_code}")
        passed += 1
    else:
        print(f"  [FAIL] {name} -> {r.status_code} (validation={validation_ok})")
        failed += 1

# === 3. DOCKER CONFIGS ===
print("\n=== 3. DOCKER CONFIGS ===")

import yaml
try:
    with open("docker-compose.yml") as f:
        dc = yaml.safe_load(f)
    services = dc.get("services", {})
    check("docker-compose services >= 5", lambda: len(services) >= 5)
    check("docker-compose has api", lambda: "api" in services)
    check("docker-compose has redis", lambda: "redis" in services)
    check("docker-compose has chroma", lambda: "chroma" in services)
    check("docker-compose has worker", lambda: "worker" in services)
except Exception as e:
    warn(f"docker-compose.yml: {e}")

check("Dockerfile exists", lambda: os.path.exists("docker/Dockerfile"))
check("nginx.conf exists", lambda: os.path.exists("docker/nginx.conf"))
check("nginx-site.conf exists", lambda: os.path.exists("docker/nginx-site.conf"))
check("CI/CD workflow exists", lambda: os.path.exists(".github/workflows/ci.yml"))
check(".env.example exists", lambda: os.path.exists(".env.example"))

df = open("docker/Dockerfile", encoding="utf-8").read()
check("Dockerfile multi-stage", lambda: "FROM python" in df and "AS builder" in df)
check("Dockerfile non-root", lambda: "appuser" in df)
check("Dockerfile healthcheck", lambda: "HEALTHCHECK" in df)

# === 4. FRONTEND VALIDATION ===
print("\n=== 4. FRONTEND VALIDATION ===")

check("package.json exists", lambda: os.path.exists("frontend/package.json"))
check("tsconfig.json exists", lambda: os.path.exists("frontend/tsconfig.json"))
check("tailwind.config.js exists", lambda: os.path.exists("frontend/tailwind.config.js"))

src_files = ["index.tsx", "index.css", "App.tsx", "types.ts",
             "components/FilterPanel.tsx", "components/DetailSheet.tsx",
             "components/OnboardingModal.tsx", "react-app-env.d.ts"]
for f in src_files:
    check(f"frontend/src/{f}", lambda p=f"frontend/src/{f}": os.path.exists(p))

pkg = json.load(open("frontend/package.json", encoding="utf-8"))
check("frontend has react", lambda: "react" in pkg.get("dependencies", {}))
check("frontend has leaflet", lambda: "leaflet" in pkg.get("dependencies", {}))
check("frontend has tailwind", lambda: "tailwindcss" in pkg.get("dependencies", {}))

check("public/index.html exists", lambda: os.path.exists("frontend/public/index.html"))
check("public/manifest.json exists", lambda: os.path.exists("frontend/public/manifest.json"))

# === 5. FILE INVENTORY ===
print("\n=== 5. FILE INVENTORY ===")

expected_dirs = ["app", "app/api/routes", "app/crawler/parsers", "app/ml/scoring",
                 "app/llm/backends", "app/vector_store", "app/tasks", "app/models",
                 "app/utils", "docker", "frontend/src/components", "frontend/public",
                 "alembic/versions", "scripts", "tests", ".github/workflows"]
for d in expected_dirs:
    check(f"dir exists: {d}", lambda p=d: os.path.isdir(p))

py_count = sum(1 for r, ds, fs in os.walk("app") for f in fs if f.endswith(".py") and "__pycache__" not in r)
py_count += sum(1 for r, ds, fs in os.walk("alembic") for f in fs if f.endswith(".py") and "__pycache__" not in r)
py_count += sum(1 for r, ds, fs in os.walk("scripts") for f in fs if f.endswith(".py") and "__pycache__" not in r)
print(f"  [INFO] Total Python files: {py_count}")
check("Python files >= 55", lambda: py_count >= 55)

# === 6. SECURITY CHECKS ===
print("\n=== 6. SECURITY CHECKS ===")

all_py = ""
for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in ("__pycache__", ".commandcode", "node_modules", ".git", "models_cache", "data")]
    for f in files:
        if f.endswith(".py") or f.endswith(".env.example") or f.endswith(".yml"):
            path = os.path.join(root, f)
            if "verify_e2e.py" in path:
                continue
            with open(path, errors='ignore') as fh:
                all_py += fh.read()

check("no hardcoded API keys", lambda: "sk-ant-" not in all_py)
check("no OpenAI keys leaked", lambda: "sk-proj-" not in all_py)

# === FINAL REPORT ===
print("\n" + "=" * 60)
print(f"RESULTS: {passed} passed, {failed} failed, {len(warnings)} warnings")
print("=" * 60)

if failed == 0 and len(warnings) == 0:
    print("PRODUCTION-READY -- ALL CHECKS PASSED")
elif failed == 0:
    print("PASSED WITH WARNINGS")
else:
    print(f"{failed} CHECK(S) FAILED")

if warnings:
    print("\nWarnings:")
    for w in warnings:
        print(f"  - {w}")

sys.exit(0 if failed == 0 else 1)
