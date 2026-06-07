import asyncio
import json
import logging
import hashlib
from datetime import datetime, timezone
from typing import Optional

from app.config import settings
from app.llm.base import LLMBackend, LLMResponse, LLMProvider

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-20250514"
CLAUDE_PRICING_INPUT_PER_1K = 0.003
CLAUDE_PRICING_OUTPUT_PER_1K = 0.015

CACHE_SYSTEM_PROMPTS = {
    "dish_rec": """You are a local food expert for Southeast Asian cuisine. You give dish recommendations backed by authentic local reviews. Always cite specific reviewer quotes. Tone: excited food traveler sharing a secret. Output valid JSON only.""",
    "gem_summary": """You are a food travel writer specializing in hidden gem restaurants. Write 2-3 sentence summaries explaining why a restaurant is a hidden gem. Must cite specific phrases from authentic reviews. Never use marketing language. Output valid JSON only.""",
    "trust_audit": """You are a fraud analyst specializing in restaurant review authenticity. Analyze review patterns to detect fake reviews, KOL sponsorships, and tourist traps. Output valid JSON only with trust_score (0-100), red_flags list, and recommendation.""",
    "menu_translate": """You are a multilingual menu translator specializing in Southeast Asian cuisine. Translate menu items with cultural context, explain unfamiliar ingredients, flag common allergens, and mark popular items based on local knowledge. Output valid JSON only.""",
}


class ClaudeBackend(LLMBackend):
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.anthropic_api_key
        self._client = None
        self._cache: dict[str, tuple[float, LLMResponse]] = {}
        self._daily_cost = 0.0
        self._daily_start = datetime.now(timezone.utc).date()

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.CLAUDE

    def _get_client(self):
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                logger.warning("anthropic package not installed")
        return self._client

    def _check_daily_cost(self):
        today = datetime.now(timezone.utc).date()
        if today != self._daily_start:
            self._daily_cost = 0.0
            self._daily_start = today
        if self._daily_cost >= settings.max_llm_daily_cost_usd:
            raise RuntimeError(f"Daily LLM budget exceeded: ${settings.max_llm_daily_cost_usd}")

    def _track_cost(self, input_tokens: int, output_tokens: int):
        cost = (input_tokens / 1000) * CLAUDE_PRICING_INPUT_PER_1K + (output_tokens / 1000) * CLAUDE_PRICING_OUTPUT_PER_1K
        self._daily_cost += cost

    def _get_cache_key(self, prompt: str, system_prompt: str = "") -> str:
        return hashlib.md5(f"{system_prompt}:::{prompt}".encode()).hexdigest()[:16]

    def _get_cached(self, cache_key: str) -> Optional[LLMResponse]:
        if cache_key in self._cache:
            cached_at, response = self._cache[cache_key]
            if (datetime.now(timezone.utc).timestamp() - cached_at) < settings.llm_cache_ttl_seconds:
                return response
            del self._cache[cache_key]
        return None

    async def complete(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.7,
                       system_prompt: str = "") -> LLMResponse:
        self._check_daily_cost()
        cache_key = self._get_cache_key(prompt, system_prompt)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        client = self._get_client()
        if client is None:
            raise RuntimeError("Anthropic client not available")

        try:
            kwargs = {
                "model": CLAUDE_MODEL,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system_prompt:
                kwargs["system"] = system_prompt
                kwargs["system"] = [
                    {"type": "text", "text": system_prompt,
                     "cache_control": {"type": "ephemeral"}}
                ]

            response = await asyncio.wait_for(
                client.messages.create(**kwargs),
                timeout=settings.llm_request_timeout_seconds,
            )
            text = response.content[0].text if response.content else ""
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            self._track_cost(input_tokens, output_tokens)
            result = LLMResponse(
                text=text,
                provider=LLMProvider.CLAUDE,
                tokens_used=input_tokens + output_tokens,
                cost_usd=round(self._daily_cost, 4),
            )
            self._cache[cache_key] = (datetime.now(timezone.utc).timestamp(), result)
            return result
        except asyncio.TimeoutError:
            raise RuntimeError(f"Claude API timeout after {settings.llm_request_timeout_seconds}s")
        except Exception as e:
            raise RuntimeError(f"Claude API error: {e}")

    async def complete_structured(self, prompt: str, schema: dict, max_tokens: int = 1024,
                                  system_prompt: str = "dish_rec") -> dict:
        full_prompt = f"{prompt}\n\nRespond with a valid JSON object matching this schema:\n{json.dumps(schema, indent=2)}"
        sys_prompt = CACHE_SYSTEM_PROMPTS.get(system_prompt, CACHE_SYSTEM_PROMPTS["dish_rec"]) if system_prompt in CACHE_SYSTEM_PROMPTS else system_prompt
        try:
            response = await self.complete(full_prompt, max_tokens=max_tokens, temperature=0.3, system_prompt=sys_prompt)
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            return json.loads(text.strip())
        except json.JSONDecodeError:
            logger.warning("Claude structured output not valid JSON, returning empty dict")
            return {}
        except Exception:
            return {}

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        prompt = f"Translate this text from {source_lang} to {target_lang}. Preserve cultural context for food items:\n\n{text}"
        response = await self.complete(prompt, max_tokens=1024, temperature=0.3,
                                        system_prompt=CACHE_SYSTEM_PROMPTS["menu_translate"])
        return response.text
