import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Square, Mic, MicOff, User, UserCheck, RefreshCw, RotateCcw, Send } from "lucide-react";
import useWebSocket from "../hooks/useWebSocket";
import useAudioStream from "../hooks/useAudioStream";
import useInterview from "../hooks/useInterview";
import useInterviewStore from "../stores/interviewStore";
import TranscriptPanel from "../components/transcript/TranscriptPanel";
import CopilotPanel from "../components/copilot/CopilotPanel";
import ScoreCard from "../components/evaluation/ScoreCard";
import { getLatestSession, getSessionChunks, hasReplayData } from "../lib/replayStore";

export default function LiveInterview() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const { endSession, fetchCoverage, fetchTranscript, fetchHistory } = useInterview();
  const { sendAudio, sendMessage } = useWebSocket(sessionId);
  const { isRecording, audioLevel, captureMode, startRecording, stopRecording } = useAudioStream(sendAudio, sessionId);

  const transcript = useInterviewStore((s) => s.transcript);
  const currentSpeaker = useInterviewStore((s) => s.currentSpeaker);
  const suggestions = useInterviewStore((s) => s.suggestions);
  const setCurrentSpeaker = useInterviewStore((s) => s.setCurrentSpeaker);
  const setSuggestions = useInterviewStore((s) => s.setSuggestions);

  useEffect(() => {
    let cancelled = false;
    async function restoreSessionState() {
      try {
        await fetchTranscript(sessionId);
        const history = await fetchHistory(sessionId);
        if (cancelled || !Array.isArray(history)) return;
        const restoredSuggestions = history
          .filter((item) => item?.type === "ai_insight")
          .map((item) => ({
            type: item?.payload?.insight_type || "real_time_insight",
            content: item?.payload?.content || "",
            priority: "medium",
            dimension: "",
          }))
          .filter((item) => item.content);
        if (restoredSuggestions.length > 0) {
          setSuggestions(restoredSuggestions);
        }
      } catch (err) {
        console.warn("[LiveInterview] restore state failed:", err);
      }
    }
    if (sessionId) {
      restoreSessionState();
    }
    return () => {
      cancelled = true;
    };
  }, [sessionId, fetchTranscript, fetchHistory, setSuggestions]);

  const [elapsed, setElapsed] = useState(0);
  const [isReplaying, setIsReplaying] = useState(false);
  const [replayAvailable, setReplayAvailable] = useState(false);
  const [replayProgress, setReplayProgress] = useState(0);
  const [manualText, setManualText] = useState("");
  const [manualSpeaker, setManualSpeaker] = useState("interviewer");
  const timerRef = useRef(null);

  useEffect(() => {
    timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(timerRef.current);
  }, []);

  useEffect(() => {
    const iv = setInterval(() => fetchCoverage(sessionId), 30_000);
    fetchCoverage(sessionId);
    return () => clearInterval(iv);
  }, [sessionId, fetchCoverage]);

  useEffect(() => {
    hasReplayData().then(setReplayAvailable).catch(() => {});
  }, [isRecording]);

  const toggleSpeaker = () => {
    const next = currentSpeaker === "interviewer" ? "candidate" : "interviewer";
    console.log("[Speaker] toggle %s -> %s", currentSpeaker, next);
    setCurrentSpeaker(next);
    sendMessage({ type: "speaker_toggle", speaker: next });
  };

  const handleEnd = async () => {
    stopRecording();
    await endSession(sessionId);
    navigate(`/review/${sessionId}`);
  };

  const requestAnalysis = () => {
    sendMessage({ type: "request_analysis" });
  };

  const submitManualTranscript = () => {
    const text = manualText.trim();
    if (!text) return;
    sendMessage({ type: "manual_transcript", speaker: manualSpeaker, text });
    setManualText("");
  };

  const handleReplay = useCallback(async () => {
    if (isReplaying || isRecording) return;
    const latest = await getLatestSession();
    if (!latest) return;

    setIsReplaying(true);
    setReplayProgress(0);
    try {
      const chunks = await getSessionChunks(latest.id);
      if (chunks.length === 0) {
        setIsReplaying(false);
        return;
      }
      for (let i = 0; i < chunks.length; i++) {
        const chunk = chunks[i];
        if (i > 0) {
          const delay = chunk.deltaMs - chunks[i - 1].deltaMs;
          if (delay > 0) {
            await new Promise((r) => setTimeout(r, Math.min(delay, 500)));
          }
        }
        const blob = new Blob([chunk.payload], { type: "application/octet-stream" });
        sendAudio(blob);
        setReplayProgress(Math.round(((i + 1) / chunks.length) * 100));
      }
    } catch (err) {
      console.error("[Replay] error:", err);
    } finally {
      setIsReplaying(false);
      setReplayProgress(0);
    }
  }, [isReplaying, isRecording, sendAudio]);

  const fmtTime = (s) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  };

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
      {/* Top bar */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0.5rem 1rem",
          borderBottom: "1px solid var(--border)",
          background: "var(--bg-card)",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <span style={{ fontWeight: 700 }}>Interview Copilot</span>
          <span style={{ color: "var(--text-dim)", fontFamily: "monospace" }}>{fmtTime(elapsed)}</span>
          {captureMode !== "none" && (
            <span
              style={{
                fontSize: "0.7rem",
                padding: "0.1rem 0.35rem",
                borderRadius: "var(--radius)",
                background: "rgba(116,185,255,0.12)",
                color: "var(--accent)",
              }}
            >
              {captureMode === "worklet" ? "PCM" : "WebM"}
            </span>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {/* Speaker toggle */}
          <button
            className="btn btn-outline btn-sm"
            onClick={toggleSpeaker}
            title="Toggle speaker"
          >
            {currentSpeaker === "interviewer" ? (
              <><UserCheck size={14} style={{ color: "var(--interviewer)" }} /> Interviewer</>
            ) : (
              <><User size={14} style={{ color: "var(--candidate)" }} /> Candidate</>
            )}
          </button>

          {/* Record button */}
          <button
            className={`btn btn-sm ${isRecording ? "btn-danger" : "btn-primary"}`}
            onClick={isRecording ? stopRecording : startRecording}
            disabled={isReplaying}
          >
            {isRecording ? <><MicOff size={14} /> Stop</> : <><Mic size={14} /> Record</>}
          </button>

          {/* Audio level indicator */}
          {isRecording && (
            <div
              style={{
                width: 40,
                height: 8,
                background: "var(--border)",
                borderRadius: 4,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${audioLevel * 100}%`,
                  height: "100%",
                  background: audioLevel > 0.5 ? "var(--success)" : "var(--accent)",
                  transition: "width 0.1s",
                }}
              />
            </div>
          )}

          {/* Replay button */}
          {replayAvailable && !isRecording && (
            <button
              className="btn btn-outline btn-sm"
              onClick={handleReplay}
              disabled={isReplaying}
              title="Replay last recording"
              style={{ position: "relative" }}
            >
              <RotateCcw size={14} className={isReplaying ? "spin" : ""} />
              {isReplaying ? ` ${replayProgress}%` : " Replay"}
            </button>
          )}

          {/* Request analysis */}
          <button className="btn btn-outline btn-sm" onClick={requestAnalysis} title="Request AI analysis">
            <RefreshCw size={14} />
          </button>

          {/* End */}
          <button className="btn btn-danger btn-sm" onClick={handleEnd}>
            <Square size={14} /> End
          </button>
        </div>
      </header>

      {/* 3-panel body */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Left: Transcript + manual input */}
        <div
          style={{
            flex: "1 1 38%",
            borderRight: "1px solid var(--border)",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          <TranscriptPanel entries={transcript} />
          {/* Manual transcript input */}
          <div
            style={{
              flexShrink: 0,
              borderTop: "1px solid var(--border)",
              padding: "0.4rem 0.5rem",
              display: "flex",
              gap: "0.35rem",
              alignItems: "center",
              background: "var(--bg-card)",
            }}
          >
            <button
              className="btn btn-outline btn-sm"
              onClick={() => setManualSpeaker(manualSpeaker === "interviewer" ? "candidate" : "interviewer")}
              style={{
                flexShrink: 0,
                minWidth: 90,
                borderColor: manualSpeaker === "interviewer" ? "var(--interviewer)" : "var(--candidate)",
                color: manualSpeaker === "interviewer" ? "var(--interviewer)" : "var(--candidate)",
              }}
              title="Toggle input speaker"
            >
              {manualSpeaker === "interviewer" ? (
                <><UserCheck size={12} /> I</>
              ) : (
                <><User size={12} /> C</>
              )}
            </button>
            <input
              type="text"
              value={manualText}
              onChange={(e) => setManualText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitManualTranscript(); } }}
              placeholder="Type transcript manually..."
              style={{
                flex: 1,
                padding: "0.3rem 0.5rem",
                fontSize: "0.8rem",
              }}
            />
            <button
              className="btn btn-primary btn-sm"
              onClick={submitManualTranscript}
              disabled={!manualText.trim()}
              style={{ flexShrink: 0 }}
            >
              <Send size={12} />
            </button>
          </div>
        </div>

        {/* Center: Copilot */}
        <div
          style={{
            flex: "1 1 32%",
            borderRight: "1px solid var(--border)",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          <CopilotPanel suggestions={suggestions} sendMessage={sendMessage} />
        </div>

        {/* Right: Evaluation */}
        <div
          style={{
            flex: "1 1 30%",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          <ScoreCard sessionId={sessionId} transcript={transcript} />
        </div>
      </div>
    </div>
  );
}
