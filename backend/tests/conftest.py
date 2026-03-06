"""
Shared fixtures for STT service tests.
"""

import os
import struct
import pytest

from app.config import Settings


SAMPLE_RATE = 16000
CHANNELS = 1
BITS = 16


def generate_pcm_silence(duration_seconds: float = 1.0) -> bytes:
    """Generate silent PCM audio (16-bit, 16kHz, mono)."""
    num_samples = int(SAMPLE_RATE * duration_seconds)
    return b"\x00\x00" * num_samples


def generate_pcm_tone(duration_seconds: float = 1.0, frequency: int = 440) -> bytes:
    """Generate a sine-wave PCM tone for more realistic audio testing."""
    import math

    num_samples = int(SAMPLE_RATE * duration_seconds)
    samples = []
    for i in range(num_samples):
        value = int(16000 * math.sin(2 * math.pi * frequency * i / SAMPLE_RATE))
        samples.append(struct.pack("<h", value))
    return b"".join(samples)


WEBM_HEADER = bytes([0x1A, 0x45, 0xDF, 0xA3]) + b"\x00" * 100


@pytest.fixture
def pcm_silence():
    return generate_pcm_silence(0.5)


@pytest.fixture
def pcm_tone():
    return generate_pcm_tone(1.0, 440)


@pytest.fixture
def webm_fake():
    return WEBM_HEADER


@pytest.fixture
def has_ai_builder_creds() -> bool:
    s = Settings()
    return bool(s.ai_builder_token)


@pytest.fixture
def has_volcengine_creds() -> bool:
    s = Settings()
    return bool(s.volcengine_app_id and s.volcengine_asr_token)
