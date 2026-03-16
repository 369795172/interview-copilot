"""
WebSocket endpoint for live interview sessions.
Handles: audio chunks in -> transcript + AI insights out.
Supports Volcano Engine streaming ASR (PCM) and AI Builder Space fallback (WebM).
"""

import asyncio
from collections import deque
import json
import logging
import re
import struct
import time
from typing import Dict, Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models.db_models import TranscriptEntry, AIInsight, CopilotLog
from app.services.transcription import TranscriptionService
from app.services.copilot import CopilotEngine
from app.services.memory import MemoryStore
from app.services.stt_router import use_volcengine, create_volcengine_client, _is_webm
from app.services.stt_volcengine import VolcEngineStreamingClient
from websockets.protocol import State as WsState
from app.services.global_context import global_context_store

logger = logging.getLogger(__name__)
router = APIRouter()

active_copilots: Dict[str, CopilotEngine] = {}
_active_ws: Dict[str, WebSocket] = {}
_session_generation: Dict[str, int] = {}

# PCM silence threshold — matches the frontend AudioWorklet VAD_ENERGY_THRESHOLD
_SILENCE_ENERGY_THRESHOLD = 0.005
# Higher threshold for AI Builder path — Whisper hallucinates more on low-energy noise
_AI_BUILDER_SILENCE_THRESHOLD = 0.02

_WHISPER_HALLUCINATION_PATTERNS = [
    re.compile(r"(风声|噪音|噪声|杂音|干扰|背景音|声音).{0,10}(太大|很大|较大|严重|有点大|过大|明显)"),
    re.compile(r"没有听到.{0,6}(清晰|有效|任何)"),
    re.compile(r"(请您?|建议).{0,10}(调整|检查).{0,6}(麦克风|话筒|环境|设备)"),
    re.compile(r"(目前|当前|暂时).{0,8}(没有|无法).{0,8}(听到|识别|检测)"),
    re.compile(r"(听到|检测到).{0,6}(一些|有些).{0,8}(噪音|杂音|干扰|背景)"),
    re.compile(r"(机器|电脑|设备|风扇).{0,10}(声音|噪音|噪声).{0,6}(大|响)"),
    re.compile(r"(风扇|机器|设备).{0,8}(出了问题|有问题|故障)"),
    re.compile(r"继续说话"),
    re.compile(r"音频.{0,6}(不清晰|质量|问题)"),
    re.compile(r"^(谢谢|感谢).{0,4}(收看|观看|聆听|收听)"),
    re.compile(r"(字幕由|本视频由).{0,12}(提供|制作)"),
    re.compile(r"字幕"),
    re.compile(r"(请(点赞|关注|订阅|三连)|欢迎收看|下期再见)"),
    re.compile(r"(谢谢大家|感谢大家|感谢您的)"),
    re.compile(r"^[（(][^）)]{1,8}[）)]$"),
    re.compile(r"^[嗯啊哦哈嘿]{3,}$"),
    re.compile(r"^([\u4e00-\u9fffA-Za-z0-9])\1{3,}$"),
    re.compile(r"[♪♫]"),
]


def _is_whisper_hallucination(text: str) -> bool:
    """Detect common Whisper hallucination patterns (meta-commentary about audio quality)."""
    return any(p.search(text) for p in _WHISPER_HALLUCINATION_PATTERNS)


def _pcm_is_silence(pcm: bytes, threshold: float = _SILENCE_ENERGY_THRESHOLD) -> bool:
    """Return True if the PCM16-LE audio frame is below the energy threshold."""
    if len(pcm) < 2:
        return True
    n_samples = len(pcm) // 2
    samples = struct.unpack(f"<{n_samples}h", pcm[:n_samples * 2])
    energy = sum(s * s for s in samples) / n_samples / (32768.0 * 32768.0)
    return energy < threshold


@router.websocket("/ws/interview/{session_id}")
async def interview_ws(websocket: WebSocket, session_id: str):
    await websocket.accept()
    logger.info("WebSocket connected for session %s", session_id)

    # --- Generation counter: prevents StrictMode race ---
    prev_ws = _active_ws.get(session_id)
    if prev_ws is not None:
        logger.info("Closing stale WebSocket for session %s (StrictMode re-mount)", session_id)
        try:
            await prev_ws.close(code=1000, reason="superseded")
        except Exception:
            pass
    gen = _session_generation.get(session_id, 0) + 1
    _session_generation[session_id] = gen
    _active_ws[session_id] = websocket

    def _is_stale() -> bool:
        return _session_generation.get(session_id) != gen

    transcription_svc = TranscriptionService()
    memory = MemoryStore()

    copilot = active_copilots.get(session_id) or CopilotEngine()
    active_copilots[session_id] = copilot

    # Load global context (company values, project background) + per-session candidate
    from app.api.routes_context import get_context_manager  # lazy to avoid circular import
    gc = global_context_store.load()
    cm = get_context_manager(session_id)
    copilot.load_context(
        company_values=gc.get("company_values", ""),
        project_background=gc.get("project_background", ""),
        candidate_profile=str(cm.candidate_profile) if cm else "",
    )
    if not copilot.transcript_buffer:
        async with async_session() as db:
            tr_result = await db.execute(
                select(TranscriptEntry)
                .where(TranscriptEntry.session_id == session_id)
                .order_by(TranscriptEntry.start_time)
            )
            previous_entries = tr_result.scalars().all()
        for entry in previous_entries:
            copilot.add_transcript(entry.speaker, entry.text)
        if previous_entries:
            logger.info("Restored %d transcript entries into copilot cache for session %s", len(previous_entries), session_id)
    logger.info(
        "Copilot context loaded for session %s: cv=%d chars, pb=%d chars, cp=%d chars",
        session_id,
        len(copilot.company_values),
        len(copilot.project_background),
        len(copilot.candidate_profile),
    )

    session_start = time.time()
    speaker_state = {"current": "interviewer"}
    volc_partial = {"text": "", "full_len": 0}
    volc_consumed = {"offset": 0}
    skip_volc_definitive = {"flag": False}
    analysis_counter = 0
    ANALYSIS_INTERVAL = 3
    transcription_error_count = 0
    recent_ai_builder_texts = deque(maxlen=3)

    volc_client: Optional[VolcEngineStreamingClient] = None
    volc_connected = False
    volc_session_start_time = 0.0
    last_volc_audio_time = 0.0
    volc_keepalive_task: Optional[asyncio.Task] = None
    ROTATE_THRESHOLD_SEC = settings.volc_session_rotate_sec
    VOLC_KEEPALIVE_INTERVAL = 8.0  # seconds between keepalive checks
    VOLC_KEEPALIVE_STALE = 5.0     # send keepalive if no audio for this long
    VOLC_SILENCE_PACKET = b"\x00" * 640  # 20ms of silence PCM16@16kHz mono

    # AI Builder audio buffer — accumulate short PCM chunks before transcribing
    # to avoid Whisper hallucination on short audio clips.
    MIN_AI_BUILDER_BYTES = 96_000  # ~3s of PCM16@16kHz mono
    FLUSH_SILENCE_SECS = 2.0      # flush after this silence gap
    ai_builder_buf = bytearray()
    ai_builder_last_chunk_time = 0.0
    flush_timer_task: Optional[asyncio.Task] = None

    # --- AI Builder buffer flush helper ---
    def _validate_ai_builder_text(result: Dict[str, Any]) -> Optional[str]:
        text = (result.get("text") or "").strip()
        if not text:
            logger.debug("AI Builder transcription empty text")
            return None

        meaningful_text = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "", text)
        min_len = max(1, int(settings.ai_builder_min_text_length))
        if len(meaningful_text) < min_len:
            logger.info(
                "Filtered short AI Builder output (meaningful_len=%d): %s",
                len(meaningful_text),
                text,
            )
            return None

        threshold = float(settings.ai_builder_confidence_threshold)
        confidence = result.get("confidence")
        if confidence is not None:
            try:
                conf_val = float(confidence)
            except (TypeError, ValueError):
                conf_val = None
            if conf_val is not None and conf_val < threshold:
                logger.info("Filtered low-confidence AI Builder output (%.3f): %s", conf_val, text[:80])
                return None

        segment_confidences = []
        for seg in (result.get("segments") or []):
            if not isinstance(seg, dict):
                continue
            seg_conf = seg.get("confidence")
            try:
                if seg_conf is not None:
                    segment_confidences.append(float(seg_conf))
            except (TypeError, ValueError):
                continue
        if segment_confidences:
            avg_conf = sum(segment_confidences) / len(segment_confidences)
            min_conf = min(segment_confidences)
            if avg_conf < threshold and min_conf < max(0.05, threshold - 0.15):
                logger.info(
                    "Filtered low segment-confidence AI Builder output (avg=%.3f, min=%.3f): %s",
                    avg_conf,
                    min_conf,
                    text[:80],
                )
                return None

        if _is_whisper_hallucination(text):
            logger.info("Filtered Whisper hallucination: %s", text[:80])
            return None

        normalized = re.sub(r"\s+", " ", text).strip()
        if normalized in recent_ai_builder_texts:
            logger.info("Filtered repeated AI Builder output: %s", text[:80])
            return None
        recent_ai_builder_texts.append(normalized)
        return text

    async def _handle_ai_builder_result(result: Dict[str, Any], elapsed: float) -> None:
        nonlocal analysis_counter, transcription_error_count
        err = result.get("error")
        if err:
            transcription_error_count += 1
            logger.warning("Transcription error #%d: %s", transcription_error_count, err)
            await websocket.send_json({
                "type": "transcription_error",
                "payload": {"error": err, "count": transcription_error_count},
            })
            return

        text = _validate_ai_builder_text(result)
        if not text:
            return

        spk = speaker_state["current"]
        logger.info("Transcribed [%s]: %s", spk, text[:80])
        entry_id = await _persist_transcript(
            session_id, spk, text, elapsed, copilot, memory,
        )
        await websocket.send_json({
            "type": "transcript",
            "payload": {"id": entry_id, "speaker": spk, "text": text, "time": elapsed},
        })
        analysis_counter += 1
        if analysis_counter >= ANALYSIS_INTERVAL and copilot.available:
            analysis_counter = 0
            asyncio.create_task(_run_analysis(websocket, copilot, session_id))

    async def _flush_ai_builder_buf():
        nonlocal ai_builder_buf
        if not ai_builder_buf:
            return
        audio_snapshot = bytes(ai_builder_buf)
        ai_builder_buf.clear()
        elapsed = round(time.time() - session_start, 2)
        logger.debug("Flushing AI Builder buffer: %d bytes (t=%.1fs)", len(audio_snapshot), elapsed)
        result = await transcription_svc.transcribe(audio_snapshot)
        await _handle_ai_builder_result(result, elapsed)

    async def _silence_flush_timer():
        """Background task: flush the AI Builder buffer after a silence gap."""
        await asyncio.sleep(FLUSH_SILENCE_SECS)
        await _flush_ai_builder_buf()

    async def _commit_volc_partial_and_flush(speaker: str) -> None:
        """Save uncommitted VolcEngine partial and flush AI Builder buffer before switch/restart."""
        nonlocal flush_timer_task, volc_partial, volc_consumed
        if flush_timer_task and not flush_timer_task.done():
            flush_timer_task.cancel()
            flush_timer_task = None
        if ai_builder_buf:
            await _flush_ai_builder_buf()
        if volc_partial["text"]:
            elapsed = round(time.time() - session_start, 2)
            logger.info("Committing VolcEngine partial [%s]: %s", speaker, volc_partial["text"][:80])
            entry_id = await _persist_transcript(
                session_id, speaker, volc_partial["text"], elapsed, copilot, memory,
            )
            await websocket.send_json({
                "type": "transcript",
                "payload": {"id": entry_id, "speaker": speaker, "text": volc_partial["text"], "time": elapsed},
            })
            volc_consumed["offset"] = volc_partial["full_len"]
            volc_partial["text"] = ""
            volc_partial["full_len"] = 0
            skip_volc_definitive["flag"] = True

    async def _volc_keepalive_loop():
        """Send periodic silence packets to VolcEngine to prevent server-side session timeout.
        Also rotates VolcEngine session before ~10min limit when ROTATE_THRESHOLD_SEC > 0.
        """
        nonlocal volc_connected, volc_client, volc_session_start_time, volc_consumed, volc_partial
        while volc_connected and volc_client:
            await asyncio.sleep(VOLC_KEEPALIVE_INTERVAL)
            if not volc_connected or not volc_client:
                break
            elapsed = time.time() - volc_session_start_time
            # Session rotation: rebuild connection before ~10min limit
            if ROTATE_THRESHOLD_SEC > 0 and elapsed >= ROTATE_THRESHOLD_SEC:
                try:
                    logger.info("VolcEngine session rotation at %.1fs for session %s", elapsed, session_id)
                    await _commit_volc_partial_and_flush(speaker_state["current"])
                    old_client = volc_client
                    volc_client = None
                    await old_client.close()
                    new_client = create_volcengine_client(
                        on_result=_on_volc_result_sync,
                        on_error=_on_volc_error,
                    )
                    if new_client:
                        await new_client.connect()
                        volc_client = new_client
                        volc_session_start_time = time.time()
                        volc_consumed["offset"] = 0
                        volc_partial["text"] = ""
                        volc_partial["full_len"] = 0
                        logger.info("VolcEngine session rotated for session %s", session_id)
                    else:
                        volc_connected = False
                        await websocket.send_json({
                            "type": "stt_provider",
                            "payload": {"provider": "ai_builder", "status": "fallback"},
                        })
                        break
                except Exception:
                    logger.exception("VolcEngine session rotation failed, falling back to AI Builder")
                    volc_connected = False
                    volc_client = None
                    try:
                        await websocket.send_json({
                            "type": "stt_provider",
                            "payload": {"provider": "ai_builder", "status": "fallback"},
                        })
                    except Exception:
                        pass
                    break
                continue
            idle = time.time() - last_volc_audio_time
            if idle >= VOLC_KEEPALIVE_STALE:
                try:
                    await volc_client.send_audio(VOLC_SILENCE_PACKET)
                    logger.debug("VolcEngine keepalive sent (idle=%.1fs)", idle)
                except Exception:
                    logger.warning("VolcEngine keepalive failed, marking disconnected")
                    volc_connected = False
                    asyncio.create_task(_do_volc_recovery())
                    break

    # Callback closures for Volcano Engine streaming results.
    # VolcEngine BigModel ASR produces cumulative text — each result contains ALL
    # recognised text from the start of the stream. We track volc_consumed["offset"]
    # so we only process the delta (new text since last committed position).
    _PUNCT_STRIP = " \t\n。，、？！.?!,;；：:"

    async def _on_volc_text(text: str, definite: bool):
        nonlocal analysis_counter
        spk = speaker_state["current"]
        elapsed = round(time.time() - session_start, 2)

        # Handle offset reset (e.g. VolcEngine reconnected with fresh stream)
        if volc_consumed["offset"] > len(text):
            volc_consumed["offset"] = 0

        new_text = text[volc_consumed["offset"]:].lstrip(_PUNCT_STRIP).strip()

        if definite:
            if skip_volc_definitive["flag"]:
                logger.info("Skipping stale VolcEngine definitive after speaker switch (offset %d->%d): %s",
                            volc_consumed["offset"], len(text), text[:80])
                skip_volc_definitive["flag"] = False
                volc_consumed["offset"] = len(text)
                volc_partial["text"] = ""
                volc_partial["full_len"] = 0
                return

            volc_consumed["offset"] = len(text)
            volc_partial["text"] = ""
            volc_partial["full_len"] = 0

            if not new_text:
                return

            logger.info("VolcEngine transcribed [%s]: %s", spk, new_text[:80])
            entry_id = None
            async with async_session() as db:
                entry = TranscriptEntry(
                    session_id=session_id,
                    speaker=spk,
                    text=new_text,
                    start_time=elapsed,
                )
                db.add(entry)
                await db.commit()
                await db.refresh(entry)
                entry_id = entry.id
            copilot.add_transcript(spk, new_text)
            if spk == "interviewer":
                memory.add_question(new_text, session_id)
            await websocket.send_json({
                "type": "transcript",
                "payload": {"id": entry_id, "speaker": spk, "text": new_text, "time": elapsed},
            })
            analysis_counter += 1
            if analysis_counter >= ANALYSIS_INTERVAL and copilot.available:
                analysis_counter = 0
                asyncio.create_task(_run_analysis(websocket, copilot, session_id))
        else:
            volc_partial["text"] = new_text
            volc_partial["full_len"] = len(text)
            if not new_text:
                return
            await websocket.send_json({
                "type": "transcript_partial",
                "payload": {"speaker": spk, "text": new_text, "time": elapsed},
            })

    def _on_volc_result_sync(text: str, definite: bool = False):
        asyncio.create_task(_on_volc_text(text, definite))

    def _on_volc_error(err: str):
        logger.error("VolcEngine ASR error: %s", err)
        asyncio.create_task(_do_volc_recovery())

    async def _do_volc_recovery():
        """Save partial, try restart VolcEngine, fallback to AI Builder on failure."""
        nonlocal volc_client, volc_connected, volc_session_start_time, volc_consumed, volc_partial
        try:
            await _commit_volc_partial_and_flush(speaker_state["current"])
            old_client = volc_client
            volc_client = None
            volc_connected = False
            if old_client:
                try:
                    await old_client.close()
                except Exception:
                    pass
            new_client = create_volcengine_client(
                on_result=_on_volc_result_sync,
                on_error=_on_volc_error,
            )
            if new_client:
                try:
                    await new_client.connect()
                    volc_client = new_client
                    volc_connected = True
                    volc_session_start_time = time.time()
                    volc_consumed["offset"] = 0
                    volc_partial["text"] = ""
                    volc_partial["full_len"] = 0
                    logger.info("VolcEngine reconnected for session %s", session_id)
                    await websocket.send_json({
                        "type": "stt_provider",
                        "payload": {"provider": "volcengine", "status": "reconnected"},
                    })
                    return
                except Exception:
                    logger.exception("VolcEngine reconnect failed")
            logger.info("VolcEngine recovery failed, falling back to AI Builder for session %s", session_id)
            await websocket.send_json({
                "type": "stt_provider",
                "payload": {"provider": "ai_builder", "status": "fallback"},
            })
        except Exception:
            logger.exception("VolcEngine recovery error")
            try:
                await websocket.send_json({
                    "type": "stt_provider",
                    "payload": {"provider": "ai_builder", "status": "fallback"},
                })
            except Exception:
                pass

    # Try to set up Volcano Engine streaming client
    volc_client = create_volcengine_client(
        on_result=_on_volc_result_sync,
        on_error=_on_volc_error,
    )

    try:
        # Checkpoint 1: bail out before expensive VolcEngine connect
        if _is_stale():
            logger.info("Stale handler (gen %d) for session %s, bailing out before connect", gen, session_id)
            return

        if volc_client:
            try:
                await volc_client.connect()

                # Checkpoint 2: bail out if superseded during the connect() await
                if _is_stale():
                    logger.info("Stale handler (gen %d) for session %s, bailing out after connect", gen, session_id)
                    await volc_client.close()
                    return

                volc_connected = True
                volc_session_start_time = time.time()
                last_volc_audio_time = time.time()
                volc_keepalive_task = asyncio.create_task(_volc_keepalive_loop())
                logger.info("VolcEngine ASR connected for session %s", session_id)
                await websocket.send_json({
                    "type": "stt_provider",
                    "payload": {"provider": "volcengine", "status": "connected"},
                })
            except (WebSocketDisconnect, RuntimeError):
                raise
            except Exception:
                logger.exception("VolcEngine ASR connect failed, falling back to AI Builder Space")
                volc_client = None
                volc_connected = False
                await websocket.send_json({
                    "type": "stt_provider",
                    "payload": {"provider": "ai_builder", "status": "fallback"},
                })
        else:
            await websocket.send_json({
                "type": "stt_provider",
                "payload": {"provider": "ai_builder", "status": "active"},
            })

        # Checkpoint 3: bail out before entering main loop
        if _is_stale():
            logger.info("Stale handler (gen %d) for session %s, bailing out before main loop", gen, session_id)
            return

        # Generate opening suggestions in background so the WS loop starts immediately
        if copilot.available and copilot.has_context and not copilot.transcript_buffer:
            asyncio.create_task(
                _send_opening_suggestions(websocket, copilot, session_id)
            )

        while True:
            raw = await websocket.receive()

            if raw.get("type") == "websocket.disconnect":
                break

            if "bytes" in raw and raw["bytes"]:
                audio_data = raw["bytes"]
                elapsed = round(time.time() - session_start, 2)
                fmt = "WebM" if _is_webm(audio_data) else "PCM"

                if volc_connected and volc_client and use_volcengine(audio_data):
                    logger.debug("Audio %s %dB -> VolcEngine (t=%.1fs)", fmt, len(audio_data), elapsed)
                    try:
                        await volc_client.send_audio(audio_data)
                        last_volc_audio_time = time.time()
                    except Exception:
                        logger.exception("VolcEngine send_audio failed, triggering recovery")
                        volc_connected = False
                        asyncio.create_task(_do_volc_recovery())
                else:
                    # WebM blobs (MediaRecorder) are already substantial; send directly.
                    # PCM 200ms chunks must be accumulated to avoid Whisper hallucination.
                    if _is_webm(audio_data):
                        logger.debug("Audio WebM %dB -> AI Builder direct (t=%.1fs)", len(audio_data), elapsed)
                        result = await transcription_svc.transcribe(audio_data)
                        await _handle_ai_builder_result(result, elapsed)
                    else:
                        # Stricter silence gate for AI Builder to prevent Whisper hallucination
                        if _pcm_is_silence(audio_data, _AI_BUILDER_SILENCE_THRESHOLD):
                            continue
                        logger.debug("Audio PCM %dB -> AI Builder buffer (buf=%dB, t=%.1fs)",
                                     len(audio_data), len(ai_builder_buf), elapsed)
                        ai_builder_buf.extend(audio_data)
                        ai_builder_last_chunk_time = time.time()
                        if flush_timer_task and not flush_timer_task.done():
                            flush_timer_task.cancel()
                        if len(ai_builder_buf) >= MIN_AI_BUILDER_BYTES:
                            await _flush_ai_builder_buf()
                        else:
                            flush_timer_task = asyncio.create_task(_silence_flush_timer())

            elif "text" in raw and raw["text"]:
                try:
                    msg = json.loads(raw["text"])
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type", "")

                if msg_type == "speaker_toggle":
                    old_spk = speaker_state["current"]
                    new_spk = msg.get(
                        "speaker",
                        "candidate" if old_spk == "interviewer" else "interviewer",
                    )

                    await _commit_volc_partial_and_flush(old_spk)

                    speaker_state["current"] = new_spk
                    logger.info("Speaker toggle: %s -> %s", old_spk, new_spk)
                    await websocket.send_json({
                        "type": "speaker_changed",
                        "payload": {"speaker": new_spk},
                    })

                elif msg_type == "manual_transcript":
                    text = (msg.get("text") or "").strip()
                    speaker = msg.get("speaker") or speaker_state["current"]
                    if text:
                        elapsed = round(time.time() - session_start, 2)
                        logger.info("Manual transcript [%s]: %s", speaker, text[:80])
                        entry_id = await _persist_transcript(
                            session_id, speaker, text, elapsed, copilot, memory,
                        )
                        await websocket.send_json({
                            "type": "transcript",
                            "payload": {"id": entry_id, "speaker": speaker, "text": text, "time": elapsed},
                        })
                        analysis_counter += 1
                        if analysis_counter >= ANALYSIS_INTERVAL and copilot.available:
                            analysis_counter = 0
                            asyncio.create_task(_run_analysis(websocket, copilot, session_id))

                elif msg_type == "request_analysis":
                    if copilot.available:
                        asyncio.create_task(_run_analysis(websocket, copilot, session_id))

                elif msg_type == "custom_suggestion":
                    content = (msg.get("content") or "").strip()
                    suggestion_type = (msg.get("suggestion_type") or "follow_up_question").strip()
                    priority = (msg.get("priority") or "medium").strip()
                    dimension = (msg.get("dimension") or "").strip()
                    if content:
                        suggestion = {
                            "type": suggestion_type,
                            "content": content,
                            "priority": priority,
                            "dimension": dimension,
                            "source": "manual",
                        }
                        async with async_session() as db:
                            db.add(
                                AIInsight(
                                    session_id=session_id,
                                    insight_type="custom",
                                    content=content,
                                )
                            )
                            db.add(
                                CopilotLog(
                                    session_id=session_id,
                                    log_type="custom_question",
                                    request_summary=content[:500],
                                    response_content=json.dumps([suggestion], ensure_ascii=False),
                                    model_used="manual",
                                )
                            )
                            await db.commit()
                        await websocket.send_json({
                            "type": "copilot_suggestions",
                            "payload": {"suggestions": [suggestion]},
                        })

                elif msg_type == "custom_prompt":
                    content = (msg.get("content") or "").strip()
                    if content:
                        copilot.append_interviewer_memory(content)
                        async with async_session() as db:
                            db.add(
                                CopilotLog(
                                    session_id=session_id,
                                    log_type="custom_prompt",
                                    request_summary=content[:500],
                                    response_content=copilot.interviewer_memory[:2000],
                                    model_used="manual",
                                )
                            )
                            await db.commit()
                        await websocket.send_json({
                            "type": "custom_prompt_updated",
                            "payload": {"active": True},
                        })

                elif msg_type == "ping":
                    def _volc_ws_open(client) -> bool:
                        return bool(client and getattr(client, "_ws", None) and getattr(client._ws, "state", None) == WsState.OPEN)
                    if volc_connected:
                        stt_healthy = _volc_ws_open(volc_client)
                    else:
                        stt_healthy = True  # AI Builder: HTTP, no long-lived connection
                    await websocket.send_json({
                        "type": "pong",
                        "payload": {
                            "stt_provider": "volcengine" if volc_connected else "ai_builder",
                            "stt_healthy": stt_healthy,
                        },
                    })

    except (WebSocketDisconnect, RuntimeError):
        logger.info("WebSocket disconnected for session %s", session_id)
    except Exception:
        logger.exception("WebSocket error for session %s", session_id)
    finally:
        if volc_keepalive_task and not volc_keepalive_task.done():
            volc_keepalive_task.cancel()
        if flush_timer_task and not flush_timer_task.done():
            flush_timer_task.cancel()
        if not _is_stale():
            try:
                await _flush_ai_builder_buf()
            except Exception:
                pass
            active_copilots.pop(session_id, None)
        if _active_ws.get(session_id) is websocket:
            _active_ws.pop(session_id, None)
        if volc_client:
            try:
                await volc_client.close()
            except Exception:
                pass


async def _persist_transcript(
    session_id: str, speaker: str, text: str, elapsed: float,
    copilot: CopilotEngine, memory: MemoryStore,
) -> Optional[str]:
    """Save transcript entry to DB, feed copilot + memory. Returns entry_id."""
    entry_id = None
    async with async_session() as db:
        entry = TranscriptEntry(
            session_id=session_id,
            speaker=speaker,
            text=text,
            start_time=elapsed,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        entry_id = entry.id
    copilot.add_transcript(speaker, text)
    if speaker == "interviewer":
        memory.add_question(text, session_id)
    return entry_id


async def _send_opening_suggestions(
    websocket: WebSocket, copilot: CopilotEngine, session_id: str,
):
    """Generate opening suggestions from context and send via WebSocket (background task)."""
    try:
        logger.info("Generating opening suggestions for session %s ...", session_id)
        opening = await copilot.generate_opening_suggestions(session_id=session_id)
        if opening:
            async with async_session() as db:
                for s in opening:
                    insight = AIInsight(
                        session_id=session_id,
                        insight_type=s.get("type", "opening_question"),
                        content=s.get("content", ""),
                    )
                    db.add(insight)
                await db.commit()
            await websocket.send_json({
                "type": "copilot_suggestions",
                "payload": {"suggestions": opening},
            })
            logger.info("Sent %d opening suggestions for session %s", len(opening), session_id)
        else:
            logger.warning("No opening suggestions generated for session %s", session_id)
    except Exception:
        logger.exception("Opening suggestions failed for session %s", session_id)


async def _run_analysis(websocket: WebSocket, copilot: CopilotEngine, session_id: str):
    """Run copilot analysis and send suggestions via WebSocket."""
    try:
        suggestions = await copilot.analyse(session_id=session_id)
        if suggestions:
            async with async_session() as db:
                for s in suggestions:
                    insight = AIInsight(
                        session_id=session_id,
                        insight_type=s.get("type", "general"),
                        content=s.get("content", ""),
                    )
                    db.add(insight)
                await db.commit()

            await websocket.send_json({
                "type": "copilot_suggestions",
                "payload": {"suggestions": suggestions},
            })
    except Exception:
        logger.exception("Analysis push failed")
