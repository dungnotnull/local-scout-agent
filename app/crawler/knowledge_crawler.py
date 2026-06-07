import asyncio
import hashlib
import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

ARXIV_API_BASE = "https://export.arxiv.org/api/query"
ARXIV_QUERIES = [
    "fake review detection multilingual",
    "restaurant recommendation authenticity",
    "tourist trap machine learning",
    "review spam social media Southeast Asia",
    "RAG retrieval augmented local search",
    "multilingual NER food domain",
    "local-tourist reviewer classification",
    "opinion spam behavioral signals",
]
ARXIV_CATEGORIES = ["cs.IR", "cs.CL", "cs.LG", "cs.SI"]

HUGGINGFACE_PAPERS_URL = "https://huggingface.co/papers"
HUGGINGFACE_API_BASE = "https://huggingface.co/api"
HUGGINGFACE_SEARCHES = [
    "fake review detection",
    "multilingual sentiment restaurant",
    "food NER multilingual",
    "tourist recommendation",
    "review authenticity",
]

PAPERS_WITH_CODE_BASE = "https://paperswithcode.com/api/v1"

RELEVANCE_THRESHOLD = 0.75
MAX_NEW_ENTRIES_PER_RUN = 20

CURRENT_MODELS = {
    "sentiment": "cardiffnlp/twitter-xlm-roberta-base-sentiment-multilingual",
    "ner": "dslim/bert-base-NER",
    "translation": "facebook/nllb-200-distilled-600M",
    "embeddings": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "classification": "microsoft/Phi-3-mini-4k-instruct",
}

KNOWLEDGE_BRAIN_PATH = Path(__file__).resolve().parent.parent.parent / "SECOND-KNOWLEDGE-BRAIN.md"


@dataclass
class Paper:
    title: str
    authors: list[str]
    year: Optional[int]
    venue: Optional[str]
    abstract: str
    url: str
    source: str
    relevance_score: float = 0.0
    relevance_note: str = ""


@dataclass
class ModelInfo:
    model_id: str
    name: str
    task: str
    benchmark: Optional[str]
    score: Optional[float]
    downloads: Optional[int]
    last_updated: Optional[str]


class KnowledgeCrawler:
    def __init__(self):
        self._embedding_pipeline = None
        self.project_description_embedding = None

    def _get_embedding_pipeline(self):
        if self._embedding_pipeline is None:
            from app.ml.embedding_pipeline import EmbeddingPipeline
            self._embedding_pipeline = EmbeddingPipeline()
            self._embedding_pipeline.load()
            project_desc = (
                "AI-powered travel companion for discovering authentic local restaurants "
                "by detecting fake reviews, filtering tourist traps, and surfacing hidden gems "
                "using multilingual NLP, RAG, and authenticity scoring from local forums and social media."
            )
            self.project_description_embedding = self._embedding_pipeline.encode(project_desc)
        return self._embedding_pipeline

    async def search_arxiv(self, query: str, max_results: int = 10) -> list[Paper]:
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
        }
        papers = []
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(ARXIV_API_BASE, params=params)
                response.raise_for_status()
                root = ET.fromstring(response.text)
                ns = {
                    "atom": "http://www.w3.org/2005/Atom",
                    "arxiv": "http://arxiv.org/schemas/atom",
                }
                for entry in root.findall("atom:entry", ns):
                    title = entry.find("atom:title", ns)
                    title_text = title.text.strip() if title is not None and title.text else ""
                    abstract = entry.find("atom:summary", ns)
                    abstract_text = abstract.text.strip() if abstract is not None and abstract.text else ""
                    authors = [
                        a.find("atom:name", ns).text.strip()
                        for a in entry.findall("atom:author", ns)
                        if a.find("atom:name", ns) is not None and a.find("atom:name", ns).text
                    ]
                    pdf_url = ""
                    for link in entry.findall("atom:link", ns):
                        if link.get("title") == "pdf":
                            pdf_url = link.get("href", "")
                            break
                    if not pdf_url:
                        id_url = entry.find("atom:id", ns)
                        pdf_url = (id_url.text if id_url is not None else "")

                    year = self._extract_year(title_text + " " + abstract_text)

                    papers.append(Paper(
                        title=title_text,
                        authors=authors,
                        year=year,
                        venue="arXiv",
                        abstract=abstract_text,
                        url=pdf_url,
                        source="arxiv",
                    ))
        except Exception as e:
            logger.warning(f"ArXiv search failed for '{query}': {e}")
        return papers

    async def search_all_arxiv(self) -> list[Paper]:
        all_papers = []
        for query in ARXIV_QUERIES:
            results = await self.search_arxiv(query)
            all_papers.extend(results)
        return self._deduplicate_papers(all_papers)

    async def check_huggingface_models(self) -> list[ModelInfo]:
        models = []
        for search in HUGGINGFACE_SEARCHES:
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    response = await client.get(
                        f"{HUGGINGFACE_API_BASE}/models",
                        params={"search": search, "sort": "downloads", "limit": 5},
                    )
                    response.raise_for_status()
                    data = response.json()
                    for item in data:
                        models.append(ModelInfo(
                            model_id=item.get("modelId", item.get("id", "")),
                            name=item.get("modelId", item.get("id", "")),
                            task=item.get("pipeline_tag", "unknown"),
                            benchmark=None,
                            score=None,
                            downloads=item.get("downloads"),
                            last_updated=item.get("lastModified"),
                        ))
            except Exception as e:
                logger.warning(f"HF model search failed for '{search}': {e}")
        return models

    async def check_papers_with_code(self) -> list[dict]:
        results = []
        tasks_to_check = ["fake-review-detection", "sentiment-analysis", "named-entity-recognition"]
        for task in tasks_to_check:
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    response = await client.get(
                        f"{PAPERS_WITH_CODE_BASE}/papers/",
                        params={"task": task, "items_per_page": 5},
                    )
                    if response.status_code == 200:
                        data = response.json()
                        results.extend(data.get("results", []))
            except Exception as e:
                logger.warning(f"PapersWithCode check failed for '{task}': {e}")
        return results

    def score_relevance(self, papers: list[Paper]) -> list[Paper]:
        pipeline = self._get_embedding_pipeline()
        if pipeline is None or self.project_description_embedding is None:
            return papers

        from numpy import dot
        from numpy.linalg import norm

        for paper in papers:
            text = f"{paper.title} {paper.abstract}"
            embedding = pipeline.encode(text)
            similarity = float(dot(embedding, self.project_description_embedding) / (
                norm(embedding) * norm(self.project_description_embedding) + 1e-9
            ))
            paper.relevance_score = round(similarity, 3)
        papers.sort(key=lambda p: p.relevance_score, reverse=True)
        return papers

    def _deduplicate_papers(self, papers: list[Paper]) -> list[Paper]:
        seen = set()
        unique = []
        for paper in papers:
            key = paper.title.lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(paper)
        return unique

    def _extract_year(self, text: str) -> Optional[int]:
        match = re.search(r'\b(20\d{2})\b', text)
        if match:
            return int(match.group(1))
        return None

    def scan_existing_entries(self) -> set[str]:
        existing = set()
        if KNOWLEDGE_BRAIN_PATH.exists():
            content = KNOWLEDGE_BRAIN_PATH.read_text(encoding="utf-8")
            for line in content.split("\n"):
                if line.startswith("|") and "|" in line[1:]:
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 2:
                        existing.add(parts[1].lower())
                match = re.search(r'\[([^\]]+)\]\(https?://[^\)]+\)', line)
                if match:
                    existing.add(match.group(1).lower())
        return existing

    def append_to_knowledge_brain(self, papers: list[Paper], date_stamp: str) -> int:
        existing_titles = self.scan_existing_entries()
        new_papers = [p for p in papers if p.title.lower() not in existing_titles]
        new_papers = new_papers[:MAX_NEW_ENTRIES_PER_RUN]

        if not new_papers:
            return 0

        lines = []
        lines.append(f"\n### {date_stamp} — Automated Crawl Addition")
        lines.append(f"**Added:** {len(new_papers)} new papers")
        lines.append("")
        lines.append("| Title | Authors | Year | Venue | Link | Relevance |")
        lines.append("|-------|---------|------|-------|------|-----------|")
        for paper in new_papers:
            authors_str = ", ".join(paper.authors[:3])
            if len(paper.authors) > 3:
                authors_str += " et al."
            lines.append(
                f"| {paper.title} | {authors_str} | {paper.year or '—'} | "
                f"{paper.venue or 'arXiv'} | [{paper.url}]({paper.url}) | "
                f"{paper.relevance_score} |"
            )

        with open(KNOWLEDGE_BRAIN_PATH, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        update_log = (
            f"### {date_stamp} — Automated Update\n"
            f"**Summary:** Knowledge crawler found {len(new_papers)} new relevant papers.\n"
            f"**Added entries:** {len(new_papers)}\n\n"
        )
        content = KNOWLEDGE_BRAIN_PATH.read_text(encoding="utf-8")
        log_section = "## Knowledge Update Log"
        if log_section in content:
            before, after = content.split(log_section, 1)
            KNOWLEDGE_BRAIN_PATH.write_text(
                before + log_section + "\n\n" + update_log + after.lstrip("\n"),
                encoding="utf-8",
            )
        else:
            with open(KNOWLEDGE_BRAIN_PATH, "a", encoding="utf-8") as f:
                f.write(f"\n{log_section}\n\n{update_log}\n")

        return len(new_papers)

    def check_model_improvements(self, hf_models: list[ModelInfo]) -> list[dict]:
        improvements = []
        for model_info in hf_models:
            if model_info.task == "text-classification":
                existing = CURRENT_MODELS.get("sentiment", "")
                if model_info.model_id != existing and model_info.downloads:
                    improvements.append({
                        "task": "sentiment_analysis",
                        "current": existing,
                        "candidate": model_info.model_id,
                        "downloads": model_info.downloads,
                        "recommendation": "Evaluate as potential replacement for sentiment model",
                    })
            elif model_info.task == "token-classification":
                existing = CURRENT_MODELS.get("ner", "")
                if model_info.model_id != existing and model_info.downloads:
                    improvements.append({
                        "task": "ner",
                        "current": existing,
                        "candidate": model_info.model_id,
                        "downloads": model_info.downloads,
                        "recommendation": "Evaluate as potential replacement for NER model",
                    })
        return improvements


knowledge_crawler = KnowledgeCrawler()
