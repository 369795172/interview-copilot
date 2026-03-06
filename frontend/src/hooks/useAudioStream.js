import { useRef, useCallback, useState, useEffect } from "react";
import { createSession, appendChunk, finishSession } from "../lib/replayStore";
import useInterviewStore from "../stores/interviewStore";

const CHUNK_INTERVAL_MS = 3000;

/**
 * Audio capture hook with IndexedDB replay persistence.
 * Primary: AudioWorklet -> PCM16@16kHz binary frames (for Volcano Engine).
 * Fallback: MediaRecorder -> WebM blobs (for AI Builder Space).
 * Supports live switching from AudioWorklet to MediaRecorder when backend
 * falls back from VolcEngine to AI Builder mid-session.
 */
export default function useAudioStream(onChunk, sessionId) {
  const streamRef = useRef(null);
  const audioCtxRef = useRef(null);
  const workletNodeRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const analyserRef = useRef(null);
  const rafRef = useRef(null);
  const modeRef = useRef("none"); // "worklet" | "mediarecorder" | "none"
  const seqRef = useRef(0);
  const startTimeRef = useRef(0);

  const [isRecording, setIsRecording] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [captureMode, setCaptureMode] = useState("none");

  const _startLevelMeter = useCallback((audioCtx, source) => {
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    analyserRef.current = analyser;
    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    const tick = () => {
      analyser.getByteFrequencyData(dataArray);
      const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
      setAudioLevel(avg / 255);
      rafRef.current = requestAnimationFrame(tick);
    };
    tick();
  }, []);

  const _tryWorklet = useCallback(
    async (stream) => {
      const audioCtx = new AudioContext({ sampleRate: 48000 });
      audioCtxRef.current = audioCtx;
      const source = audioCtx.createMediaStreamSource(stream);

      await audioCtx.audioWorklet.addModule("/audio-processor.worklet.js");
      const workletNode = new AudioWorkletNode(audioCtx, "audio-processor");
      workletNodeRef.current = workletNode;

      workletNode.port.onmessage = (e) => {
        if (e.data?.type === "audio" && e.data.pcm) {
          const blob = new Blob([e.data.pcm], { type: "application/octet-stream" });
          onChunk(blob);
          // Persist to IndexedDB for replay
          seqRef.current++;
          const deltaMs = Date.now() - startTimeRef.current;
          appendChunk(sessionId, seqRef.current, deltaMs, e.data.pcm).catch(() => {});
        }
      };

      source.connect(workletNode);
      workletNode.connect(audioCtx.destination);
      _startLevelMeter(audioCtx, source);
      modeRef.current = "worklet";
      setCaptureMode("worklet");
    },
    [onChunk, _startLevelMeter, sessionId]
  );

  const _fallbackMediaRecorder = useCallback(
    (stream) => {
      const audioCtx = new AudioContext();
      audioCtxRef.current = audioCtx;
      const source = audioCtx.createMediaStreamSource(stream);
      _startLevelMeter(audioCtx, source);

      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = recorder;
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          onChunk(e.data);
          seqRef.current++;
          const deltaMs = Date.now() - startTimeRef.current;
          e.data.arrayBuffer().then((buf) => {
            appendChunk(sessionId, seqRef.current, deltaMs, buf).catch(() => {});
          });
        }
      };
      recorder.start(CHUNK_INTERVAL_MS);
      modeRef.current = "mediarecorder";
      setCaptureMode("mediarecorder");
    },
    [onChunk, _startLevelMeter, sessionId]
  );

  const _switchToMediaRecorder = useCallback(() => {
    const stream = streamRef.current;
    if (!stream || modeRef.current !== "worklet") return;
    console.log("[Audio] Switching from AudioWorklet to MediaRecorder (backend fallback)");
    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    _fallbackMediaRecorder(stream);
  }, [_fallbackMediaRecorder]);

  // Watch for backend STT provider fallback during active recording
  useEffect(() => {
    const unsub = useInterviewStore.subscribe((state, prevState) => {
      const cur = state.sttProvider;
      const prev = prevState?.sttProvider;
      if (
        cur?.provider === "ai_builder" &&
        cur?.status === "fallback" &&
        prev?.provider !== "ai_builder" &&
        modeRef.current === "worklet"
      ) {
        _switchToMediaRecorder();
      }
    });
    return unsub;
  }, [_switchToMediaRecorder]);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, sampleRate: 48000 },
      });
      streamRef.current = stream;
      seqRef.current = 0;
      startTimeRef.current = Date.now();

      if (sessionId) {
        createSession(sessionId).catch((e) => console.warn("[Replay] createSession failed:", e));
      }

      const sttProvider = useInterviewStore.getState().sttProvider;
      const preferWebM = sttProvider?.provider === "ai_builder";

      if (preferWebM) {
        console.log("[Audio] STT provider is ai_builder, using MediaRecorder (WebM)");
        _fallbackMediaRecorder(stream);
      } else if (typeof AudioWorkletNode !== "undefined") {
        try {
          await _tryWorklet(stream);
        } catch (err) {
          console.warn("[Audio] AudioWorklet failed, falling back to MediaRecorder:", err);
          _fallbackMediaRecorder(stream);
        }
      } else {
        _fallbackMediaRecorder(stream);
      }

      setIsRecording(true);
    } catch (err) {
      console.error("Mic access error:", err);
    }
  }, [_tryWorklet, _fallbackMediaRecorder, sessionId]);

  const stopRecording = useCallback(() => {
    const durationMs = Date.now() - startTimeRef.current;
    if (sessionId) {
      finishSession(sessionId, durationMs).catch((e) => console.warn("[Replay] finishSession failed:", e));
    }
    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    modeRef.current = "none";
    setIsRecording(false);
    setAudioLevel(0);
    setCaptureMode("none");
  }, [sessionId]);

  return { isRecording, audioLevel, captureMode, startRecording, stopRecording };
}
