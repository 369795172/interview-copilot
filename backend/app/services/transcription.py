"""
Speech-to-text via AI Builder Space API.
Based on OpenAPI spec: https://space.ai-builders.com/backend/openapi.json

Two endpoints:
  /v1/audio/transcriptions       - quick, for short chunks
  /v1/audio/transcriptions_long  - AssemblyAI with speaker diarization + timestamps
"""

import asyncio
import io
import logging
import struct
from typing import Optional, Dict, Any, List

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

WEBM_MAGIC = bytes([0x1A, 0x45, 0xDF, 0xA3])


def _is_webm(data: bytes) -> bool:
    return len(data) >= 4 and data[:4] == WEBM_MAGIC


def _pcm_to_wav(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, bits: int = 16) -> bytes:
    """Wrap raw PCM bytes in a WAV header so AI Builder Space can decode it."""
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    data_size = len(pcm_data)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,            # chunk size
        1,             # PCM format
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits,
        b"data",
        data_size,
    )
    return header + pcm_data

_http_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=60.0)
    return _http_client


async def close_transcription_client() -> None:
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


class TranscriptionService:
    """Transcribes audio via AI Builder Space /v1/audio/transcriptions."""

    RETRY_BACKOFF = (1, 2, 4)

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.token = token or settings.ai_builder_token
        self.base_url = base_url or settings.ai_builder_base_url

    @property
    def available(self) -> bool:
        return bool(self.token)

    async def transcribe(
        self,
        audio_data: bytes,
        language: str = "zh-CN",
        mime_type: str = "auto",
    ) -> Dict[str, Any]:
        """Short-form transcription. Returns {text, segments, detected_language, ...}.
        mime_type='auto' detects format: WebM magic bytes → webm, else → wrap PCM as WAV.
        """
        if not self.token:
            return {"text": "", "error": "Transcription not configured (no AI Builder token)"}

        if mime_type == "auto":
            if _is_webm(audio_data):
                mime_type = "audio/webm"
            else:
                audio_data = _pcm_to_wav(audio_data)
                mime_type = "audio/wav"
                logger.debug("Converted PCM (%d bytes payload) to WAV for AI Builder", len(audio_data))

        ext = "webm" if "webm" in mime_type else "wav"
        files = {"audio_file": (f"chunk.{ext}", io.BytesIO(audio_data), mime_type)}
        data: Dict[str, str] = {"language": language}

        last_error: Optional[str] = None
        for attempt, delay in enumerate(self.RETRY_BACKOFF):
            try:
                client = _get_client()
                resp = await client.post(
                    f"{self.base_url}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.token}"},
                    files=files,
                    data=data,
                    timeout=60.0,
                )
                if resp.status_code == 200:
                    result = resp.json()
                    return {
                        "text": result.get("text", ""),
                        "request_id": result.get("request_id"),
                        "segments": result.get("segments"),
                        "detected_language": result.get("detected_language"),
                        "duration_seconds": result.get("duration_seconds"),
                        "confidence": result.get("confidence"),
                    }
                last_error = f"HTTP {resp.status_code}"
                if 500 <= resp.status_code < 600 and attempt < len(self.RETRY_BACKOFF) - 1:
                    logger.warning(
                        "Transcription HTTP %s (attempt %d/%d), retrying in %ds: %s",
                        resp.status_code,
                        attempt + 1,
                        len(self.RETRY_BACKOFF),
                        delay,
                        resp.text[:200],
                    )
                    await asyncio.sleep(delay)
                    files = {"audio_file": (f"chunk.{ext}", io.BytesIO(audio_data), mime_type)}
                else:
                    logger.warning("Transcription HTTP %s: %s", resp.status_code, resp.text[:200])
                    return {"text": "", "error": last_error}
            except Exception as exc:
                last_error = str(exc)
                logger.exception("Transcription failed (attempt %d/%d)", attempt + 1, len(self.RETRY_BACKOFF))
                if attempt < len(self.RETRY_BACKOFF) - 1:
                    await asyncio.sleep(delay)
                    files = {"audio_file": (f"chunk.{ext}", io.BytesIO(audio_data), mime_type)}
                else:
                    return {"text": "", "error": last_error}

        return {"text": "", "error": last_error or "Transcription failed"}

    async def transcribe_long(
        self,
        audio_data: bytes,
        language: str = "zh-CN",
        mime_type: str = "audio/webm",
        speaker_labels: bool = True,
    ) -> Dict[str, Any]:
        """Long-form transcription with speaker diarization via /v1/audio/transcriptions_long.
        Ideal for full interview recordings — identifies different speakers automatically.
        """
        if not self.token:
            return {"text": "", "error": "Transcription not configured (no AI Builder token)"}

        ext = "webm" if "webm" in mime_type else "wav"
        files = {"audio_file": (f"recording.{ext}", io.BytesIO(audio_data), mime_type)}
        data: Dict[str, Any] = {
            "language": language,
            "speaker_labels": "true" if speaker_labels else "false",
        }

        try:
            client = _get_client()
            resp = await client.post(
                f"{self.base_url}/audio/transcriptions_long",
                headers={"Authorization": f"Bearer {self.token}"},
                files=files,
                data=data,
                timeout=300.0,
            )
            if resp.status_code == 200:
                return resp.json()
            return {"text": "", "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except Exception as exc:
            logger.exception("Long transcription failed")
            return {"text": "", "error": str(exc)}
