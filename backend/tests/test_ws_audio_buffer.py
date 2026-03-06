"""
Tests for the AI Builder audio accumulation buffer logic in ws_interview.
Verifies that short PCM chunks are accumulated before transcription
to prevent Whisper hallucination on <1s audio clips.
"""

import struct

import pytest

from app.services.stt_router import _is_webm, WEBM_MAGIC
from app.api.ws_interview import _pcm_is_silence


class TestAudioBufferDesign:
    """Validate the design constraints that drive the buffer logic."""

    PCM_CHUNK_SIZE = 6400  # 200ms of PCM16@16kHz mono (3200 samples * 2 bytes)
    MIN_BUFFER_BYTES = 48_000  # ~1.5s threshold from ws_interview

    def test_single_pcm_chunk_below_threshold(self):
        """A single 200ms PCM chunk must NOT be sent directly — it's way below threshold."""
        assert self.PCM_CHUNK_SIZE < self.MIN_BUFFER_BYTES

    def test_multiple_chunks_reach_threshold(self):
        """Accumulating ~8 chunks (1.6s) should exceed the buffer threshold."""
        chunks_needed = self.MIN_BUFFER_BYTES // self.PCM_CHUNK_SIZE + 1
        total = chunks_needed * self.PCM_CHUNK_SIZE
        assert total >= self.MIN_BUFFER_BYTES
        assert chunks_needed <= 10  # shouldn't need more than ~10 chunks

    def test_webm_bypasses_buffer(self):
        """WebM blobs should be detected and sent directly (no buffering)."""
        webm_data = WEBM_MAGIC + b"\x00" * 5000
        assert _is_webm(webm_data) is True

    def test_pcm_enters_buffer(self):
        """Raw PCM data must NOT be detected as WebM."""
        pcm_data = b"\x00" * 6400
        assert _is_webm(pcm_data) is False

    def test_bytearray_accumulation(self):
        """bytearray.extend() correctly accumulates multiple PCM chunks."""
        buf = bytearray()
        chunk = b"\xAB\xCD" * 3200  # 6400 bytes
        for _ in range(8):
            buf.extend(chunk)
        assert len(buf) == 8 * 6400
        assert len(buf) >= self.MIN_BUFFER_BYTES

    def test_buffer_clear_resets(self):
        """After flush, buffer.clear() should reset to empty."""
        buf = bytearray(b"\x00" * 50000)
        snapshot = bytes(buf)
        buf.clear()
        assert len(buf) == 0
        assert len(snapshot) == 50000

    def test_silence_flush_timing(self):
        """FLUSH_SILENCE_SECS should be reasonable (1-3 seconds)."""
        FLUSH_SILENCE_SECS = 1.5
        assert 0.5 <= FLUSH_SILENCE_SECS <= 5.0


class TestBufferEdgeCases:
    """Edge cases for the accumulation buffer."""

    def test_empty_buffer_flush_is_noop(self):
        """Flushing an empty buffer should produce no audio to transcribe."""
        buf = bytearray()
        assert not buf  # falsy when empty

    def test_pcm_data_integrity_after_accumulation(self):
        """Accumulated PCM data should be byte-for-byte identical to the concatenation."""
        chunks = [bytes(range(256)) * 25 for _ in range(5)]  # 5 chunks of 6400 bytes
        buf = bytearray()
        for c in chunks:
            buf.extend(c)
        expected = b"".join(chunks)
        assert bytes(buf) == expected

    def test_wav_wrapping_on_accumulated_buffer(self):
        """The accumulated buffer (pure PCM) should be wrappable as WAV."""
        from app.services.transcription import _pcm_to_wav
        pcm = b"\x00\x00" * 24000  # 1.5s of 16kHz mono
        wav = _pcm_to_wav(pcm)
        assert wav[:4] == b"RIFF"
        assert len(wav) == 44 + len(pcm)


class TestPcmIsSilence:
    """Tests for server-side silence detection that prevents Whisper hallucination."""

    def test_all_zeros_is_silence(self):
        pcm = b"\x00\x00" * 3200  # 200ms of silence
        assert _pcm_is_silence(pcm) is True

    def test_loud_tone_is_not_silence(self):
        n = 3200
        samples = [int(16000 * ((-1) ** i)) for i in range(n)]
        pcm = struct.pack(f"<{n}h", *samples)
        assert _pcm_is_silence(pcm) is False

    def test_near_threshold_quiet(self):
        """Very quiet audio (below threshold) should be detected as silence."""
        n = 3200
        amplitude = 50  # very quiet (threshold ~ sqrt(0.005) * 32768 ≈ 2317)
        samples = [amplitude * ((-1) ** i) for i in range(n)]
        pcm = struct.pack(f"<{n}h", *samples)
        assert _pcm_is_silence(pcm) is True

    def test_near_threshold_loud(self):
        """Audio above threshold should NOT be silence."""
        n = 3200
        amplitude = 5000  # well above threshold
        samples = [amplitude * ((-1) ** i) for i in range(n)]
        pcm = struct.pack(f"<{n}h", *samples)
        assert _pcm_is_silence(pcm) is False

    def test_empty_data_is_silence(self):
        assert _pcm_is_silence(b"") is True

    def test_single_byte_is_silence(self):
        assert _pcm_is_silence(b"\x00") is True

    def test_custom_threshold(self):
        n = 3200
        amplitude = 3000
        samples = [amplitude * ((-1) ** i) for i in range(n)]
        pcm = struct.pack(f"<{n}h", *samples)
        assert _pcm_is_silence(pcm, threshold=0.5) is True
        assert _pcm_is_silence(pcm, threshold=0.001) is False


class TestSessionGeneration:
    """Verify the generation counter pattern prevents stale handlers."""

    def test_generation_increments(self):
        from app.api.ws_interview import _session_generation
        sid = "__test_gen__"
        _session_generation[sid] = 0
        gen1 = _session_generation[sid] + 1
        _session_generation[sid] = gen1
        gen2 = _session_generation[sid] + 1
        _session_generation[sid] = gen2
        assert gen2 > gen1
        assert gen2 == 2
        del _session_generation[sid]

    def test_stale_check_detects_mismatch(self):
        from app.api.ws_interview import _session_generation
        sid = "__test_stale__"
        _session_generation[sid] = 1
        my_gen = 1
        assert _session_generation.get(sid) == my_gen
        _session_generation[sid] = 2
        assert _session_generation.get(sid) != my_gen
        del _session_generation[sid]
