import { useState } from "react";

export default function DimensionRow({ dimension, subDimension, weight, value, suggestion, onScore, onApplySuggestion }) {
  const [note, setNote] = useState("");
  const [showNote, setShowNote] = useState(false);

  const handleClick = (score) => {
    onScore(score, note || undefined);
  };

  const suggestedScore = suggestion?.suggested_score;
  const hasSuggestion = suggestion && suggestedScore != null;

  return (
    <div
      style={{
        padding: "0.35rem 0.5rem",
        marginBottom: "0.2rem",
        borderRadius: "var(--radius)",
        background: value ? "rgba(108,92,231,0.06)" : hasSuggestion ? "rgba(108,92,231,0.03)" : "transparent",
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
                background: value === n ? "var(--accent)" : suggestedScore === n && !value ? "rgba(108,92,231,0.25)" : "transparent",
                color: value === n ? "#fff" : suggestedScore === n && !value ? "var(--accent-light)" : "var(--text-dim)",
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
        {hasSuggestion && onApplySuggestion && (
          <button
            onClick={() => onApplySuggestion(suggestion)}
            className="btn btn-primary btn-sm"
            style={{ padding: "0.1rem 0.35rem", fontSize: "0.65rem" }}
            title="采纳 AI 建议"
          >
            采纳
          </button>
        )}
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

      {hasSuggestion && suggestion.reasoning && (
        <div style={{ marginTop: "0.25rem", fontSize: "0.7rem", color: "var(--text-dim)", lineHeight: 1.3 }}>
          {suggestion.reasoning.length > 60 ? `${suggestion.reasoning.slice(0, 60)}…` : suggestion.reasoning}
        </div>
      )}

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
