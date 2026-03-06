"""
Evaluation engine.
Manages multi-dimensional scoring, evidence linking, and export.
"""

import logging
from typing import List, Dict, Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import EvaluationScore, TranscriptEntry
from app.services.copilot import DEFAULT_EVALUATION_FRAMEWORK, CopilotEngine

logger = logging.getLogger(__name__)


class EvaluationEngine:
    """Handles scoring, evidence linking, and coverage analysis."""

    def __init__(self, framework: Optional[Dict[str, Any]] = None):
        self.framework = framework or DEFAULT_EVALUATION_FRAMEWORK

    def get_dimensions(self) -> List[Dict[str, Any]]:
        """Return the flat list of all sub-dimensions with their parent info."""
        dims = []
        for dim in self.framework["dimensions"]:
            for sub in dim["sub_dimensions"]:
                dims.append({
                    "dimension": dim["name"],
                    "sub_dimension": sub["name"],
                    "weight": sub["weight"],
                })
        return dims

    async def get_coverage(self, db: AsyncSession, session_id: str) -> Dict[str, Any]:
        """Calculate which dimensions have scores and which are still gaps."""
        result = await db.execute(
            select(EvaluationScore).where(EvaluationScore.session_id == session_id)
        )
        scores = result.scalars().all()
        scored = {(s.dimension, s.sub_dimension): s.score for s in scores if s.score is not None}

        coverage = []
        total_weighted = 0.0
        max_weighted = 0.0
        gaps = []

        for dim in self.framework["dimensions"]:
            for sub in dim["sub_dimensions"]:
                key = (dim["name"], sub["name"])
                weight = sub["weight"]
                max_weighted += weight * 5
                if key in scored:
                    total_weighted += weight * scored[key]
                    coverage.append({**sub, "dimension": dim["name"], "score": scored[key], "status": "scored"})
                else:
                    gaps.append(f"{dim['name']} / {sub['name']}")
                    coverage.append({**sub, "dimension": dim["name"], "score": None, "status": "gap"})

        pct = round(total_weighted / max_weighted * 100, 1) if max_weighted else 0
        return {"coverage": coverage, "gaps": gaps, "weighted_total": round(total_weighted / max_weighted * 100) if max_weighted else 0, "completion_pct": pct}

    async def suggest_scores(
        self,
        db: AsyncSession,
        session_id: str,
        copilot: CopilotEngine,
    ) -> List[Dict[str, Any]]:
        """Ask copilot to suggest scores for dimensions with evidence but no score."""
        result = await db.execute(
            select(EvaluationScore).where(
                EvaluationScore.session_id == session_id,
                EvaluationScore.score.is_(None),
            )
        )
        unsored = result.scalars().all()
        suggestions = []
        for ev in unsored:
            if not ev.transcript_entry_ids:
                continue
            tr_result = await db.execute(
                select(TranscriptEntry).where(TranscriptEntry.id.in_(ev.transcript_entry_ids))
            )
            entries = tr_result.scalars().all()
            evidence = [f"[{e.speaker}] {e.text}" for e in entries]
            suggestion = await copilot.suggest_score(ev.dimension, ev.sub_dimension or "", evidence)
            suggestions.append({
                "dimension": ev.dimension,
                "sub_dimension": ev.sub_dimension,
                "evaluation_id": ev.id,
                **suggestion,
            })
        return suggestions

    def compute_decision(self, scores: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Given all scored dimensions, compute weighted total and hiring decision."""
        total = 0.0
        max_total = 0.0
        for dim in self.framework["dimensions"]:
            for sub in dim["sub_dimensions"]:
                w = sub["weight"]
                max_total += w * 5
                matched = [s for s in scores if s.get("dimension") == dim["name"] and s.get("sub_dimension") == sub["name"]]
                if matched and matched[0].get("score") is not None:
                    total += w * matched[0]["score"]

        normalised = round(total / max_total * 100) if max_total else 0
        rules = self.framework["decision_rules"]
        if normalised >= rules["strong_hire"]:
            decision = "strong_hire"
        elif normalised >= rules["proceed"]:
            decision = "proceed"
        elif normalised >= rules["borderline"]:
            decision = "borderline"
        else:
            decision = "no_hire"

        return {"weighted_score": normalised, "decision": decision}

    def export_markdown(self, session_data: Dict[str, Any], scores: List[Dict[str, Any]], decision: Dict[str, Any]) -> str:
        """Export a completed scorecard as Markdown."""
        lines = [
            f"# Interview Scorecard",
            f"",
            f"**Candidate**: {session_data.get('candidate_name', 'N/A')}",
            f"**Role**: {session_data.get('role_title', 'N/A')}",
            f"**Date**: {session_data.get('date', 'N/A')}",
            f"**Interviewer**: {session_data.get('interviewer', 'N/A')}",
            f"",
            f"## Scores",
            f"",
            f"| Dimension | Sub-dimension | Score | Evidence |",
            f"|-----------|---------------|-------|----------|",
        ]
        for s in scores:
            lines.append(f"| {s.get('dimension','')} | {s.get('sub_dimension','')} | {s.get('score', '-')}/5 | {s.get('evidence_note', '')} |")

        lines.extend([
            f"",
            f"## Decision",
            f"",
            f"- **Weighted Score**: {decision['weighted_score']}/100",
            f"- **Recommendation**: {decision['decision']}",
        ])
        return "\n".join(lines)
