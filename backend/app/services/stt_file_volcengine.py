"""
Volcano Engine BigModel File Recognition API (Flash).
One-shot transcription for full recording files — higher accuracy than streaming.
API: https://www.volcengine.com/docs/6561/1631584
Resource: volc.bigasr.auc_turbo
"""

import base64
import logging
import uuid
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

VOLC_FILE_ASR_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash"
X_API_RESOURCE_ID = "volc.bigasr.auc_turbo"


def _is_available() -> bool:
    return bool(settings.volcengine_app_id and settings.volcengine_asr_token)


async def transcribe_file(
    audio_data: bytes,
    *,
    mime_type: str = "audio/wav",
) -> Dict[str, Any]:
    """Transcribe a full audio file via Volcano Engine Flash API.

    Args:
        audio_data: Raw audio bytes (WAV, MP3, or OGG OPUS).
        mime_type: MIME type hint; used to validate format.

    Returns:
        {
            "text": str,           # Full transcript
            "utterances": [        # Per-segment with timestamps (ms)
                {"start_time": int, "end_time": int, "text": str},
                ...
            ],
            "duration_ms": int,
            "error": str | None,
        }
    """
    if not _is_available():
        return {"text": "", "utterances": [], "error": "Volcano Engine file ASR not configured"}

    app_id = settings.volcengine_app_id
    token = settings.volcengine_asr_token

    payload = {
        "user": {"uid": app_id},
        "audio": {"data": base64.b64encode(audio_data).decode("ascii")},
        "request": {"model_name": "bigmodel"},
    }

    headers = {
        "X-Api-App-Key": app_id,
        "X-Api-Access-Key": token,
        "X-Api-Resource-Id": X_API_RESOURCE_ID,
        "X-Api-Request-Id": str(uuid.uuid4()),
        "X-Api-Sequence": "-1",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(VOLC_FILE_ASR_URL, json=payload, headers=headers)
    except Exception as e:
        logger.exception("Volcano file ASR request failed")
        return {"text": "", "utterances": [], "error": str(e)}

    status = resp.headers.get("X-Api-Status-Code", "")
    if status != "20000000":
        msg = resp.headers.get("X-Api-Message", resp.text[:200])
        logger.warning("Volcano file ASR failed: status=%s msg=%s", status, msg)
        return {"text": "", "utterances": [], "error": f"API error {status}: {msg}"}

    try:
        data = resp.json()
    except Exception as e:
        return {"text": "", "utterances": [], "error": f"Invalid JSON: {e}"}

    result = data.get("result") or {}
    text = (result.get("text") or "").strip()
    utterances_raw = result.get("utterances") or []

    utterances: List[Dict[str, Any]] = []
    for u in utterances_raw:
        if isinstance(u, dict):
            utterances.append({
                "start_time": int(u.get("start_time", 0)),
                "end_time": int(u.get("end_time", 0)),
                "text": (u.get("text") or "").strip(),
            })

    audio_info = data.get("audio_info") or {}
    duration_ms = int(audio_info.get("duration", 0))

    return {
        "text": text,
        "utterances": utterances,
        "duration_ms": duration_ms,
        "error": None,
    }
