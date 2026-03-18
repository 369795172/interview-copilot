"""
LLM-based transcript refinement service.
Corrects STT errors, removes fillers, fixes punctuation.
"""

import logging
from typing import Optional

from openai import AsyncOpenAI

from app.config import settings
from app.prompts.transcript_refiner import TRANSCRIPT_REFINER_SYSTEM, TRANSCRIPT_REFINER_USER

logger = logging.getLogger(__name__)

_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.llm_api_key or "sk-placeholder",
            base_url=settings.llm_base_url,
            default_headers={
                "HTTP-Referer": "https://interview-copilot.local",
                "X-OpenRouter-Title": "Interview Copilot",
            },
        )
    return _client


class TranscriptRefiner:
    """Refines raw STT output via LLM to improve accuracy and readability."""

    @property
    def available(self) -> bool:
        return bool(settings.llm_refine_enabled and settings.llm_api_key)

    async def refine(self, raw_text: str) -> Optional[str]:
        """Refine raw transcript text. Returns refined text or None on failure."""
        if not raw_text or not raw_text.strip():
            return None
        if not self.available:
            return None

        try:
            client = _get_client()
            resp = await client.chat.completions.create(
                model=settings.llm_refine_model,
                messages=[
                    {"role": "system", "content": TRANSCRIPT_REFINER_SYSTEM},
                    {"role": "user", "content": TRANSCRIPT_REFINER_USER.format(raw_text=raw_text)},
                ],
                temperature=0.2,
                max_tokens=2048,
            )
            refined = (resp.choices[0].message.content or "").strip()
            if not refined:
                return None
            return refined
        except Exception as e:
            logger.warning("Transcript refinement failed: %s", e)
            return None
