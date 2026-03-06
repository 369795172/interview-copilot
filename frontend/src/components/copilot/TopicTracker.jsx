import { CheckCircle, Circle, AlertCircle } from "lucide-react";

export default function TopicTracker({ coverage }) {
  if (!coverage?.coverage) return null;

  const dims = {};
  for (const c of coverage.coverage) {
    if (!dims[c.dimension]) dims[c.dimension] = [];
    dims[c.dimension].push(c);
  }

  return (
    <div
      style={{
        padding: "0.6rem",
        marginBottom: "0.75rem",
        borderRadius: "var(--radius)",
        background: "var(--bg-card)",
        border: "1px solid var(--border)",
      }}
    >
      <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-dim)", marginBottom: "0.4rem" }}>
        Topic Coverage ({coverage.completion_pct || 0}%)
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
        {Object.entries(dims).map(([dim, subs]) => {
          const scored = subs.filter((s) => s.status === "scored").length;
          const total = subs.length;
          const pct = total > 0 ? (scored / total) * 100 : 0;
          const allScored = scored === total;
          const noneScored = scored === 0;

          return (
            <div key={dim} style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              {allScored ? (
                <CheckCircle size={12} style={{ color: "var(--success)" }} />
              ) : noneScored ? (
                <Circle size={12} style={{ color: "var(--text-dim)" }} />
              ) : (
                <AlertCircle size={12} style={{ color: "var(--warning)" }} />
              )}
              <span style={{ fontSize: "0.8rem", flex: 1 }}>{dim}</span>
              <div
                style={{
                  width: 50,
                  height: 4,
                  background: "var(--border)",
                  borderRadius: 2,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    width: `${pct}%`,
                    height: "100%",
                    background: allScored ? "var(--success)" : "var(--warning)",
                  }}
                />
              </div>
              <span style={{ fontSize: "0.7rem", color: "var(--text-dim)", width: 30, textAlign: "right" }}>
                {scored}/{total}
              </span>
            </div>
          );
        })}
      </div>
      {coverage.gaps?.length > 0 && (
        <div style={{ marginTop: "0.4rem", fontSize: "0.7rem", color: "var(--warning)" }}>
          Gaps: {coverage.gaps.slice(0, 3).join(", ")}
          {coverage.gaps.length > 3 && ` +${coverage.gaps.length - 3} more`}
        </div>
      )}
    </div>
  );
}
