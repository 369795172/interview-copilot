"""
Persistent global context store.

Company values and project background are workspace-level knowledge that
persists across interview sessions.  They are stored as a JSON file in
``settings.data_dir`` and loaded automatically when a new CopilotEngine
is initialised for a session.
"""

import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)

_FILENAME = "global_context.json"

_EMPTY: Dict[str, Any] = {
    "company_values": "",
    "company_values_source": "",
    "project_background": "",
    "project_background_source": "",
    "updated_at": "",
}


class GlobalContextStore:
    """Read/write ``global_context.json`` in the application data directory."""

    def __init__(self, data_dir: Optional[Path] = None):
        self._dir = data_dir or settings.data_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / _FILENAME

    def load(self) -> Dict[str, Any]:
        if not self._path.exists():
            return dict(_EMPTY)
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {**_EMPTY, **data}
        except Exception:
            logger.exception("Failed to read %s", self._path)
            return dict(_EMPTY)

    def _save(self, data: Dict[str, Any]) -> None:
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        try:
            fd, tmp = tempfile.mkstemp(
                dir=str(self._dir), suffix=".tmp", prefix="gc_"
            )
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            Path(tmp).replace(self._path)
            logger.info("Global context saved to %s", self._path)
        except Exception:
            logger.exception("Failed to save global context")

    def update_company_values(self, text: str, source: str = "") -> None:
        data = self.load()
        data["company_values"] = text
        data["company_values_source"] = source
        self._save(data)

    def update_project_background(self, text: str, source: str = "") -> None:
        data = self.load()
        data["project_background"] = text
        data["project_background_source"] = source
        self._save(data)

    def snapshot(self) -> Dict[str, Any]:
        """Return a summary suitable for API responses."""
        data = self.load()
        cv = data.get("company_values", "")
        pb = data.get("project_background", "")
        return {
            "company_values_chars": len(cv),
            "company_values_source": data.get("company_values_source", ""),
            "project_background_chars": len(pb),
            "project_background_source": data.get("project_background_source", ""),
            "updated_at": data.get("updated_at", ""),
        }


global_context_store = GlobalContextStore()
