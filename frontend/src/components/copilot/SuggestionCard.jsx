const PRIORITY_COLORS = {
  high: "var(--danger)",
  medium: "var(--warning)",
  low: "var(--text-dim)",
};

const TYPE_LABELS = {
  follow_up_question: "Follow-up",
  topic_coverage_update: "Coverage",
  inconsistency_alert: "Inconsistency",
  real_time_insight: "Insight",
  suggested_pivot: "Pivot",
  anti_repetition_alert: "Repetition",
};

export default function SuggestionCard({ suggestion, icon: Icon, pinned, onTogglePin, onDismiss }) {
  const { type, content, dimension, priority } = suggestion;
  const borderColor = PRIORITY_COLORS[priority] || "var(--border)";

  return (
    <div
      style={{
        padding: "0.6rem",
        marginBottom: "0.5rem",
        borderRadius: "var(--radius)",
        background: "var(--bg-card)",
        borderLeft: `3px solid ${borderColor}`,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "0.3rem", marginBottom: "0.25rem" }}>
        <Icon size={12} style={{ color: borderColor }} />
        <span style={{ fontSize: "0.7rem", fontWeight: 600, color: borderColor, textTransform: "uppercase" }}>
          {TYPE_LABELS[type] || type}
        </span>
        {dimension && (
          <span style={{ fontSize: "0.65rem", color: "var(--text-dim)", marginLeft: "auto" }}>
            {dimension}
          </span>
        )}
      </div>
      <p style={{ fontSize: "0.85rem", lineHeight: 1.5 }}>{content}</p>
      <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.45rem" }}>
        <button className="btn btn-outline btn-sm" onClick={onTogglePin}>
          {pinned ? "Unpin" : "Pin"}
        </button>
        <button className="btn btn-outline btn-sm" onClick={onDismiss}>
          Dismiss
        </button>
      </div>
    </div>
  );
}
