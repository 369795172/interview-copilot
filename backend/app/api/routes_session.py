"""
Interview session CRUD routes.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.db_models import (
    InterviewSession,
    Candidate,
    TranscriptEntry,
    EvaluationScore,
    AIInsight,
    CopilotLog,
)
from app.models.schemas import (
    SessionCreate, SessionOut,
    CandidateCreate, CandidateOut,
    TranscriptEntryOut,
    SessionHistoryItemOut,
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


@router.post("/{session_id}/audio/upload")
async def upload_session_audio(
    session_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload full recording for a session. Accepts WAV, MP3, OGG, WebM."""
    s = await db.get(InterviewSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")

    session_dir = Path(settings.upload_dir) / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename or "recording").suffix.lower() or ".wav"
    if ext not in (".wav", ".mp3", ".ogg", ".webm", ".opus"):
        ext = ".wav"
    path = session_dir / f"recording{ext}"

    try:
        content = await file.read()
        path.write_bytes(content)
    except Exception as e:
        raise HTTPException(500, f"Failed to save audio: {e}")

    return {"ok": True, "path": str(path), "size": len(content)}


@router.post("/{session_id}/transcribe-from-recording")
async def transcribe_from_recording(
    session_id: str,
    mode: Literal["replace", "append"] = Query("replace", description="replace=clear existing; append=add to end"),
    default_speaker: Literal["interviewer", "candidate"] = Query("candidate", description="Speaker for file ASR output (no diarization)"),
    db: AsyncSession = Depends(get_db),
):
    """Run file-based ASR on uploaded recording and merge into transcript."""
    s = await db.get(InterviewSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")

    session_dir = Path(settings.upload_dir) / session_id
    candidates = list(session_dir.glob("recording.*")) if session_dir.exists() else []
    if not candidates:
        raise HTTPException(404, "No recording found. Upload via POST /audio/upload first.")

    path = candidates[0]
    audio_data = path.read_bytes()

    from app.services.stt_file_volcengine import transcribe_file

    result = await transcribe_file(audio_data)
    if result.get("error"):
        raise HTTPException(502, f"Transcription failed: {result['error']}")

    utterances = result.get("utterances") or []
    if not utterances and result.get("text"):
        utterances = [{"start_time": 0, "end_time": result.get("duration_ms", 0), "text": result["text"]}]

    if mode == "replace":
        await db.execute(delete(TranscriptEntry).where(TranscriptEntry.session_id == session_id))
        await db.commit()

    for u in utterances:
        start_sec = u.get("start_time", 0) / 1000.0
        text = (u.get("text") or "").strip()
        if not text:
            continue
        entry = TranscriptEntry(
            session_id=session_id,
            speaker=default_speaker,
            text=text,
            start_time=start_sec,
            end_time=u.get("end_time") / 1000.0 if u.get("end_time") else None,
        )
        db.add(entry)
    await db.commit()

    return {"ok": True, "entries_added": len(utterances), "mode": mode}


@router.get("/{session_id}/transcript", response_model=List[TranscriptEntryOut])
async def get_transcript(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TranscriptEntry)
        .where(TranscriptEntry.session_id == session_id)
        .order_by(TranscriptEntry.start_time)
    )
    return result.scalars().all()


@router.get("/{session_id}/history", response_model=List[SessionHistoryItemOut])
async def get_history(
    session_id: str,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(InterviewSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    tr_result = await db.execute(
        select(TranscriptEntry)
        .where(TranscriptEntry.session_id == session_id)
        .order_by(TranscriptEntry.created_at)
    )
    entries = tr_result.scalars().all()

    insight_result = await db.execute(
        select(AIInsight)
        .where(AIInsight.session_id == session_id)
        .order_by(AIInsight.created_at)
    )
    insights = insight_result.scalars().all()

    log_result = await db.execute(
        select(CopilotLog)
        .where(CopilotLog.session_id == session_id)
        .order_by(CopilotLog.created_at)
    )
    logs = log_result.scalars().all()

    timeline = []
    for e in entries:
        timeline.append(
            {
                "type": "transcript",
                "created_at": e.created_at,
                "payload": {
                    "id": e.id,
                    "speaker": e.speaker,
                    "text": e.text,
                    "start_time": e.start_time,
                },
            }
        )

    for s in insights:
        timeline.append(
            {
                "type": "ai_insight",
                "created_at": s.created_at,
                "payload": {
                    "id": s.id,
                    "insight_type": s.insight_type,
                    "content": s.content,
                    "related_transcript_ids": s.related_transcript_ids or [],
                },
            }
        )

    for l in logs:
        parsed_response = l.response_content
        if l.response_content:
            try:
                parsed_response = json.loads(l.response_content)
            except Exception:
                parsed_response = l.response_content
        timeline.append(
            {
                "type": "copilot_log",
                "created_at": l.created_at,
                "payload": {
                    "id": l.id,
                    "log_type": l.log_type,
                    "request_summary": l.request_summary,
                    "response_content": parsed_response,
                    "model_used": l.model_used,
                },
            }
        )

    timeline.sort(key=lambda item: item["created_at"])
    return timeline[offset: offset + limit]


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
