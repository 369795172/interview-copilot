import { useEffect, useRef, useCallback } from "react";
import useInterviewStore from "../stores/interviewStore";

export default function useWebSocket(sessionId) {
  const wsRef = useRef(null);
  const addTranscript = useInterviewStore((s) => s.addTranscript);
  const appendSuggestions = useInterviewStore((s) => s.appendSuggestions);
  const setCurrentSpeaker = useInterviewStore((s) => s.setCurrentSpeaker);
  const setTranscriptionError = useInterviewStore((s) => s.setTranscriptionError);
  const setPartialTranscript = useInterviewStore((s) => s.setPartialTranscript);
  const setSttProvider = useInterviewStore((s) => s.setSttProvider);
  const setWs = useInterviewStore((s) => s.setWs);

  useEffect(() => {
    if (!sessionId) return;

    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const host = window.location.host;
    const url = `${proto}://${host}/ws/interview/${sessionId}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("[WS] Connected", sessionId);
      setWs(ws);
    };

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        switch (msg.type) {
          case "transcript":
            setPartialTranscript(null);
            addTranscript(msg.payload);
            break;
          case "transcript_partial":
            setPartialTranscript(msg.payload);
            break;
          case "copilot_suggestions":
            appendSuggestions(msg.payload.suggestions || []);
            break;
          case "speaker_changed":
            setCurrentSpeaker(msg.payload.speaker);
            break;
          case "transcription_error":
            setTranscriptionError(msg.payload);
            break;
          case "stt_provider":
            setSttProvider(msg.payload);
            break;
          case "pong":
            break;
          default:
            console.log("[WS] Unknown message type:", msg.type);
        }
      } catch (e) {
        console.warn("[WS] Parse error", e);
      }
    };

    ws.onclose = () => {
      console.log("[WS] Disconnected");
      setWs(null);
    };

    // Heartbeat
    const hb = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ping" }));
      }
    }, 25_000);

    return () => {
      clearInterval(hb);
      ws.close();
    };
  }, [sessionId, addTranscript, appendSuggestions, setCurrentSpeaker, setTranscriptionError, setPartialTranscript, setSttProvider, setWs]);

  const sendAudio = useCallback((audioBlob) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      audioBlob.arrayBuffer().then((buf) => ws.send(buf));
    }
  }, []);

  const sendMessage = useCallback((msg) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg));
    }
  }, []);

  return { sendAudio, sendMessage };
}
