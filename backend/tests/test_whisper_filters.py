"""
Tests for Whisper hallucination filtering patterns.
"""

from app.api.ws_interview import _is_whisper_hallucination


def test_matches_audio_quality_meta_hallucination():
    assert _is_whisper_hallucination("当前没有听到清晰的声音，请检查麦克风。") is True


def test_matches_platform_style_hallucination():
    assert _is_whisper_hallucination("感谢大家收看，记得点赞关注订阅。") is True


def test_matches_repeated_filler():
    assert _is_whisper_hallucination("嗯嗯嗯嗯") is True


def test_matches_music_marker():
    assert _is_whisper_hallucination("♪") is True


def test_matches_parenthesized_noise_annotation():
    assert _is_whisper_hallucination("（噪音）") is True


def test_matches_machine_fan_noise_meta_description():
    assert _is_whisper_hallucination("这台机器的声音有点大，我们来看看是不是风扇出了问题。") is True


def test_matches_video_subtitle_meta():
    assert _is_whisper_hallucination("字幕由AI识别提供") is True


def test_keeps_normal_interview_text():
    assert _is_whisper_hallucination("你在上一个项目里是如何做性能优化的？") is False
