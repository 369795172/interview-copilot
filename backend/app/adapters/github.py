"""
GitHub / local directory adapter.
Reads project structure and key files to build a context summary.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next"}
KEY_FILES = {"README.md", "README.rst", "readme.md", "package.json", "pyproject.toml", "requirements.txt", "Cargo.toml", "go.mod"}
MAX_FILE_SIZE = 30_000  # chars


class GitHubAdapter:
    """Reads project context from GitHub repos or local directories."""

    def read_local(self, path: str) -> Dict[str, Any]:
        """Scan a local directory for project structure and key files."""
        root = Path(path).expanduser().resolve()
        if not root.is_dir():
            return {"error": f"Not a directory: {path}"}

        tree = self._build_tree(root, depth=3)
        key_contents = self._read_key_files(root)
        summary = self._summarise(root.name, tree, key_contents)
        return {"name": root.name, "tree": tree, "key_files": list(key_contents.keys()), "summary": summary}

    async def read_repo(self, repo_url: str) -> Dict[str, Any]:
        """Fetch repo metadata and README from GitHub API."""
        owner, repo = self._parse_url(repo_url)
        if not owner:
            return {"error": f"Cannot parse GitHub URL: {repo_url}"}

        token = settings.github_token
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            async with httpx.AsyncClient() as client:
                meta_resp = await client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers, timeout=15)
                meta = meta_resp.json() if meta_resp.status_code == 200 else {}

                readme_resp = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/readme",
                    headers={**headers, "Accept": "application/vnd.github.v3.raw"},
                    timeout=15,
                )
                readme = readme_resp.text if readme_resp.status_code == 200 else ""

                tree_resp = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1",
                    headers=headers,
                    timeout=15,
                )
                tree_data = tree_resp.json() if tree_resp.status_code == 200 else {}
                paths = [t["path"] for t in tree_data.get("tree", []) if t.get("type") == "blob"][:200]

            description = meta.get("description", "")
            language = meta.get("language", "")
            topics = meta.get("topics", [])

            summary_parts = [
                f"# {owner}/{repo}",
                f"Description: {description}" if description else "",
                f"Language: {language}" if language else "",
                f"Topics: {', '.join(topics)}" if topics else "",
                "",
                "## File structure (top 200 files)",
                "\n".join(f"- {p}" for p in paths[:100]),
                "",
                "## README",
                readme[:MAX_FILE_SIZE] if readme else "(no README)",
            ]
            summary = "\n".join(summary_parts)
            return {"name": f"{owner}/{repo}", "summary": summary}

        except Exception as exc:
            logger.exception("GitHub fetch failed")
            return {"error": str(exc)}

    # ---- internal helpers ----

    @staticmethod
    def _parse_url(url: str):
        import re
        m = re.search(r"github\.com/([^/]+)/([^/\s?#]+)", url)
        if m:
            return m.group(1), m.group(2).removesuffix(".git")
        return None, None

    @staticmethod
    def _build_tree(root: Path, depth: int) -> str:
        lines: List[str] = []

        def _walk(p: Path, prefix: str, d: int):
            if d <= 0:
                return
            try:
                entries = sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
            except PermissionError:
                return
            for i, entry in enumerate(entries):
                if entry.name.startswith(".") and entry.name not in (".env.example",):
                    continue
                if entry.name in IGNORED_DIRS:
                    continue
                connector = "└── " if i == len(entries) - 1 else "├── "
                lines.append(f"{prefix}{connector}{entry.name}")
                if entry.is_dir():
                    ext = "    " if i == len(entries) - 1 else "│   "
                    _walk(entry, prefix + ext, d - 1)

        _walk(root, "", depth)
        return "\n".join(lines[:300])

    @staticmethod
    def _read_key_files(root: Path) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for name in KEY_FILES:
            fp = root / name
            if fp.is_file():
                try:
                    result[name] = fp.read_text(encoding="utf-8", errors="replace")[:MAX_FILE_SIZE]
                except Exception:
                    pass
        return result

    @staticmethod
    def _summarise(name: str, tree: str, key_contents: Dict[str, str]) -> str:
        parts = [f"# Project: {name}", "", "## Directory tree", tree, ""]
        for fname, content in key_contents.items():
            parts.append(f"## {fname}")
            parts.append(content[:5000])
            parts.append("")
        return "\n".join(parts)
