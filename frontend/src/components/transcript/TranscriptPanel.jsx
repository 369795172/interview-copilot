import { useEffect, useRef } from "react";
import TranscriptEntry from "./TranscriptEntry";
import useInterviewStore from "../../stores/interviewStore";

export default function TranscriptPanel({ entries }) {
  const bottomRef = useRef(null);
  const transcriptionError = useInterviewStore((s) => s.transcriptionError);
  const partialTranscript = useInterviewStore((s) => s.partialTranscript);
  const sttProvider = useInterviewStore((s) => s.sttProvider);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries.length, partialTranscript]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div
        style={{
          padding: "0.6rem 1rem",
          borderBottom: "1px solid var(--border)",
          fontWeight: 600,
          fontSize: "0.85rem",
          color: "var(--text-dim)",
          flexShrink: 0,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span>Transcript ({entries.length})</span>
        {sttProvider && (
          <span
            style={{
              fontSize: "0.7rem",
              padding: "0.15rem 0.4rem",
              borderRadius: "var(--radius)",
              background:
                sttProvider.status === "connected"
                  ? "rgba(85,239,196,0.15)"
                  : sttProvider.status === "fallback"
                  ? "rgba(253,203,110,0.2)"
                  : "rgba(116,185,255,0.15)",
              color:
                sttProvider.status === "connected"
                  ? "var(--success)"
                  : sttProvider.status === "fallback"
                  ? "var(--warning, #e17055)"
                  : "var(--accent)",
            }}
          >
            STT: {sttProvider.provider}
          </span>
        )}
      </div>
      {transcriptionError && (
        <div
          style={{
            padding: "0.5rem 1rem",
            background: "rgba(220, 53, 69, 0.15)",
            borderBottom: "1px solid var(--danger)",
            fontSize: "0.8rem",
            color: "var(--danger)",
            flexShrink: 0,
          }}
        >
          Transcription error ({transcriptionError.count}): {transcriptionError.error}
        </div>
      )}
      <div style={{ flex: 1, overflow: "auto", padding: "0.5rem" }}>
        {entries.length === 0 && !partialTranscript && (
          <p style={{ color: "var(--text-dim)", textAlign: "center", padding: "2rem 1rem", fontSize: "0.85rem" }}>
            Start recording to see the transcript here...
          </p>
        )}
        {entries.map((e, i) => (
          <TranscriptEntry key={e.id || i} entry={e} />
        ))}
        {partialTranscript && (
          <div
            style={{
              padding: "0.4rem 0.6rem",
              marginBottom: "0.25rem",
              borderRadius: "var(--radius)",
              background: "rgba(116,185,255,0.03)",
              borderLeft: "3px solid rgba(116,185,255,0.3)",
              opacity: 0.65,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.15rem" }}>
              <span
                className="badge"
                style={{ textTransform: "capitalize", fontSize: "0.7rem", opacity: 0.7 }}
              >
                {partialTranscript.speaker}
              </span>
              <span
                style={{
                  display: "inline-block",
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: "var(--accent)",
                  animation: "pulse 1.2s infinite",
                }}
              />
            </div>
            <p style={{ fontSize: "0.85rem", lineHeight: 1.5, fontStyle: "italic" }}>
              {partialTranscript.text}
            </p>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
