import json
import logging
import hashlib
import time
from typing import Optional

import redis

from app.config import settings
from app.llm.base import LLMBackend, LLMResponse, LLMProvider
from app.llm.backends import ClaudeBackend, GPT4Backend, OllamaBackend

logger = logging.getLogger(__name__)


class CostTracker:
    def __init__(self):
        self._daily_costs: dict[str, float] = {}
        self._request_counts: dict[str, int] = {}
        self._redis = None
        self._init_redis()

    def _init_redis(self):
        try:
            self._redis = redis.from_url(settings.redis_url, decode_responses=True)
            self._redis.ping()
        except Exception:
            self._redis = None

    def record(self, provider: str, cost_usd: float, tokens: int):
        self._daily_costs[provider] = self._daily_costs.get(provider, 0) + cost_usd
        self._request_counts[provider] = self._request_counts.get(provider, 0) + 1
        if self._redis:
            try:
                day_key = f"llm:cost:{time.strftime('%Y-%m-%d')}"
                self._redis.hincrbyfloat(day_key, provider, cost_usd)
                self._redis.hincrby(f"llm:requests:{time.strftime('%Y-%m-%d')}", provider, 1)
            except Exception:
                pass

    def get_daily_stats(self) -> dict:
        return {
            "costs": dict(self._daily_costs),
            "total_cost": round(sum(self._daily_costs.values()), 4),
            "requests": dict(self._request_counts),
            "total_requests": sum(self._request_counts.values()),
            "budget_limit": settings.max_llm_daily_cost_usd,
            "budget_remaining": round(settings.max_llm_daily_cost_usd - sum(self._daily_costs.values()), 4),
        }

    def is_budget_exceeded(self) -> bool:
        return sum(self._daily_costs.values()) >= settings.max_llm_daily_cost_usd


class LLMRouter:
    def __init__(self):
        self._backends: list[LLMBackend] = []
        self.cost_tracker = CostTracker()
        self._init_backends()
        self._redis_cache = None
        self._init_redis_cache()

    def _init_redis_cache(self):
        try:
            self._redis_cache = redis.from_url(settings.redis_url, decode_responses=True)
            self._redis_cache.ping()
        except Exception:
            self._redis_cache = None

    def _init_backends(self):
        chain = [settings.llm_primary] + [
            b.strip() for b in settings.llm_fallback_chain.split(",") if b.strip()
        ]

        for name in chain:
            if name == "claude" and settings.anthropic_api_key:
                self._backends.append(ClaudeBackend(api_key=settings.anthropic_api_key))
            elif name == "gpt-4o" and settings.openai_api_key:
                self._backends.append(GPT4Backend(api_key=settings.openai_api_key))
            elif name == "ollama-llama3":
                self._backends.append(OllamaBackend(
                    base_url=settings.ollama_base_url,
                    model="llama3:8b",
                ))

        if not self._backends:
            logger.warning("No LLM backends configured. Using Ollama fallback.")
            self._backends.append(OllamaBackend(
                base_url=settings.ollama_base_url,
                model="llama3:8b",
            ))

    def _get_redis_cache_key(self, prefix: str, *args) -> str:
        raw = f"{prefix}:{'::'.join(str(a) for a in args)}"
        return f"llm:cache:{hashlib.md5(raw.encode()).hexdigest()[:16]}"

    def _get_redis_cached(self, key: str) -> Optional[str]:
        if self._redis_cache is None:
            return None
        try:
            return self._redis_cache.get(key)
        except Exception:
            return None

    def _set_redis_cache(self, key: str, value: str, ttl: int = None):
        if self._redis_cache is None:
            return
        try:
            self._redis_cache.setex(key, ttl or settings.llm_cache_ttl_seconds, value)
        except Exception:
            pass

    def _tiered_route(self, task_type: str) -> list[LLMBackend]:
        simple_tasks = {"translate_menu_simple", "classify_language"}
        if task_type in simple_tasks:
            ollama_backend = [b for b in self._backends if isinstance(b, OllamaBackend)]
            other_backends = [b for b in self._backends if not isinstance(b, OllamaBackend)]
            return ollama_backend + other_backends
        return self._backends

    async def complete(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.7,
                       task_type: str = "general") -> LLMResponse:
        if self.cost_tracker.is_budget_exceeded():
            ollama = [b for b in self._backends if isinstance(b, OllamaBackend)]
            if ollama:
                logger.warning("Budget exceeded, using Ollama only")
                return await ollama[0].complete(prompt, max_tokens, temperature)
            raise RuntimeError("LLM budget exceeded and no Ollama fallback available")

        backends = self._tiered_route(task_type)
        for backend in backends:
            try:
                result = await asyncio_complete(backend, prompt, max_tokens, temperature)
                self.cost_tracker.record(backend.provider.value, result.cost_usd, result.tokens_used)
                logger.debug(f"LLM served by {backend.provider}")
                return result
            except Exception as e:
                logger.warning(f"Backend {backend.provider} failed: {e}")
                continue
        raise RuntimeError("All LLM backends exhausted")

    async def complete_structured(self, prompt: str, schema: dict, max_tokens: int = 1024,
                                  task_type: str = "general") -> dict:
        cache_key = self._get_redis_cache_key("structured", prompt, json.dumps(schema))
        cached = self._get_redis_cached(cache_key)
        if cached:
            try:
                return json.loads(cached)
            except json.JSONDecodeError:
                pass

        backends = self._tiered_route(task_type)
        for backend in backends:
            try:
                result = await backend.complete_structured(prompt, schema, max_tokens)
                self._set_redis_cache(cache_key, json.dumps(result))
                return result
            except Exception as e:
                logger.warning(f"Backend {backend.provider} structured completion failed: {e}")
                continue
        raise RuntimeError("All LLM backends exhausted")

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        cache_key = self._get_redis_cache_key("translate", text, source_lang, target_lang)
        cached = self._get_redis_cached(cache_key)
        if cached:
            return cached

        backends = self._tiered_route("translate_menu_simple")
        for backend in backends:
            try:
                result = await backend.translate(text, source_lang, target_lang)
                self._set_redis_cache(cache_key, result)
                return result
            except Exception as e:
                logger.warning(f"Backend {backend.provider} translation failed: {e}")
                continue
        return text

    async def dish_recommendations(self, restaurant_name: str, reviews: list[str], preferences: dict) -> str:
        cache_key = self._get_redis_cache_key("dish_rec", restaurant_name, json.dumps(preferences))
        cached = self._get_redis_cached(cache_key)
        if cached:
            return cached

        prompt = _build_dish_rec_prompt(restaurant_name, reviews, preferences)
        response = await self.complete(prompt, max_tokens=512, task_type="recommendation")
        self._set_redis_cache(cache_key, response.text)
        return response.text

    async def hidden_gem_summary(self, restaurant_name: str, reviews: list[str], signals: dict) -> str:
        cache_key = self._get_redis_cache_key("gem_summary", restaurant_name)
        cached = self._get_redis_cached(cache_key)
        if cached:
            return cached

        prompt = _build_gem_summary_prompt(restaurant_name, reviews, signals)
        response = await self.complete(prompt, max_tokens=256, task_type="summary")
        self._set_redis_cache(cache_key, response.text)
        return response.text

    async def trust_audit(self, restaurant_name: str, review_data: dict) -> dict:
        cache_key = self._get_redis_cache_key("trust_audit", restaurant_name)
        cached = self._get_redis_cached(cache_key)
        if cached:
            try:
                return json.loads(cached)
            except json.JSONDecodeError:
                pass

        prompt = _build_trust_audit_prompt(restaurant_name, review_data)
        schema = {
            "type": "object",
            "properties": {
                "trust_score": {"type": "integer", "minimum": 0, "maximum": 100},
                "red_flags": {"type": "array", "items": {"type": "string"}},
                "recommendation": {"type": "string"},
            },
            "required": ["trust_score", "red_flags", "recommendation"],
        }
        result = await self.complete_structured(prompt, schema, task_type="trust_audit")
        self._set_redis_cache(cache_key, json.dumps(result))
        return result


async def asyncio_complete(backend: LLMBackend, prompt: str, max_tokens: int, temperature: float) -> LLMResponse:
    import asyncio
    return await asyncio.wait_for(
        backend.complete(prompt, max_tokens, temperature),
        timeout=settings.llm_request_timeout_seconds,
    )


def _build_dish_rec_prompt(name: str, reviews: list[str], prefs: dict) -> str:
    return f"""Given these authentic local reviews about {name}:
{chr(10).join(reviews[:5])}

User preferences: {json.dumps(prefs)}

Recommend the top 3 dishes to order. For each dish:
- Name in local language + translation
- Why locals love it (cite specific review language)
- Approximate price
- Any ordering tips"""


def _build_gem_summary_prompt(name: str, reviews: list[str], signals: dict) -> str:
    return f"""Write a 2-3 sentence summary explaining why {name} is a hidden gem.
Local ratio: {signals.get('local_ratio', 'unknown')}
Authenticity signals: {signals.get('authenticity', 'unknown')}
Cite specific phrases from:
{chr(10).join(reviews[:3])}"""


def _build_trust_audit_prompt(name: str, data: dict) -> str:
    return f"""Analyze review patterns for {name}:
Review distribution: {data.get('review_distribution', 'unknown')}
Rating timeline: {data.get('rating_timeline', 'unknown')}
Language patterns: {data.get('language_patterns', 'unknown')}

Output trust_score (0-100), red_flags list, and recommendation."""


llm_router = LLMRouter()
