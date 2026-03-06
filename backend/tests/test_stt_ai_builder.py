"""
Tests for AI Builder Space transcription service.
Covers: PCM-to-WAV conversion, format detection, HTTP call logic, retry behavior.
"""

import struct
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest
import respx

import app.services.transcription as transcription_mod
from app.services.transcription import (
    TranscriptionService,
    _pcm_to_wav,
    _is_webm,
    close_transcription_client,
)


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

class TestIsWebm:
    def test_detects_webm_magic(self, webm_fake):
        assert _is_webm(webm_fake) is True

    def test_rejects_pcm(self, pcm_silence):
        assert _is_webm(pcm_silence) is False

    def test_rejects_short_data(self):
        assert _is_webm(b"\x1A\x45") is False

    def test_rejects_empty(self):
        assert _is_webm(b"") is False

    def test_rejects_wav_header(self):
        assert _is_webm(b"RIFF" + b"\x00" * 100) is False


# ---------------------------------------------------------------------------
# PCM to WAV conversion
# ---------------------------------------------------------------------------

class TestPcmToWav:
    def test_wav_starts_with_riff(self, pcm_silence):
        wav = _pcm_to_wav(pcm_silence)
        assert wav[:4] == b"RIFF"

    def test_wav_contains_wave_marker(self, pcm_silence):
        wav = _pcm_to_wav(pcm_silence)
        assert wav[8:12] == b"WAVE"

    def test_wav_format_chunk(self, pcm_silence):
        wav = _pcm_to_wav(pcm_silence)
        assert wav[12:16] == b"fmt "

    def test_wav_pcm_format(self, pcm_silence):
        wav = _pcm_to_wav(pcm_silence)
        audio_format = struct.unpack("<H", wav[20:22])[0]
        assert audio_format == 1  # PCM

    def test_wav_sample_rate(self, pcm_silence):
        wav = _pcm_to_wav(pcm_silence)
        sample_rate = struct.unpack("<I", wav[24:28])[0]
        assert sample_rate == 16000

    def test_wav_channels(self, pcm_silence):
        wav = _pcm_to_wav(pcm_silence)
        channels = struct.unpack("<H", wav[22:24])[0]
        assert channels == 1

    def test_wav_bits_per_sample(self, pcm_silence):
        wav = _pcm_to_wav(pcm_silence)
        bits = struct.unpack("<H", wav[34:36])[0]
        assert bits == 16

    def test_data_chunk_size_matches(self, pcm_silence):
        wav = _pcm_to_wav(pcm_silence)
        data_size = struct.unpack("<I", wav[40:44])[0]
        assert data_size == len(pcm_silence)

    def test_total_length(self, pcm_silence):
        wav = _pcm_to_wav(pcm_silence)
        assert len(wav) == 44 + len(pcm_silence)  # 44-byte header + data

    def test_custom_params(self):
        pcm = b"\x00" * 100
        wav = _pcm_to_wav(pcm, sample_rate=8000, channels=2, bits=8)
        sr = struct.unpack("<I", wav[24:28])[0]
        ch = struct.unpack("<H", wav[22:24])[0]
        bits = struct.unpack("<H", wav[34:36])[0]
        assert sr == 8000
        assert ch == 2
        assert bits == 8


# ---------------------------------------------------------------------------
# TranscriptionService: unit tests (mocked HTTP)
# ---------------------------------------------------------------------------

class TestTranscriptionServiceUnit:
    """Unit tests with mocked settings to avoid picking up real .env credentials."""

    def _make_svc(self, token="test-token", base_url="https://test.example.com/v1"):
        svc = TranscriptionService.__new__(TranscriptionService)
        svc.token = token
        svc.base_url = base_url
        return svc

    def test_available_with_token(self):
        svc = self._make_svc(token="test-token")
        assert svc.available is True

    def test_unavailable_without_token(self):
        svc = self._make_svc(token="")
        assert svc.available is False

    @pytest.mark.asyncio
    async def test_returns_error_when_no_token(self):
        svc = self._make_svc(token="")
        result = await svc.transcribe(b"\x00" * 100)
        assert result["text"] == ""
        assert "not configured" in result["error"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_successful_transcription(self, pcm_silence):
        transcription_mod._http_client = None

        respx.post("https://test.example.com/v1/audio/transcriptions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "text": "你好世界",
                    "request_id": "req-123",
                    "segments": [],
                    "detected_language": "zh-CN",
                    "duration_seconds": 0.5,
                    "confidence": 0.95,
                },
            )
        )

        svc = self._make_svc()
        result = await svc.transcribe(pcm_silence)

        assert result["text"] == "你好世界"
        assert result["request_id"] == "req-123"
        assert result["confidence"] == 0.95

        transcription_mod._http_client = None

    @pytest.mark.asyncio
    @respx.mock
    async def test_handles_500_with_retry(self, pcm_silence):
        transcription_mod._http_client = None

        route = respx.post("https://test.example.com/v1/audio/transcriptions")
        route.side_effect = [
            httpx.Response(500, text="Internal Server Error"),
            httpx.Response(500, text="Internal Server Error"),
            httpx.Response(200, json={"text": "重试成功"}),
        ]

        svc = self._make_svc()
        result = await svc.transcribe(pcm_silence)

        assert result["text"] == "重试成功"
        assert route.call_count == 3

        transcription_mod._http_client = None

    @pytest.mark.asyncio
    @respx.mock
    async def test_handles_400_no_retry(self, pcm_silence):
        transcription_mod._http_client = None

        route = respx.post("https://test.example.com/v1/audio/transcriptions")
        route.mock(return_value=httpx.Response(400, text="Bad Request"))

        svc = self._make_svc()
        result = await svc.transcribe(pcm_silence)

        assert result["text"] == ""
        assert "400" in result["error"]
        assert route.call_count == 1

        transcription_mod._http_client = None

    @pytest.mark.asyncio
    @respx.mock
    async def test_auto_detect_webm(self, webm_fake):
        transcription_mod._http_client = None

        route = respx.post("https://test.example.com/v1/audio/transcriptions")
        route.mock(return_value=httpx.Response(200, json={"text": "webm audio"}))

        svc = self._make_svc()
        result = await svc.transcribe(webm_fake, mime_type="auto")

        assert result["text"] == "webm audio"
        assert route.call_count == 1

        transcription_mod._http_client = None

    @pytest.mark.asyncio
    @respx.mock
    async def test_auto_detect_pcm_wraps_wav(self, pcm_silence):
        """When auto-detecting PCM, the service should wrap it as WAV."""
        transcription_mod._http_client = None

        calls = []

        def capture_request(request):
            calls.append(request)
            return httpx.Response(200, json={"text": "pcm wrapped"})

        respx.post("https://test.example.com/v1/audio/transcriptions").mock(
            side_effect=capture_request
        )

        svc = self._make_svc()
        result = await svc.transcribe(pcm_silence, mime_type="auto")

        assert result["text"] == "pcm wrapped"

        transcription_mod._http_client = None

    @pytest.mark.asyncio
    async def test_transcribe_long_returns_error_without_token(self):
        svc = self._make_svc(token="")
        result = await svc.transcribe_long(b"\x00" * 100)
        assert result["text"] == ""
        assert "not configured" in result["error"]


# ---------------------------------------------------------------------------
# Integration: real AI Builder service
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestAIBuilderIntegration:
    """These tests hit the real AI Builder Space API.
    Run with: pytest -m integration
    Requires IC_AI_BUILDER_TOKEN in env/.env
    """

    @pytest.mark.asyncio
    async def test_transcribe_silence(self, has_ai_builder_creds, pcm_silence):
        if not has_ai_builder_creds:
            pytest.skip("AI Builder credentials not configured")

        await close_transcription_client()
        svc = TranscriptionService()
        result = await svc.transcribe(pcm_silence)

        assert "error" not in result or result.get("error") is None, \
            f"Unexpected error: {result.get('error')}"
        assert isinstance(result.get("text"), str)
        await close_transcription_client()

    @pytest.mark.asyncio
    async def test_transcribe_tone(self, has_ai_builder_creds, pcm_tone):
        if not has_ai_builder_creds:
            pytest.skip("AI Builder credentials not configured")

        await close_transcription_client()
        svc = TranscriptionService()
        result = await svc.transcribe(pcm_tone)

        assert "error" not in result or result.get("error") is None, \
            f"Unexpected error: {result.get('error')}"
        assert isinstance(result.get("text"), str)
        await close_transcription_client()
