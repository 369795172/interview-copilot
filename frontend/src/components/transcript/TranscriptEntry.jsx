export default function TranscriptEntry({ entry }) {
  const isInterviewer = entry.speaker === "interviewer";
  const color = isInterviewer ? "var(--interviewer)" : "var(--candidate)";
  const mins = entry.time != null ? Math.floor(entry.time / 60) : 0;
  const secs = entry.time != null ? Math.floor(entry.time % 60) : 0;
  const ts = `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;

  if (isInterviewer) {
    return (
      <div
        style={{
          padding: "0.25rem 0.5rem",
          marginBottom: "0.2rem",
          borderRadius: "var(--radius)",
          background: "rgba(116,185,255,0.03)",
          borderLeft: "2px solid rgba(116,185,255,0.4)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
          <span
            className="badge badge-interviewer"
            style={{
              fontSize: "0.65rem",
              padding: "0.1rem 0.35rem",
              opacity: 0.85,
            }}
          >
            Q
          </span>
          <span style={{ fontSize: "0.65rem", color: "var(--text-dim)", fontFamily: "monospace" }}>{ts}</span>
          <span style={{ fontSize: "0.78rem", lineHeight: 1.4, color: "var(--text)" }}>{entry.text}</span>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        padding: "0.4rem 0.6rem",
        marginBottom: "0.25rem",
        borderRadius: "var(--radius)",
        background: "rgba(85,239,196,0.05)",
        borderLeft: `3px solid ${color}`,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.15rem" }}>
        <span
          className="badge badge-candidate"
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
