"""
STT provider router: selects Volcano Engine (PCM) or AI Builder Space (WebM).
"""

import logging
from typing import Dict, Any, Optional, Callable, Awaitable

from app.config import settings
from app.services.transcription import TranscriptionService
from app.services.stt_volcengine import VolcEngineStreamingClient

logger = logging.getLogger(__name__)

# WebM/EBML magic bytes
WEBM_MAGIC = bytes([0x1A, 0x45, 0xDF, 0xA3])


def _is_webm(data: bytes) -> bool:
    return len(data) >= 4 and data[:4] == WEBM_MAGIC


def use_volcengine(audio_data: bytes) -> bool:
    """True if we should use Volcano Engine for this chunk (PCM + configured)."""
    if settings.stt_provider == "ai_builder":
        return False
    if not (settings.volcengine_app_id and settings.volcengine_asr_token):
        return False
    if _is_webm(audio_data):
        return False
    return True


def get_transcription_service() -> TranscriptionService:
    """Get AI Builder Space service for WebM chunks."""
    return TranscriptionService()


def create_volcengine_client(
    on_result: Callable[[str, bool], None],
    on_error: Optional[Callable[[str], None]] = None,
) -> Optional[VolcEngineStreamingClient]:
    """Create Volcano Engine streaming client if configured."""
    if not (settings.volcengine_app_id and settings.volcengine_asr_token):
        return None
    if settings.stt_provider == "ai_builder":
        return None
    return VolcEngineStreamingClient(on_result=on_result, on_error=on_error)
