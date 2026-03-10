"""
Context loading routes: Feishu, GitHub, file upload, model selection.

Company values and project background are persisted as *global* context
(shared across sessions) via ``GlobalContextStore``.  Candidate profiles
remain per-session.
"""

import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.models.schemas import FeishuImportRequest, GitHubImportRequest, ContextSummary
from app.services.context_manager import ContextManager
from app.services.copilot import AVAILABLE_MODELS
from app.services.global_context import global_context_store
from app.api.ws_interview import active_copilots

router = APIRouter(prefix="/api/context", tags=["context"])

# Shared context managers keyed by session_id (per-session, in-memory)
_context_managers: dict[str, ContextManager] = {}


def _get_cm(session_id: str) -> ContextManager:
    if session_id not in _context_managers:
        _context_managers[session_id] = ContextManager()
    return _context_managers[session_id]


def get_context_manager(session_id: str) -> Optional[ContextManager]:
    """Return the existing ContextManager for *session_id*, or None."""
    return _context_managers.get(session_id)


# ---- Fixed routes (must come before /{session_id} parameterised routes) ----

class ModelSelectRequest(BaseModel):
    model_id: str


@router.get("/models")
async def list_models():
    return {"models": AVAILABLE_MODELS, "default": settings.llm_model}


@router.get("/global")
async def get_global_context():
    """Return a snapshot of the persistent global context."""
    return global_context_store.snapshot()


# ---- Per-session routes ----

@router.post("/{session_id}/model")
async def select_model(session_id: str, body: ModelSelectRequest):
    copilot = active_copilots.get(session_id)
    if copilot:
        copilot.selected_model = body.model_id
    return {"status": "ok", "model": body.model_id}


@router.post("/{session_id}/feishu")
async def import_feishu(session_id: str, body: FeishuImportRequest):
    cm = _get_cm(session_id)
    result = await cm.load_feishu(body.url)
    if result.get("error"):
        raise HTTPException(400, detail=result["error"])
    global_context_store.update_company_values(cm.company_values, source=body.url)
    copilot = active_copilots.get(session_id)
    if copilot:
        copilot.company_values = cm.company_values
    return {"status": "ok", "title": result.get("title", ""), "chars": len(cm.company_values)}


@router.post("/{session_id}/github")
async def import_github(session_id: str, body: GitHubImportRequest):
    cm = _get_cm(session_id)
    result = await cm.load_github(repo_url=body.repo_url, local_path=body.local_path)
    if "error" in result:
        raise HTTPException(400, result["error"])
    source = body.repo_url or body.local_path or ""
    global_context_store.update_project_background(cm.project_background, source=source)
    copilot = active_copilots.get(session_id)
    if copilot:
        copilot.project_background = cm.project_background
    return {"status": "ok", "name": result.get("name", ""), "chars": len(cm.project_background)}


@router.post("/{session_id}/upload")
async def upload_candidate_file(
    session_id: str,
    file: UploadFile = File(...),
):
    cm = _get_cm(session_id)
    dest = Path(settings.upload_dir) / session_id
    dest.mkdir(parents=True, exist_ok=True)
    file_path = dest / file.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    profile = await cm.load_candidate_file(str(file_path), file.filename)
    copilot = active_copilots.get(session_id)
    if copilot:
        # Fix: cm.candidate_profile is already raw_text string
        copilot.candidate_profile = cm.candidate_profile
    return {"status": "ok", "file": file.filename, "profile": profile}


@router.post("/{session_id}/notes")
async def set_notes(session_id: str, notes: str = Form(...)):
    cm = _get_cm(session_id)
    cm.set_custom_notes(notes)
    return {"status": "ok"}


@router.get("/{session_id}/summary", response_model=ContextSummary)
async def get_context_summary(session_id: str):
    cm = _get_cm(session_id)
    snap = cm.snapshot()
    return ContextSummary(**snap)
