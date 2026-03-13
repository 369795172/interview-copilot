"""
Core AI copilot engine.
Assembles interview context and generates real-time suggestions via LLM.
"""

import json
import logging
from typing import Optional, List, Dict, Any

from openai import AsyncOpenAI

from app.config import settings
from app.database import async_session
from app.models.db_models import CopilotLog
from app.prompts.copilot_system import (
    COPILOT_SYSTEM_PROMPT,
    QUESTION_GENERATOR_PROMPT,
    EVALUATION_ASSIST_PROMPT,
    OPENING_SUGGESTIONS_PROMPT,
)

logger = logging.getLogger(__name__)

# Default evaluation framework based on existing scorecard
DEFAULT_EVALUATION_FRAMEWORK: Dict[str, Any] = {
    "dimensions": [
        {
            "name": "技术能力",
            "weight": 0.40,
            "sub_dimensions": [
                {"name": "编码与框架", "weight": 0.10},
                {"name": "数据与性能", "weight": 0.10},
                {"name": "存量系统协作", "weight": 0.10},
                {"name": "工程质量", "weight": 0.10},
            ],
        },
        {
            "name": "AI 时代适应度",
            "weight": 0.25,
            "sub_dimensions": [
                {"name": "AI 使用策略", "weight": 0.10},
                {"name": "AI 输出校验", "weight": 0.10},
                {"name": "Prompt 与上下文", "weight": 0.05},
            ],
        },
        {
            "name": "性格稳定与职业可靠性",
            "weight": 0.20,
            "sub_dimensions": [
                {"name": "情绪稳定性", "weight": 0.10},
                {"name": "言行一致与诚信", "weight": 0.05},
                {"name": "稳定性与长期意愿", "weight": 0.05},
            ],
        },
        {
            "name": "软实力",
            "weight": 0.15,
            "sub_dimensions": [
                {"name": "沟通", "weight": 0.04},
                {"name": "自驱", "weight": 0.04},
                {"name": "迭代", "weight": 0.04},
                {"name": "格局", "weight": 0.03},
            ],
        },
    ],
    "decision_rules": {
        "strong_hire": 82,
        "proceed": 72,
        "borderline": 65,
    },
    "veto_items": [
        "关键经历明显失真且无法解释",
        "实操中完全无法独立判断 AI 输出",
        "情绪或沟通行为显著影响协作安全",
    ],
}


AVAILABLE_MODELS = [
    {"id": "deepseek/deepseek-chat-v3-0324", "name": "DeepSeek V3 (0324)", "tier": "recommended"},
    {"id": "anthropic/claude-sonnet-4", "name": "Claude Sonnet 4", "tier": "premium"},
    {"id": "openai/gpt-4.1-mini", "name": "GPT-4.1 Mini", "tier": "standard"},
    {"id": "google/gemini-2.5-flash", "name": "Gemini 2.5 Flash", "tier": "standard"},
    {"id": "deepseek/deepseek-r1", "name": "DeepSeek R1", "tier": "reasoning"},
    {"id": "openai/o4-mini", "name": "o4 Mini", "tier": "reasoning"},
    {"id": "anthropic/claude-3.5-haiku", "name": "Claude 3.5 Haiku", "tier": "fast"},
    {"id": "google/gemini-2.0-flash-001", "name": "Gemini 2.0 Flash", "tier": "fast"},
]


class CopilotEngine:
    """Real-time AI copilot that analyses transcript and suggests actions."""

    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None
        self.transcript_buffer: List[Dict[str, str]] = []
        self.covered_topics: Dict[str, int] = {}
        self.asked_questions: List[str] = []
        self.selected_model: Optional[str] = None

        # Populated during session setup
        self.company_values: str = ""
        self.project_background: str = ""
        self.candidate_profile: str = ""
        self.evaluation_framework: Dict[str, Any] = DEFAULT_EVALUATION_FRAMEWORK
        self.interviewer_memory: str = ""

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=settings.llm_api_key or "sk-placeholder",
                base_url=settings.llm_base_url,
                default_headers={
                    "HTTP-Referer": "https://interview-copilot.local",
                    "X-OpenRouter-Title": "Interview Copilot",
                },
            )
        return self._client

    @property
    def model(self) -> str:
        return self.selected_model or settings.llm_model

    @property
    def available(self) -> bool:
        return bool(settings.llm_api_key)

    def load_context(
        self,
        company_values: str = "",
        project_background: str = "",
        candidate_profile: str = "",
        evaluation_framework: Optional[Dict[str, Any]] = None,
        interviewer_memory: str = "",
    ):
        self.company_values = company_values
        self.project_background = project_background
        self.candidate_profile = candidate_profile
        if evaluation_framework:
            self.evaluation_framework = evaluation_framework
        self.interviewer_memory = interviewer_memory

    @property
    def has_context(self) -> bool:
        return bool(self.candidate_profile or self.company_values or self.project_background)

    @staticmethod
    def _parse_llm_json(raw: str, fallback: Any = None) -> Any:
        """Parse LLM output as JSON, stripping markdown fences and handling errors gracefully."""
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("LLM returned non-JSON (first 200 chars): %s", raw[:200])
            return fallback

    async def generate_opening_suggestions(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Generate opening questions and strategy from context alone (no transcript needed)."""
        if not self.available:
            logger.warning("Opening suggestions skipped: LLM not available")
            return []
        if not self.has_context:
            logger.warning("Opening suggestions skipped: no context (cv=%d, company=%d, project=%d)",
                           len(self.candidate_profile), len(self.company_values), len(self.project_background))
            return []

        prompt = OPENING_SUGGESTIONS_PROMPT.format(
            company_values=self.company_values[:3000] or "(not provided)",
            project_background=self.project_background[:3000] or "(not provided)",
            candidate_profile=self.candidate_profile[:4000] or "(not provided)",
            evaluation_framework=json.dumps(self.evaluation_framework, ensure_ascii=False)[:3000],
        )

        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=settings.llm_max_tokens,
            )
            raw = resp.choices[0].message.content or "[]"
            parsed = self._parse_llm_json(raw, fallback=[])
            if isinstance(parsed, dict):
                parsed = parsed.get("suggestions", [parsed])
            suggestions = parsed if isinstance(parsed, list) else [parsed]
            await self._log_llm_interaction(
                session_id=session_id,
                log_type="opening_suggestions",
                request_summary=prompt,
                response_content=suggestions,
            )
            logger.info("Generated %d opening suggestions", len(suggestions))
            return suggestions
        except Exception:
            logger.exception("Opening suggestions generation failed")
            return []

    def add_transcript(self, speaker: str, text: str):
        self.transcript_buffer.append({"speaker": speaker, "text": text})
        if speaker == "interviewer":
            self.asked_questions.append(text)

    def append_interviewer_memory(self, content: str):
        content = (content or "").strip()
        if not content:
            return
        if self.interviewer_memory:
            self.interviewer_memory = f"{self.interviewer_memory}\n{content}"
        else:
            self.interviewer_memory = content

    async def _log_llm_interaction(
        self,
        session_id: Optional[str],
        log_type: str,
        request_summary: str,
        response_content: Any,
    ) -> None:
        if not session_id:
            return
        try:
            payload = response_content if isinstance(response_content, str) else json.dumps(response_content, ensure_ascii=False)
            async with async_session() as db:
                db.add(
                    CopilotLog(
                        session_id=session_id,
                        log_type=log_type,
                        request_summary=request_summary[:1000],
                        response_content=payload[:8000],
                        model_used=self.model,
                    )
                )
                await db.commit()
        except Exception:
            logger.exception("Failed to persist copilot interaction log")

    def _recent_transcript_text(self, last_n: int = 20) -> str:
        entries = self.transcript_buffer[-last_n:]
        return "\n".join(f"[{e['speaker']}] {e['text']}" for e in entries)

    def _build_system_prompt(self) -> str:
        return COPILOT_SYSTEM_PROMPT.format(
            company_values=self.company_values[:2000] or "(not provided)",
            project_background=self.project_background[:2000] or "(not provided)",
            candidate_profile=self.candidate_profile[:2000] or "(not provided)",
            evaluation_framework=json.dumps(self.evaluation_framework, ensure_ascii=False)[:3000],
            interviewer_memory=self.interviewer_memory[:1000] or "(none)",
        )

    async def analyse(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Run copilot analysis on the current transcript and return suggestions."""
        if not self.available or len(self.transcript_buffer) < 2:
            return []

        system = self._build_system_prompt()
        user_msg = (
            f"Current transcript (last 20 exchanges):\n"
            f"{self._recent_transcript_text()}\n\n"
            f"Already-asked questions by interviewer:\n"
            f"{chr(10).join(self.asked_questions[-15:])}\n\n"
            f"Please provide your suggestions."
        )

        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )
            raw = resp.choices[0].message.content or "[]"
            parsed = self._parse_llm_json(raw, fallback=[])
            if isinstance(parsed, dict):
                parsed = parsed.get("suggestions", [parsed])
            suggestions = parsed if isinstance(parsed, list) else [parsed]
            await self._log_llm_interaction(
                session_id=session_id,
                log_type="analysis",
                request_summary=user_msg,
                response_content=suggestions,
            )
            return suggestions
        except Exception:
            logger.exception("Copilot analysis failed")
            return []

    async def suggest_questions(self, evaluation_gaps: List[str]) -> List[Dict[str, str]]:
        """Generate targeted follow-up questions for uncovered dimensions."""
        if not self.available:
            return []

        prompt = QUESTION_GENERATOR_PROMPT.format(
            recent_transcript=self._recent_transcript_text(10),
            evaluation_gaps=", ".join(evaluation_gaps),
            candidate_highlights=self.candidate_profile[:1000],
        )
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=1024,
            )
            raw = resp.choices[0].message.content or "[]"
            parsed = self._parse_llm_json(raw, fallback=[])
            if isinstance(parsed, dict):
                parsed = parsed.get("questions", [parsed])
            return parsed if isinstance(parsed, list) else [parsed]
        except Exception:
            logger.exception("Question generation failed")
            return []

    async def suggest_score(
        self,
        dimension: str,
        sub_dimension: str,
        evidence_segments: List[str],
    ) -> Dict[str, Any]:
        """Ask LLM to suggest a score for a given dimension based on evidence."""
        if not self.available:
            return {"suggested_score": None, "reasoning": "LLM not configured"}

        prompt = EVALUATION_ASSIST_PROMPT.format(
            dimension=dimension,
            sub_dimension=sub_dimension,
            evidence_segments="\n---\n".join(evidence_segments),
        )
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=512,
            )
            raw = resp.choices[0].message.content or "{}"
            result = self._parse_llm_json(raw, fallback={"suggested_score": None, "reasoning": "LLM returned non-JSON"})
            return result
        except Exception:
            logger.exception("Score suggestion failed")
            return {"suggested_score": None, "reasoning": "Analysis failed"}
