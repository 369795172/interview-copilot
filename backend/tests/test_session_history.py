"""
Tests for session history timeline and pagination.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.api.routes_session import get_history
from app.models.db_models import Base, InterviewSession, TranscriptEntry, AIInsight, CopilotLog


async def _create_session() -> tuple[AsyncSession, Any]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return session_factory(), engine


@pytest.mark.asyncio
async def test_history_merges_three_sources():
    db_session, engine = await _create_session()
    session_id = "sess-1"
    base_time = datetime.now(timezone.utc)

    db_session.add(
        InterviewSession(
            id=session_id,
            status="active",
            created_at=base_time,
        )
    )
    db_session.add(
        TranscriptEntry(
            session_id=session_id,
            speaker="interviewer",
            text="请先介绍一个你最有挑战的项目。",
            start_time=1.0,
            created_at=base_time + timedelta(seconds=1),
        )
    )
    db_session.add(
        AIInsight(
            session_id=session_id,
            insight_type="follow_up_question",
            content="追问候选人量化结果。",
            created_at=base_time + timedelta(seconds=2),
        )
    )
    db_session.add(
        CopilotLog(
            session_id=session_id,
            log_type="analysis",
            request_summary="Current transcript ...",
            response_content='[{"type":"follow_up_question","content":"请给出数据指标"}]',
            model_used="deepseek/deepseek-chat-v3-0324",
            created_at=base_time + timedelta(seconds=3),
        )
    )
    await db_session.commit()

    history = await get_history(session_id=session_id, limit=200, offset=0, db=db_session)
    assert len(history) == 3
    assert [item["type"] for item in history] == ["transcript", "ai_insight", "copilot_log"]

    await db_session.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_history_supports_limit_offset():
    db_session, engine = await _create_session()
    session_id = "sess-2"
    base_time = datetime.now(timezone.utc)
    db_session.add(InterviewSession(id=session_id, status="active", created_at=base_time))

    for idx in range(5):
        db_session.add(
            TranscriptEntry(
                session_id=session_id,
                speaker="candidate",
                text=f"answer-{idx}",
                start_time=float(idx),
                created_at=base_time + timedelta(seconds=idx),
            )
        )
    await db_session.commit()

    page = await get_history(session_id=session_id, limit=2, offset=1, db=db_session)
    assert len(page) == 2
    assert page[0]["payload"]["text"] == "answer-1"
    assert page[1]["payload"]["text"] == "answer-2"

    await db_session.close()
    await engine.dispose()
