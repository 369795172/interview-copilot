"""
Tests for the STT provider router.
Covers: provider selection logic, factory functions.
"""

from unittest.mock import patch, MagicMock

import pytest

from app.services.stt_router import (
    _is_webm,
    use_volcengine,
    get_transcription_service,
    create_volcengine_client,
    WEBM_MAGIC,
)
from app.services.transcription import TranscriptionService
from app.services.stt_volcengine import VolcEngineStreamingClient


# ---------------------------------------------------------------------------
# WebM detection (router's copy)
# ---------------------------------------------------------------------------

class TestRouterIsWebm:
    def test_detects_webm(self):
        assert _is_webm(WEBM_MAGIC + b"\x00" * 10) is True

    def test_rejects_pcm(self):
        assert _is_webm(b"\x00" * 100) is False

    def test_rejects_short(self):
        assert _is_webm(b"\x1A\x45") is False


# ---------------------------------------------------------------------------
# use_volcengine routing logic
# ---------------------------------------------------------------------------

class TestUseVolcengine:
    def _mock_settings(self, provider="auto", app_id="id", token="tok"):
        mock = MagicMock()
        mock.stt_provider = provider
        mock.volcengine_app_id = app_id
        mock.volcengine_asr_token = token
        return mock

    def test_uses_volcengine_for_pcm_when_auto(self):
        pcm = b"\x00" * 320
        with patch("app.services.stt_router.settings", self._mock_settings("auto")):
            assert use_volcengine(pcm) is True

    def test_skips_volcengine_for_webm(self):
        webm = WEBM_MAGIC + b"\x00" * 100
        with patch("app.services.stt_router.settings", self._mock_settings("auto")):
            assert use_volcengine(webm) is False

    def test_skips_when_provider_is_ai_builder(self):
        pcm = b"\x00" * 320
        with patch("app.services.stt_router.settings", self._mock_settings("ai_builder")):
            assert use_volcengine(pcm) is False

    def test_skips_when_no_app_id(self):
        pcm = b"\x00" * 320
        with patch("app.services.stt_router.settings", self._mock_settings("auto", app_id="")):
            assert use_volcengine(pcm) is False

    def test_skips_when_no_token(self):
        pcm = b"\x00" * 320
        with patch("app.services.stt_router.settings", self._mock_settings("auto", token="")):
            assert use_volcengine(pcm) is False

    def test_uses_volcengine_when_explicit_provider(self):
        pcm = b"\x00" * 320
        with patch("app.services.stt_router.settings", self._mock_settings("volcengine")):
            assert use_volcengine(pcm) is True


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------

class TestFactoryFunctions:
    def test_get_transcription_service_returns_instance(self):
        svc = get_transcription_service()
        assert isinstance(svc, TranscriptionService)

    def test_create_volcengine_client_with_creds(self):
        mock_settings = MagicMock()
        mock_settings.stt_provider = "auto"
        mock_settings.volcengine_app_id = "test-id"
        mock_settings.volcengine_asr_token = "test-token"

        with patch("app.services.stt_router.settings", mock_settings):
            client = create_volcengine_client(on_result=lambda t, d: None)
            assert isinstance(client, VolcEngineStreamingClient)

    def test_create_volcengine_client_returns_none_without_creds(self):
        mock_settings = MagicMock()
        mock_settings.stt_provider = "auto"
        mock_settings.volcengine_app_id = ""
        mock_settings.volcengine_asr_token = ""

        with patch("app.services.stt_router.settings", mock_settings):
            client = create_volcengine_client(on_result=lambda t, d: None)
            assert client is None

    def test_create_volcengine_client_returns_none_when_ai_builder_forced(self):
        mock_settings = MagicMock()
        mock_settings.stt_provider = "ai_builder"
        mock_settings.volcengine_app_id = "test-id"
        mock_settings.volcengine_asr_token = "test-token"

        with patch("app.services.stt_router.settings", mock_settings):
            client = create_volcengine_client(on_result=lambda t, d: None)
            assert client is None
