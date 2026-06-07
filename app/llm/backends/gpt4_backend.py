import asyncio
import json
import logging
import hashlib
from datetime import datetime, timezone
from typing import Optional

from app.config import settings
from app.llm.base import LLMBackend, LLMResponse, LLMProvider

logger = logging.getLogger(__name__)

GPT4O_MODEL = "gpt-4o-2024-08-06"
GPT4O_PRICING_INPUT_PER_1K = 0.0025
GPT4O_PRICING_OUTPUT_PER_1K = 0.010


class GPT4Backend(LLMBackend):
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.openai_api_key
        self._client = None
        self._daily_cost = 0.0
        self._daily_start = datetime.now(timezone.utc).date()
        self._cache: dict[str, tuple[float, LLMResponse]] = {}

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.GPT4O

    def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                logger.warning("openai package not installed")
        return self._client

    def _check_daily_cost(self):
        today = datetime.now(timezone.utc).date()
        if today != self._daily_start:
            self._daily_cost = 0.0
            self._daily_start = today

    def _get_cache_key(self, prompt: str) -> str:
        return hashlib.md5(prompt.encode()).hexdigest()[:16]

    async def complete(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.7) -> LLMResponse:
        self._check_daily_cost()
        cache_key = self._get_cache_key(prompt)
        if cache_key in self._cache:
            cached_at, response = self._cache[cache_key]
            if (datetime.now(timezone.utc).timestamp() - cached_at) < settings.llm_cache_ttl_seconds:
                return response

        client = self._get_client()
        if client is None:
            raise RuntimeError("OpenAI client not available")

        retries = 3
        last_error = None
        for attempt in range(retries):
            try:
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=GPT4O_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=max_tokens,
                        temperature=temperature,
                    ),
                    timeout=settings.llm_request_timeout_seconds,
                )
                text = response.choices[0].message.content or ""
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens
                cost = (input_tokens / 1000) * GPT4O_PRICING_INPUT_PER_1K + (output_tokens / 1000) * GPT4O_PRICING_OUTPUT_PER_1K
                self._daily_cost += cost
                result = LLMResponse(
                    text=text,
                    provider=LLMProvider.GPT4O,
                    tokens_used=input_tokens + output_tokens,
                    cost_usd=round(self._daily_cost, 4),
                )
                self._cache[cache_key] = (datetime.now(timezone.utc).timestamp(), result)
                return result
            except asyncio.TimeoutError:
                last_error = RuntimeError(f"OpenAI timeout after {settings.llm_request_timeout_seconds}s")
            except Exception as e:
                last_error = e
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
        raise RuntimeError(f"OpenAI API error after {retries} retries: {last_error}")

    async def complete_structured(self, prompt: str, schema: dict, max_tokens: int = 1024) -> dict:
        client = self._get_client()
        if client is None:
            return {}
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=GPT4O_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=0.3,
                    response_format={"type": "json_object"},
                ),
                timeout=settings.llm_request_timeout_seconds,
            )
            text = response.choices[0].message.content or ""
            return json.loads(text)
        except json.JSONDecodeError:
            return {}
        except Exception:
            return {}

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        prompt = f"Translate the following text from {source_lang} to {target_lang}. Preserve food terminology and cultural context:\n\n{text}"
        response = await self.complete(prompt, max_tokens=1024, temperature=0.3)
        return response.text
