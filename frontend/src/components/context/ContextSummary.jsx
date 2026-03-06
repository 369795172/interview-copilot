import { useEffect, useState } from "react";
import { Info } from "lucide-react";

export default function ContextSummary({ sessionId }) {
  const [summary, setSummary] = useState(null);

  const refresh = () => {
    fetch(`/api/context/${sessionId}/summary`)
      .then((r) => r.json())
      .then(setSummary)
      .catch(() => {});
  };

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 10_000);
    return () => clearInterval(iv);
  }, [sessionId]);

  if (!summary) return null;

  const items = [
    { label: "Company Values", value: summary.company_values },
    { label: "Project Background", value: summary.project_background },
    { label: "Candidate Profile", value: summary.candidate_profile ? JSON.stringify(summary.candidate_profile).slice(0, 200) : "" },
    { label: "Custom Notes", value: summary.custom_notes },
  ].filter((i) => i.value);

  if (items.length === 0) return null;

  return (
    <div className="card">
      <h3 style={{ fontSize: "0.9rem", fontWeight: 600, marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.3rem" }}>
        <Info size={14} style={{ color: "var(--accent-light)" }} />
        Loaded Context
      </h3>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
        {items.map((item) => (
          <div key={item.label}>
            <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-dim)" }}>{item.label}</span>
            <p style={{ fontSize: "0.8rem", color: "var(--text)", marginTop: 2 }}>
              {item.value.length > 150 ? item.value.slice(0, 150) + "..." : item.value}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
