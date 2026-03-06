export default function TranscriptEntry({ entry }) {
  const isInterviewer = entry.speaker === "interviewer";
  const color = isInterviewer ? "var(--interviewer)" : "var(--candidate)";
  const mins = entry.time != null ? Math.floor(entry.time / 60) : 0;
  const secs = entry.time != null ? Math.floor(entry.time % 60) : 0;
  const ts = `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;

  return (
    <div
      style={{
        padding: "0.4rem 0.6rem",
        marginBottom: "0.25rem",
        borderRadius: "var(--radius)",
        background: isInterviewer ? "rgba(116,185,255,0.05)" : "rgba(85,239,196,0.05)",
        borderLeft: `3px solid ${color}`,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.15rem" }}>
        <span
          className={`badge ${isInterviewer ? "badge-interviewer" : "badge-candidate"}`}
          style={{ textTransform: "capitalize" }}
        >
          {entry.speaker}
        </span>
        <span style={{ fontSize: "0.7rem", color: "var(--text-dim)", fontFamily: "monospace" }}>{ts}</span>
      </div>
      <p style={{ fontSize: "0.85rem", lineHeight: 1.5 }}>{entry.text}</p>
    </div>
  );
}
