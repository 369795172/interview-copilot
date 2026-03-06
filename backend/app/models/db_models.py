import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Float, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, relationship


def _utcnow():
    return datetime.now(timezone.utc)


def _new_id():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(String, primary_key=True, default=_new_id)
    name = Column(String, nullable=False)
    resume_path = Column(String, nullable=True)
    parsed_profile = Column(JSON, nullable=True)
    uploaded_files = Column(JSON, default=list)
    created_at = Column(DateTime, default=_utcnow)

    sessions = relationship("InterviewSession", back_populates="candidate")


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(String, primary_key=True, default=_new_id)
    interviewer_id = Column(String, nullable=True)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=True)
    status = Column(String, default="preparing")  # preparing | active | completed
    role_title = Column(String, nullable=True)
    context_snapshot = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)

    candidate = relationship("Candidate", back_populates="sessions")
    transcript_entries = relationship("TranscriptEntry", back_populates="session", order_by="TranscriptEntry.start_time")
    ai_insights = relationship("AIInsight", back_populates="session", order_by="AIInsight.created_at")
    evaluation_scores = relationship("EvaluationScore", back_populates="session")


class TranscriptEntry(Base):
    __tablename__ = "transcript_entries"

    id = Column(String, primary_key=True, default=_new_id)
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False)
    speaker = Column(String, nullable=False)  # interviewer | candidate
    text = Column(Text, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=True)
    audio_ref = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    session = relationship("InterviewSession", back_populates="transcript_entries")


class AIInsight(Base):
    __tablename__ = "ai_insights"

    id = Column(String, primary_key=True, default=_new_id)
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False)
    insight_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    related_transcript_ids = Column(JSON, default=list)
    created_at = Column(DateTime, default=_utcnow)

    session = relationship("InterviewSession", back_populates="ai_insights")


class EvaluationScore(Base):
    __tablename__ = "evaluation_scores"

    id = Column(String, primary_key=True, default=_new_id)
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False)
    dimension = Column(String, nullable=False)
    sub_dimension = Column(String, nullable=True)
    score = Column(Integer, nullable=True)
    evidence_note = Column(Text, nullable=True)
    transcript_entry_ids = Column(JSON, default=list)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    session = relationship("InterviewSession", back_populates="evaluation_scores")
