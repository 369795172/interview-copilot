"""
Volcano Engine BigModel Streaming ASR client.
WebSocket to openspeech.bytedance.com with binary protocol.

Protocol reference: https://github.com/aiyou178/volcengine-audio (volcengine-audio SDK)
"""

import asyncio
import gzip
import json
import logging
import struct
import uuid
from typing import Optional, Dict, Any

import websockets
from websockets.protocol import State as WsState

from app.config import settings

logger = logging.getLogger(__name__)

# BigModel ASR endpoint — must use /sauc/bigmodel (real-time streaming).
# /sauc/bigmodel_async is NON-streaming and will close the connection.
VOLC_WS_URL = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel"
X_API_RESOURCE_ID = "volc.bigasr.sauc.duration"

# --- Protocol message types (byte 1, upper nibble) ---
MSG_TYPE_FULL_CLIENT_REQUEST = 0x1
MSG_TYPE_AUDIO_ONLY_REQUEST = 0x2
MSG_TYPE_FULL_SERVER_RESPONSE = 0x9
MSG_TYPE_SERVER_ACK = 0xB
MSG_TYPE_SERVER_ERROR = 0xF


def _build_header(msg_type: int, flags: int = 0, serial: int = 0, comp: int = 1) -> bytes:
    """Build 4-byte protocol header."""
    byte0 = (1 << 4) | 1  # version=1, header_size=1
    byte1 = (msg_type << 4) | (flags & 0xF)
    byte2 = (serial << 4) | (comp & 0xF)
    byte3 = 0
    return bytes([byte0, byte1, byte2, byte3])


def _build_full_client_request() -> bytes:
    """Build initial JSON config for PCM 16kHz mono (V3 format).

    Wire format: header(4) | sequence(4) | payload_size(4) | compressed_json
    Sequence=1 for the initial request per V3 convention.
    """
    request_cfg: Dict[str, Any] = {
        "model_name": "bigmodel",
        "enable_itn": True,
        "enable_punc": True,
        "enable_ddc": False,
    }
    hotwords_str = (settings.volcengine_hotwords or "").strip()
    if hotwords_str:
        hotwords_list = [w.strip() for w in hotwords_str.split(",") if w.strip()]
        if hotwords_list:
            request_cfg["hotwords"] = hotwords_list

    payload = {
        "user": {"uid": "interview-copilot"},
        "audio": {
            "format": "pcm",
            "rate": 16000,
            "bits": 16,
            "channel": 1,
        },
        "request": request_cfg,
    }
    body = json.dumps(payload).encode("utf-8")
    compressed = gzip.compress(body)
    header = _build_header(0x1, flags=0x1, serial=1, comp=1)  # POS_SEQUENCE
    seq = struct.pack(">i", 1)
    size = struct.pack(">I", len(compressed))
    return header + seq + size + compressed


def _build_audio_packet(pcm_data: bytes, seq: int, is_last: bool = False) -> bytes:
    """Build audio-only message (V3 format).

    Wire format: header(4) | sequence(4) | audio_size(4) | compressed_audio
    """
    compressed = gzip.compress(pcm_data)
    # POS_SEQUENCE=0x1 for normal, NEG_WITH_SEQUENCE=0x3 for last
    flags = 0x3 if is_last else 0x1
    header = _build_header(0x2, flags=flags, serial=0, comp=1)
    seq_val = -seq if is_last else seq
    return header + struct.pack(">i", seq_val) + struct.pack(">I", len(compressed)) + compressed


def _parse_server_response(data: bytes) -> Dict[str, Any]:
    """Parse any server response (ACK / full response / error).

    Returns a dict that always contains ``"msg_type"`` (str) and may contain:
    - ``"sequence"`` (int) if the message carried a sequence number
    - ``"payload"`` (dict | str) – parsed JSON body when available
    - ``"error_code"`` (int) – for SERVER_ERROR messages
    - ``"is_last"`` (bool) – True when NEG_SEQUENCE flag is set
    """
    if len(data) < 4:
        return {"msg_type": "unknown", "raw_len": len(data)}

    header_size = data[0] & 0x0F  # in 32-bit words
    msg_type = (data[1] >> 4) & 0xF
    flags = data[1] & 0xF
    compression = data[2] & 0xF

    result: Dict[str, Any] = {"msg_type": _msg_type_name(msg_type), "is_last": False}

    payload = data[header_size * 4:]  # everything after header

    # Consume optional sequence (flags bit-0 set, or specific to ACK/error)
    if flags & 0x01:
        if len(payload) >= 4:
            result["sequence"] = struct.unpack(">i", payload[:4])[0]
            payload = payload[4:]
    if flags & 0x02:
        result["is_last"] = True

    payload_msg = None

    if msg_type == MSG_TYPE_FULL_SERVER_RESPONSE:
        if len(payload) >= 4:
            payload_size = struct.unpack(">I", payload[:4])[0]
            payload_msg = payload[4: 4 + payload_size] if payload_size else None

    elif msg_type == MSG_TYPE_SERVER_ACK:
        # ACK always carries a sequence even without flags bit
        if "sequence" not in result and len(payload) >= 4:
            result["sequence"] = struct.unpack(">i", payload[:4])[0]
            payload = payload[4:]
        if len(payload) >= 4:
            payload_size = struct.unpack(">I", payload[:4])[0]
            payload_msg = payload[4: 4 + payload_size] if payload_size else None

    elif msg_type == MSG_TYPE_SERVER_ERROR:
        if len(payload) >= 4:
            result["error_code"] = struct.unpack(">I", payload[:4])[0]
            payload = payload[4:]
        if len(payload) >= 4:
            payload_size = struct.unpack(">I", payload[:4])[0]
            payload_msg = payload[4: 4 + payload_size] if payload_size else None

    else:
        return result  # unknown type, return what we have

    # Decompress + deserialise payload
    if payload_msg is not None:
        try:
            if compression == 1:  # GZIP
                payload_msg = gzip.decompress(payload_msg)
            result["payload"] = json.loads(payload_msg.decode("utf-8"))
        except Exception:
            result["payload_raw"] = payload_msg.hex()[:200]

    return result


def _msg_type_name(t: int) -> str:
    return {
        MSG_TYPE_FULL_SERVER_RESPONSE: "full_server_response",
        MSG_TYPE_SERVER_ACK: "server_ack",
        MSG_TYPE_SERVER_ERROR: "server_error",
    }.get(t, f"unknown_{t:#x}")


class VolcEngineStreamingClient:
    """Async client for Volcano Engine BigModel streaming ASR."""

    def __init__(
        self,
        app_id: Optional[str] = None,
        token: Optional[str] = None,
        on_result=None,
        on_error=None,
    ):
        self.app_id = app_id or settings.volcengine_app_id
        self.token = token or settings.volcengine_asr_token
        self.on_result = on_result
        self.on_error = on_error
        self._ws = None
        self._connect_id = str(uuid.uuid4())
        self._seq = 1  # FullClientRequest uses seq=1; audio starts at 2
        self._recv_task: Optional[asyncio.Task] = None

    @property
    def available(self) -> bool:
        return bool(self.app_id and self.token)

    async def connect(self) -> None:
        if not self.available:
            raise ValueError("VolcEngine ASR not configured (missing app_id or token)")
        headers = {
            "X-Api-App-Key": self.app_id,
            "X-Api-Access-Key": self.token,
            "X-Api-Resource-Id": X_API_RESOURCE_ID,
            "X-Api-Connect-Id": self._connect_id,
        }
        self._ws = await websockets.connect(
            VOLC_WS_URL,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        )
        logger.info("VolcEngine WS opened (id=%s, state=%s)", self._connect_id[:8], self._ws.state.name)
        init_msg = _build_full_client_request()
        await self._ws.send(init_msg)
        first = await self._ws.recv()
        if isinstance(first, str):
            first = first.encode()
        resp = _parse_server_response(first)
        logger.info("VolcEngine ACK (id=%s): %s", self._connect_id[:8], resp)

        if resp.get("msg_type") == "server_error":
            code = resp.get("error_code", "?")
            detail = resp.get("payload", resp.get("payload_raw", ""))
            raise RuntimeError(f"VolcEngine server error {code}: {detail}")

        self._recv_task = asyncio.create_task(self._receive_loop())

    async def _receive_loop(self) -> None:
        logger.info("VolcEngine _receive_loop started (id=%s, ws_state=%s)",
                     self._connect_id[:8], self._ws.state.name if self._ws else "no_ws")
        try:
            while self._ws and self._ws.state == WsState.OPEN:
                msg = await self._ws.recv()
                if isinstance(msg, str):
                    continue
                resp = _parse_server_response(msg)
                mt = resp.get("msg_type", "")

                if mt == "server_error":
                    logger.error("VolcEngine server error in stream: %s", resp)
                    if self.on_error:
                        self.on_error(f"server error {resp.get('error_code')}")
                    break

                if mt == "server_ack":
                    logger.debug("VolcEngine stream ACK: %s", resp)
                    continue

                # full_server_response — extract recognition result
                payload = resp.get("payload")
                if payload and self.on_result:
                    result = payload.get("result", {})
                    text = result.get("text", "").strip()
                    if text:
                        definite = bool(payload.get("is_last") or resp.get("is_last"))
                        self.on_result(text, definite=definite)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception("VolcEngine receive error")
            if self.on_error:
                self.on_error(str(e))
        finally:
            state = self._ws.state.name if self._ws else "no_ws"
            logger.info("VolcEngine _receive_loop exited (ws_state=%s, id=%s)", state, self._connect_id[:8])

    async def send_audio(self, pcm_data: bytes, is_last: bool = False) -> None:
        if not self._ws:
            raise RuntimeError("VolcEngine not connected (ws=None)")
        if self._ws.state != WsState.OPEN:
            raise RuntimeError(f"VolcEngine not connected (ws_state={self._ws.state.name}, id={self._connect_id[:8]})")
        self._seq += 1
        packet = _build_audio_packet(pcm_data, self._seq, is_last=is_last)
        await self._ws.send(packet)

    async def close(self) -> None:
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()
            self._ws = None
