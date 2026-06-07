from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, AsyncIterator
from enum import Enum


class LLMProvider(str, Enum):
    CLAUDE = "claude"
    GPT4O = "gpt-4o"
    OLLAMA = "ollama"


@dataclass
class LLMResponse:
    text: str
    provider: LLMProvider
    tokens_used: int
    cost_usd: float


class LLMBackend(ABC):
    @abstractmethod
    async def complete(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.7) -> LLMResponse:
        ...

    @abstractmethod
    async def complete_structured(self, prompt: str, schema: dict, max_tokens: int = 1024) -> dict:
        ...

    @abstractmethod
    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        ...

    @property
    @abstractmethod
    def provider(self) -> LLMProvider:
        ... 
