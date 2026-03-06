"""
File parser adapter.
Parses PDF, Markdown, DOCX, and TXT files to extract candidate profiles.
"""

import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


def parse_resume(file_path: str, file_name: str) -> Dict[str, Any]:
    """Parse a resume / candidate file and return a structured profile dict."""
    ext = Path(file_name).suffix.lower()
    text = ""

    try:
        if ext == ".pdf":
            text = _parse_pdf(file_path)
        elif ext in (".md", ".txt"):
            text = Path(file_path).read_text(encoding="utf-8", errors="replace")
        elif ext in (".docx",):
            text = _parse_docx(file_path)
        else:
            text = Path(file_path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        logger.exception("Failed to parse file %s", file_name)
        return {"raw_text": "", "error": f"Parse failed for {file_name}"}

    return {
        "file_name": file_name,
        "raw_text": text[:50_000],
        "char_count": len(text),
    }


def _parse_pdf(file_path: str) -> str:
    try:
        import fitz  # pymupdf
        doc = fitz.open(file_path)
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n\n".join(pages)
    except ImportError:
        logger.warning("pymupdf not installed; falling back to raw read")
        return Path(file_path).read_text(encoding="utf-8", errors="replace")


def _parse_docx(file_path: str) -> str:
    try:
        from docx import Document
        doc = Document(file_path)
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        logger.warning("python-docx not installed; falling back to raw read")
        return Path(file_path).read_text(encoding="utf-8", errors="replace")
