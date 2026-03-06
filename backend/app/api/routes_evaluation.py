"""
Evaluation CRUD and AI-assisted scoring routes.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db_models import EvaluationScore
from app.models.schemas import EvaluationScoreCreate, EvaluationScoreUpdate, EvaluationScoreOut
from app.services.evaluation import EvaluationEngine
from app.services.copilot import CopilotEngine
from app.api.ws_interview import active_copilots

router = APIRouter(prefix="/api/sessions/{session_id}/evaluation", tags=["evaluation"])


@router.get("/dimensions")
async def get_dimensions():
    engine = EvaluationEngine()
    return {"dimensions": engine.get_dimensions()}


@router.get("/coverage")
async def get_coverage(session_id: str, db: AsyncSession = Depends(get_db)):
    engine = EvaluationEngine()
    return await engine.get_coverage(db, session_id)


@router.post("/scores", response_model=EvaluationScoreOut)
async def create_score(session_id: str, body: EvaluationScoreCreate, db: AsyncSession = Depends(get_db)):
    ev = EvaluationScore(
        session_id=session_id,
        dimension=body.dimension,
        sub_dimension=body.sub_dimension,
        score=body.score,
        evidence_note=body.evidence_note,
        transcript_entry_ids=body.transcript_entry_ids,
    )
    db.add(ev)
    await db.commit()
    await db.refresh(ev)
    return ev


@router.put("/scores/{score_id}", response_model=EvaluationScoreOut)
async def update_score(session_id: str, score_id: str, body: EvaluationScoreUpdate, db: AsyncSession = Depends(get_db)):
    ev = await db.get(EvaluationScore, score_id)
    if not ev or ev.session_id != session_id:
        raise HTTPException(404, "Score not found")
    if body.score is not None:
        ev.score = body.score
    if body.evidence_note is not None:
        ev.evidence_note = body.evidence_note
    if body.transcript_entry_ids is not None:
        ev.transcript_entry_ids = body.transcript_entry_ids
    await db.commit()
    await db.refresh(ev)
    return ev


@router.get("/scores", response_model=List[EvaluationScoreOut])
async def list_scores(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(EvaluationScore).where(EvaluationScore.session_id == session_id)
    )
    return result.scalars().all()


@router.post("/suggest")
async def suggest_scores(session_id: str, db: AsyncSession = Depends(get_db)):
    copilot = active_copilots.get(session_id) or CopilotEngine()
    engine = EvaluationEngine()
    suggestions = await engine.suggest_scores(db, session_id, copilot)
    return {"suggestions": suggestions}


@router.get("/decision")
async def get_decision(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(EvaluationScore).where(EvaluationScore.session_id == session_id)
    )
    scores_raw = result.scalars().all()
    scores = [{"dimension": s.dimension, "sub_dimension": s.sub_dimension, "score": s.score, "evidence_note": s.evidence_note} for s in scores_raw]
    engine = EvaluationEngine()
    return engine.compute_decision(scores)
