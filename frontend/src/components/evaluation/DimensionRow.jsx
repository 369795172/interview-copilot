import { useState } from "react";

export default function DimensionRow({ dimension, subDimension, weight, value, onScore }) {
  const [note, setNote] = useState("");
  const [showNote, setShowNote] = useState(false);

  const handleClick = (score) => {
    onScore(score, note || undefined);
  };

  return (
    <div
      style={{
        padding: "0.35rem 0.5rem",
        marginBottom: "0.2rem",
        borderRadius: "var(--radius)",
        background: value ? "rgba(108,92,231,0.06)" : "transparent",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
        <span style={{ fontSize: "0.8rem", flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {subDimension}
        </span>
        <div style={{ display: "flex", gap: "2px", flexShrink: 0 }}>
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              onClick={() => handleClick(n)}
              style={{
                width: 22,
                height: 22,
                borderRadius: 4,
                border: "1px solid var(--border)",
                background: value === n ? "var(--accent)" : "transparent",
                color: value === n ? "#fff" : "var(--text-dim)",
                fontSize: "0.7rem",
                fontWeight: 600,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: "pointer",
                transition: "all 0.1s",
              }}
              title={`Score ${n}/5`}
            >
              {n}
            </button>
          ))}
        </div>
        <button
          onClick={() => setShowNote(!showNote)}
          style={{
            background: "none",
            color: note ? "var(--accent-light)" : "var(--text-dim)",
            fontSize: "0.7rem",
            padding: "0 0.2rem",
          }}
          title="Add evidence note"
        >
          +
        </button>
      </div>

      {showNote && (
        <div style={{ marginTop: "0.3rem" }}>
          <textarea
            placeholder="Evidence note..."
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            style={{ width: "100%", fontSize: "0.75rem", resize: "vertical" }}
          />
        </div>
      )}
    </div>
  );
}
