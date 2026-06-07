import asyncio
import json
import logging
import hashlib
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.config import settings
from app.llm.base import LLMBackend, LLMResponse, LLMProvider

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_MODEL = "llama3:8b"


class OllamaBackend(LLMBackend):
    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or DEFAULT_OLLAMA_MODEL
        self._healthy = True
        self._last_health_check = 0.0

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.OLLAMA

    async def health_check(self) -> bool:
        now = datetime.now(timezone.utc).timestamp()
        if now - self._last_health_check < 30:
            return self._healthy
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                self._healthy = response.status_code == 200
        except Exception:
            self._healthy = False
        self._last_health_check = now
        return self._healthy

    async def _ensure_model(self):
        if not await self.health_check():
            raise RuntimeError(f"Ollama at {self.base_url} is not healthy")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": self.model},
                )
        except Exception:
            pass

    async def complete(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.7) -> LLMResponse:
        if not await self.health_check():
            raise RuntimeError("Ollama unavailable")

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
                "num_ctx": 4096,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=settings.llm_request_timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                text = data.get("response", "")
                eval_count = data.get("eval_count", 0)
                return LLMResponse(
                    text=text,
                    provider=LLMProvider.OLLAMA,
                    tokens_used=eval_count,
                    cost_usd=0.0,
                )
        except asyncio.TimeoutError:
            raise RuntimeError(f"Ollama timeout after {settings.llm_request_timeout_seconds}s")
        except Exception as e:
            raise RuntimeError(f"Ollama error: {e}")

    async def complete_structured(self, prompt: str, schema: dict, max_tokens: int = 1024) -> dict:
        full_prompt = f"""{prompt}

Respond with ONLY a valid JSON object matching this schema:
{json.dumps(schema, indent=2)}

JSON:"""
        response = await self.complete(full_prompt, max_tokens=max_tokens, temperature=0.2)
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        json_match = text.strip()
        try:
            return json.loads(json_match)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            return {}

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        prompt = f"Translate from {source_lang} to {target_lang}. Preserve food terms:\n\n{text}"
        response = await self.complete(prompt, max_tokens=1024, temperature=0.2)
        return response.text
