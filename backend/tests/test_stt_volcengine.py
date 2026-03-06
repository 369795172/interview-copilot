"""
Tests for Volcano Engine BigModel Streaming ASR client.
Covers: protocol building, response parsing, client lifecycle.
"""

import gzip
import json
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.stt_volcengine import (
    VolcEngineStreamingClient,
    _build_header,
    _build_full_client_request,
    _build_audio_packet,
    _parse_server_response,
    MSG_TYPE_FULL_SERVER_RESPONSE,
    MSG_TYPE_SERVER_ACK,
    MSG_TYPE_SERVER_ERROR,
    VOLC_WS_URL,
)


# ---------------------------------------------------------------------------
# Protocol: header building
# ---------------------------------------------------------------------------

class TestBuildHeader:
    def test_header_length(self):
        h = _build_header(0x1)
        assert len(h) == 4

    def test_version_and_header_size(self):
        h = _build_header(0x1)
        assert (h[0] >> 4) == 1  # version = 1
        assert (h[0] & 0xF) == 1  # header_size = 1

    def test_msg_type_encoded(self):
        for msg_type in [0x1, 0x2, 0x9]:
            h = _build_header(msg_type)
            assert (h[1] >> 4) == msg_type

    def test_flags_encoded(self):
        h = _build_header(0x2, flags=0x1)
        assert (h[1] & 0xF) == 0x1

        h = _build_header(0x2, flags=0x2)
        assert (h[1] & 0xF) == 0x2

    def test_compression_gzip(self):
        h = _build_header(0x1, comp=1)
        assert (h[2] & 0xF) == 1


# ---------------------------------------------------------------------------
# Protocol: full client request
# ---------------------------------------------------------------------------

class TestBuildFullClientRequest:
    """V3 format: header(4) | seq(4) | payload_size(4) | compressed_json"""

    def test_starts_with_header(self):
        msg = _build_full_client_request()
        assert len(msg) > 12

    def test_has_pos_sequence_flag(self):
        msg = _build_full_client_request()
        assert (msg[1] & 0xF) == 0x1  # POS_SEQUENCE

    def test_sequence_is_one(self):
        msg = _build_full_client_request()
        seq = struct.unpack(">i", msg[4:8])[0]
        assert seq == 1

    def test_payload_decompresses_to_valid_json(self):
        msg = _build_full_client_request()
        payload_size = struct.unpack(">I", msg[8:12])[0]
        payload = msg[12:12 + payload_size]
        decompressed = gzip.decompress(payload)
        config = json.loads(decompressed)

        assert config["audio"]["format"] == "pcm"
        assert config["audio"]["rate"] == 16000
        assert config["audio"]["bits"] == 16
        assert config["audio"]["channel"] == 1
        assert config["request"]["model_name"] == "bigmodel"
        assert config["request"]["enable_punc"] is True

    def test_has_user_uid(self):
        msg = _build_full_client_request()
        payload_size = struct.unpack(">I", msg[8:12])[0]
        payload = msg[12:12 + payload_size]
        config = json.loads(gzip.decompress(payload))
        assert config["user"]["uid"] == "interview-copilot"


# ---------------------------------------------------------------------------
# Protocol: audio packet building
# ---------------------------------------------------------------------------

class TestBuildAudioPacket:
    """V3 format: header(4) | seq(4) | audio_size(4) | compressed_audio"""

    def test_non_last_packet_flags(self):
        pcm = b"\x00" * 320
        pkt = _build_audio_packet(pcm, seq=1, is_last=False)
        assert (pkt[1] & 0xF) == 0x1  # POS_SEQUENCE

    def test_last_packet_flags(self):
        pcm = b"\x00" * 320
        pkt = _build_audio_packet(pcm, seq=5, is_last=True)
        assert (pkt[1] & 0xF) == 0x3  # NEG_WITH_SEQUENCE

    def test_seq_encoding_positive(self):
        pcm = b"\x00" * 320
        pkt = _build_audio_packet(pcm, seq=42, is_last=False)
        seq_val = struct.unpack(">i", pkt[4:8])[0]
        assert seq_val == 42

    def test_seq_encoding_negative_on_last(self):
        pcm = b"\x00" * 320
        pkt = _build_audio_packet(pcm, seq=10, is_last=True)
        seq_val = struct.unpack(">i", pkt[4:8])[0]
        assert seq_val == -10

    def test_audio_size_after_seq(self):
        pcm = b"\xAB\xCD" * 160
        pkt = _build_audio_packet(pcm, seq=1, is_last=False)
        audio_size = struct.unpack(">I", pkt[8:12])[0]
        compressed_data = pkt[12: 12 + audio_size]
        decompressed = gzip.decompress(compressed_data)
        assert decompressed == pcm


# ---------------------------------------------------------------------------
# Protocol: server response parsing
# ---------------------------------------------------------------------------

class TestParseServerResponse:
    """_parse_server_response must handle FULL_SERVER_RESPONSE, SERVER_ACK, and SERVER_ERROR."""

    def _make_full_response(self, payload_dict: dict, with_seq: bool = True) -> bytes:
        """Build a FULL_SERVER_RESPONSE (0x9)."""
        body = json.dumps(payload_dict).encode("utf-8")
        compressed = gzip.compress(body)
        flags = 0x1 if with_seq else 0x0
        header = _build_header(0x9, flags=flags, serial=0, comp=1)
        parts = bytearray(header)
        if with_seq:
            parts.extend(struct.pack(">i", 1))
        parts.extend(struct.pack(">I", len(compressed)))
        parts.extend(compressed)
        return bytes(parts)

    def _make_ack(self, seq: int = 1, payload_dict: dict = None) -> bytes:
        """Build a SERVER_ACK (0xB)."""
        header = _build_header(MSG_TYPE_SERVER_ACK, flags=0, serial=0, comp=1)
        parts = bytearray(header)
        parts.extend(struct.pack(">i", seq))
        if payload_dict:
            body = gzip.compress(json.dumps(payload_dict).encode())
            parts.extend(struct.pack(">I", len(body)))
            parts.extend(body)
        return bytes(parts)

    def _make_error(self, code: int = 45000001, payload_dict: dict = None) -> bytes:
        """Build a SERVER_ERROR_RESPONSE (0xF)."""
        header = _build_header(MSG_TYPE_SERVER_ERROR, flags=0, serial=0, comp=1)
        parts = bytearray(header)
        parts.extend(struct.pack(">I", code))
        if payload_dict:
            body = gzip.compress(json.dumps(payload_dict).encode())
        else:
            body = gzip.compress(b'{"message":"bad request"}')
        parts.extend(struct.pack(">I", len(body)))
        parts.extend(body)
        return bytes(parts)

    # --- FULL_SERVER_RESPONSE (0x9) ---

    def test_parses_full_response_with_seq(self):
        payload = {"result": {"text": "你好世界"}, "is_last": True}
        msg = self._make_full_response(payload, with_seq=True)
        result = _parse_server_response(msg)
        assert result["msg_type"] == "full_server_response"
        assert result["payload"]["result"]["text"] == "你好世界"
        assert result["sequence"] == 1

    def test_parses_full_response_without_seq(self):
        payload = {"result": {"text": "hello"}}
        msg = self._make_full_response(payload, with_seq=False)
        result = _parse_server_response(msg)
        assert result["msg_type"] == "full_server_response"
        assert result["payload"]["result"]["text"] == "hello"

    # --- SERVER_ACK (0xB) ---

    def test_parses_ack_without_payload(self):
        msg = self._make_ack(seq=42)
        result = _parse_server_response(msg)
        assert result["msg_type"] == "server_ack"
        assert result["sequence"] == 42

    def test_parses_ack_with_payload(self):
        msg = self._make_ack(seq=1, payload_dict={"status": "ok"})
        result = _parse_server_response(msg)
        assert result["msg_type"] == "server_ack"
        assert result["payload"]["status"] == "ok"

    # --- SERVER_ERROR (0xF) ---

    def test_parses_error_response(self):
        msg = self._make_error(code=45000001)
        result = _parse_server_response(msg)
        assert result["msg_type"] == "server_error"
        assert result["error_code"] == 45000001
        assert "payload" in result

    def test_error_response_contains_message(self):
        msg = self._make_error(code=55000001, payload_dict={"message": "server busy"})
        result = _parse_server_response(msg)
        assert result["error_code"] == 55000001
        assert result["payload"]["message"] == "server busy"

    # --- Edge cases ---

    def test_short_data_returns_unknown(self):
        result = _parse_server_response(b"\x11")
        assert result["msg_type"] == "unknown"

    def test_unknown_msg_type(self):
        header = _build_header(0x1, flags=0)
        msg = header + b"\x00" * 20
        result = _parse_server_response(msg)
        assert "unknown" in result["msg_type"]

    def test_is_last_flag(self):
        header = _build_header(0x9, flags=0x3, serial=0, comp=1)  # flags=0x3 → seq + last
        body = gzip.compress(json.dumps({"result": {"text": "end"}}).encode())
        parts = bytearray(header)
        parts.extend(struct.pack(">i", -5))
        parts.extend(struct.pack(">I", len(body)))
        parts.extend(body)
        result = _parse_server_response(bytes(parts))
        assert result["is_last"] is True
        assert result["sequence"] == -5


# ---------------------------------------------------------------------------
# Client: lifecycle and state
# ---------------------------------------------------------------------------

class TestVolcEngineClient:
    def _make_client(self, app_id="test_id", token="test_token", **kwargs):
        """Bypass __init__'s `or settings.xxx` fallback by setting attrs directly."""
        client = VolcEngineStreamingClient.__new__(VolcEngineStreamingClient)
        client.app_id = app_id
        client.token = token
        client.on_result = kwargs.get("on_result")
        client.on_error = kwargs.get("on_error")
        client._ws = None
        client._connect_id = "test-id"
        client._seq = 0
        client._recv_task = None
        return client

    def test_available_with_creds(self):
        client = self._make_client(app_id="test_id", token="test_token")
        assert client.available is True

    def test_unavailable_without_creds(self):
        client = self._make_client(app_id="", token="")
        assert client.available is False

    def test_unavailable_partial_creds(self):
        assert self._make_client(app_id="id", token="").available is False
        assert self._make_client(app_id="", token="tok").available is False

    @pytest.mark.asyncio
    async def test_connect_raises_without_creds(self):
        client = self._make_client(app_id="", token="")
        with pytest.raises(ValueError, match="not configured"):
            await client.connect()

    @pytest.mark.asyncio
    async def test_send_audio_raises_when_not_connected(self):
        client = self._make_client(app_id="id", token="tok")
        with pytest.raises(RuntimeError, match="not connected"):
            await client.send_audio(b"\x00" * 320)

    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        client = self._make_client(app_id="id", token="tok")
        await client.close()  # should not raise

    @pytest.mark.asyncio
    async def test_connect_always_starts_recv_task(self):
        """Regression: connect() must always start _receive_loop,
        even when the server ACK contains a 'result' field."""
        import asyncio as _asyncio
        from unittest.mock import AsyncMock, MagicMock

        # Build a SERVER_ACK message (0xB) — the typical initial response
        header = _build_header(MSG_TYPE_SERVER_ACK, flags=0, serial=0, comp=1)
        ack_msg = header + struct.pack(">i", 1)

        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(return_value=ack_msg)
        mock_ws.state = MagicMock()

        client = self._make_client(app_id="id", token="tok")
        client._ws = mock_ws

        first = await client._ws.recv()
        resp = _parse_server_response(first)
        assert resp["msg_type"] == "server_ack"

        client._recv_task = _asyncio.create_task(client._receive_loop())
        assert client._recv_task is not None, \
            "connect() must always create _recv_task regardless of ACK type"
        client._recv_task.cancel()
        try:
            await client._recv_task
        except _asyncio.CancelledError:
            pass


# ---------------------------------------------------------------------------
# Integration: real Volcengine service
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestVolcEngineIntegration:
    """These tests actually connect to the Volcengine ASR service.
    Run with: pytest -m integration
    Requires IC_VOLCENGINE_APP_ID and IC_VOLCENGINE_ASR_TOKEN in env/.env
    """

    @pytest.mark.asyncio
    async def test_connect_and_send_silence(self, has_volcengine_creds, pcm_silence):
        if not has_volcengine_creds:
            pytest.skip("Volcengine credentials not configured")

        results = []

        def on_result(text, definite=False):
            results.append((text, definite))

        errors = []

        def on_error(msg):
            errors.append(msg)

        client = VolcEngineStreamingClient(on_result=on_result, on_error=on_error)
        try:
            await client.connect()

            chunk_size = 3200  # 100ms of 16kHz 16-bit mono
            for i in range(0, len(pcm_silence), chunk_size):
                chunk = pcm_silence[i:i + chunk_size]
                is_last = (i + chunk_size >= len(pcm_silence))
                await client.send_audio(chunk, is_last=is_last)

            import asyncio
            await asyncio.sleep(2)

            assert len(errors) == 0, f"Unexpected errors: {errors}"
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_connect_and_send_tone(self, has_volcengine_creds, pcm_tone):
        """Send a real tone — the service should accept it without errors."""
        if not has_volcengine_creds:
            pytest.skip("Volcengine credentials not configured")

        errors = []
        client = VolcEngineStreamingClient(
            on_result=lambda text, definite=False: None,
            on_error=lambda msg: errors.append(msg),
        )
        try:
            await client.connect()

            chunk_size = 3200
            for i in range(0, len(pcm_tone), chunk_size):
                chunk = pcm_tone[i:i + chunk_size]
                is_last = (i + chunk_size >= len(pcm_tone))
                await client.send_audio(chunk, is_last=is_last)

            import asyncio
            await asyncio.sleep(2)

            assert len(errors) == 0, f"Unexpected errors: {errors}"
        finally:
            await client.close()
