import asyncio
import logging
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app
from app.crawler.knowledge_crawler import knowledge_crawler

logger = logging.getLogger(__name__)

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

HUGGINGFACE_SEARCHES = [
    "fake review detection",
    "multilingual sentiment restaurant",
    "food NER multilingual",
    "tourist recommendation",
]

RELEVANCE_THRESHOLD = 0.75
MAX_NEW_ENTRIES_PER_RUN = 20


@celery_app.task(bind=True, max_retries=1, time_limit=7200)
def run_knowledge_crawler(self):
    logger.info("Starting knowledge crawler run")
    try:
        papers = asyncio.run(knowledge_crawler.search_all_arxiv())
        logger.info(f"Knowledge crawler: found {len(papers)} papers from ArXiv")
        scored = knowledge_crawler.score_relevance(papers)
        relevant = [p for p in scored if p.relevance_score >= RELEVANCE_THRESHOLD]
        logger.info(f"Knowledge crawler: {len(relevant)} papers above relevance threshold")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        added = knowledge_crawler.append_to_knowledge_brain(relevant, today)
        logger.info(f"Knowledge crawler: appended {added} new entries to SECOND-KNOWLEDGE-BRAIN.md")
        return {"status": "completed", "papers_found": len(relevant), "new_entries": added}
    except Exception as e:
        logger.error(f"Knowledge crawler failed: {e}")
        return {"status": "failed", "error": str(e)}


@celery_app.task(bind=True, max_retries=1, time_limit=7200)
def check_model_improvements(self):
    logger.info("Checking for model improvements")
    try:
        hf_models = asyncio.run(knowledge_crawler.check_huggingface_models())
        logger.info(f"Model check: found {len(hf_models)} candidate models")
        improvements = knowledge_crawler.check_model_improvements(hf_models)
        if improvements:
            logger.info(f"Model check: {len(improvements)} potential upgrades found")
            for imp in improvements:
                logger.info(f"  [{imp['task']}] {imp['current']} -> {imp['candidate']} ({imp['recommendation']})")
        pwc_results = asyncio.run(knowledge_crawler.check_papers_with_code())
        logger.info(f"PapersWithCode: found {len(pwc_results)} results")
        return {
            "status": "completed",
            "hf_models_found": len(hf_models),
            "improvements_found": len(improvements),
            "improvements": improvements,
            "pwc_results": len(pwc_results),
        }
    except Exception as e:
        logger.error(f"Model improvement check failed: {e}")
        return {"status": "failed", "error": str(e)}
