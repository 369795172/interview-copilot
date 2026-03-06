"""
Interview session CRUD routes.
"""

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db_models import InterviewSession, Candidate, TranscriptEntry, EvaluationScore
from app.models.schemas import (
    SessionCreate, SessionOut,
    CandidateCreate, CandidateOut,
    TranscriptEntryOut,
)
from app.services.evaluation import EvaluationEngine

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


# ---- Candidates ----

@router.post("/candidates", response_model=CandidateOut)
async def create_candidate(body: CandidateCreate, db: AsyncSession = Depends(get_db)):
    c = Candidate(name=body.name, resume_path=body.resume_path)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


@router.get("/candidates", response_model=List[CandidateOut])
async def list_candidates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Candidate).order_by(Candidate.created_at.desc()))
    return result.scalars().all()


# ---- Sessions ----

@router.post("", response_model=SessionOut)
async def create_session(body: SessionCreate, db: AsyncSession = Depends(get_db)):
    session = InterviewSession(
        role_title=body.role_title,
        candidate_id=body.candidate_id,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("", response_model=List[SessionOut])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InterviewSession).order_by(InterviewSession.created_at.desc()))
    return result.scalars().all()


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    s = await db.get(InterviewSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    return s


@router.post("/{session_id}/start", response_model=SessionOut)
async def start_session(session_id: str, db: AsyncSession = Depends(get_db)):
    s = await db.get(InterviewSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    s.status = "active"
    s.started_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(s)
    return s


@router.post("/{session_id}/end", response_model=SessionOut)
async def end_session(session_id: str, db: AsyncSession = Depends(get_db)):
    s = await db.get(InterviewSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    s.status = "completed"
    s.ended_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(s)
    return s


@router.get("/{session_id}/transcript", response_model=List[TranscriptEntryOut])
async def get_transcript(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TranscriptEntry)
        .where(TranscriptEntry.session_id == session_id)
        .order_by(TranscriptEntry.start_time)
    )
    return result.scalars().all()


@router.get("/{session_id}/export")
async def export_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Export session transcript + scorecard as Markdown."""
    s = await db.get(InterviewSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")

    # Transcript
    tr_result = await db.execute(
        select(TranscriptEntry).where(TranscriptEntry.session_id == session_id).order_by(TranscriptEntry.start_time)
    )
    entries = tr_result.scalars().all()

    # Scores
    sc_result = await db.execute(
        select(EvaluationScore).where(EvaluationScore.session_id == session_id)
    )
    scores_raw = sc_result.scalars().all()
    scores = [{"dimension": sc.dimension, "sub_dimension": sc.sub_dimension, "score": sc.score, "evidence_note": sc.evidence_note} for sc in scores_raw]

    engine = EvaluationEngine()
    decision = engine.compute_decision(scores)

    candidate_name = ""
    if s.candidate_id:
        c = await db.get(Candidate, s.candidate_id)
        candidate_name = c.name if c else ""

    md = engine.export_markdown(
        {"candidate_name": candidate_name, "role_title": s.role_title, "date": str(s.created_at)[:10], "interviewer": s.interviewer_id or ""},
        scores,
        decision,
    )

    # Append transcript
    md += "\n\n## Transcript\n\n"
    for e in entries:
        mins = int(e.start_time // 60)
        secs = int(e.start_time % 60)
        md += f"**[{mins:02d}:{secs:02d}] {e.speaker}**: {e.text}\n\n"

    return {"markdown": md, "decision": decision}
