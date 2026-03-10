"""
Context manager: aggregates context from Feishu, GitHub, file uploads,
and custom notes into a unified context object for the copilot.
"""

import logging
from typing import Optional, Dict, Any

from app.adapters.feishu import FeishuReaderAdapter
from app.adapters.github import GitHubAdapter
from app.adapters.file_parser import parse_resume

logger = logging.getLogger(__name__)


class ContextManager:
    """Collects and manages all context sources for an interview session."""

    def __init__(self):
        self.company_values: str = ""
        self.project_background: str = ""
        self.candidate_profile: str = ""  # Now stores raw_text instead of dict
        self.evaluation_framework: Optional[Dict[str, Any]] = None
        self.custom_notes: str = ""

    async def load_feishu(self, url: str) -> Dict[str, Any]:
        """Import company values / JD from a Feishu document."""
        reader = FeishuReaderAdapter()
        result = reader.read(url=url)
        if result.get("plain_text"):
            self.company_values = result["plain_text"]
            logger.info("Loaded Feishu doc: %s (%d chars)", result.get("title"), len(self.company_values))
        return result

    async def load_github(self, repo_url: Optional[str] = None, local_path: Optional[str] = None) -> Dict[str, Any]:
        """Import project background from GitHub repo or local directory."""
        adapter = GitHubAdapter()
        if local_path:
            result = adapter.read_local(local_path)
        elif repo_url:
            result = await adapter.read_repo(repo_url)
        else:
            return {"error": "No repo_url or local_path provided"}
        if result.get("summary"):
            self.project_background = result["summary"]
        return result

    async def load_candidate_file(self, file_path: str, file_name: str) -> Dict[str, Any]:
        """Parse an uploaded candidate file (PDF / MD / DOCX)."""
        profile = parse_resume(file_path, file_name)
        # Fix: store raw_text content instead of the whole dict
        self.candidate_profile = profile.get("raw_text", "") if isinstance(profile, dict) else str(profile)
        return profile

    def set_custom_notes(self, notes: str):
        self.custom_notes = notes

    def snapshot(self) -> Dict[str, Any]:
        """Return a serialisable snapshot of all loaded context."""
        return {
            "company_values": self.company_values[:500] + ("..." if len(self.company_values) > 500 else ""),
            "project_background": self.project_background[:500] + ("..." if len(self.project_background) > 500 else ""),
            "candidate_profile": self.candidate_profile,
            "evaluation_framework": self.evaluation_framework,
            "custom_notes": self.custom_notes[:300],
        }
