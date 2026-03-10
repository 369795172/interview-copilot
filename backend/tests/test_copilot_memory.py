"""
Tests for manual copilot memory updates.
"""

from app.services.copilot import CopilotEngine


def test_append_interviewer_memory_first_entry():
    copilot = CopilotEngine()
    copilot.append_interviewer_memory("优先验证候选人在高并发下的排障能力。")
    assert copilot.interviewer_memory == "优先验证候选人在高并发下的排障能力。"


def test_append_interviewer_memory_appends_with_newline():
    copilot = CopilotEngine()
    copilot.append_interviewer_memory("先考察系统设计。")
    copilot.append_interviewer_memory("再验证 AI 输出校验习惯。")
    assert copilot.interviewer_memory == "先考察系统设计。\n再验证 AI 输出校验习惯。"


def test_append_interviewer_memory_ignores_blank():
    copilot = CopilotEngine()
    copilot.append_interviewer_memory("   ")
    assert copilot.interviewer_memory == ""
