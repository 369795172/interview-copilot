from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ---------- Candidate ----------

class CandidateCreate(BaseModel):
    name: str
    resume_path: Optional[str] = None

class CandidateOut(BaseModel):
    id: str
    name: str
    resume_path: Optional[str] = None
    parsed_profile: Optional[Dict[str, Any]] = None
    uploaded_files: List[str] = []
    created_at: datetime


# ---------- Interview Session ----------

class SessionCreate(BaseModel):
    role_title: Optional[str] = None
    candidate_id: Optional[str] = None

class SessionOut(BaseModel):
    id: str
    interviewer_id: Optional[str] = None
    candidate_id: Optional[str] = None
    status: str
    role_title: Optional[str] = None
    context_snapshot: Dict[str, Any] = {}
    created_at: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


# ---------- Transcript ----------

class TranscriptEntryOut(BaseModel):
    id: str
    session_id: str
    speaker: str
    text: str
    start_time: float
    end_time: Optional[float] = None
    created_at: datetime


# ---------- AI Insight ----------

class AIInsightOut(BaseModel):
    id: str
    session_id: str
    insight_type: str
    content: str
    related_transcript_ids: List[str] = []
    created_at: datetime


# ---------- Evaluation ----------

class EvaluationScoreCreate(BaseModel):
    dimension: str
    sub_dimension: Optional[str] = None
    score: Optional[int] = Field(None, ge=1, le=5)
    evidence_note: Optional[str] = None
    transcript_entry_ids: List[str] = []

class EvaluationScoreUpdate(BaseModel):
    score: Optional[int] = Field(None, ge=1, le=5)
    evidence_note: Optional[str] = None
    transcript_entry_ids: Optional[List[str]] = None

class EvaluationScoreOut(BaseModel):
    id: str
    session_id: str
    dimension: str
    sub_dimension: Optional[str] = None
    score: Optional[int] = None
    evidence_note: Optional[str] = None
    transcript_entry_ids: List[str] = []
    created_at: datetime
    updated_at: datetime


# ---------- Context ----------

class FeishuImportRequest(BaseModel):
    url: str

class GitHubImportRequest(BaseModel):
    repo_url: Optional[str] = None
    local_path: Optional[str] = None

class ContextSummary(BaseModel):
    company_values: Optional[str] = None
    project_background: Optional[str] = None
    # Backward-compatible: legacy sessions may store dict profile,
    # newer flow stores resume raw text string.
    candidate_profile: Optional[Dict[str, Any] | str] = None
    evaluation_framework: Optional[Dict[str, Any]] = None
    custom_notes: Optional[str] = None


# ---------- WebSocket messages ----------

class WSMessage(BaseModel):
    type: str
    payload: Dict[str, Any] = {}
