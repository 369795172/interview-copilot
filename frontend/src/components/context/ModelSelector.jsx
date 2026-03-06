import { useEffect, useState } from "react";
import { Cpu, Check } from "lucide-react";

const TIER_LABELS = {
  recommended: { label: "Recommended", color: "var(--success)" },
  premium: { label: "Premium", color: "var(--accent-light)" },
  standard: { label: "Standard", color: "var(--text-dim)" },
  reasoning: { label: "Reasoning", color: "var(--warning)" },
  fast: { label: "Fast", color: "var(--interviewer)" },
};

export default function ModelSelector({ sessionId }) {
  const [models, setModels] = useState([]);
  const [defaultModel, setDefaultModel] = useState("");
  const [selected, setSelected] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch("/api/context/models")
      .then((r) => r.json())
      .then((data) => {
        setModels(data.models || []);
        setDefaultModel(data.default || "");
        setSelected(data.default || "");
      })
      .catch(() => {});
  }, []);

  const handleSelect = async (modelId) => {
    setSelected(modelId);
    setSaving(true);
    try {
      await fetch(`/api/context/${sessionId}/model`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_id: modelId }),
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <h3 style={{ fontSize: "0.95rem", fontWeight: 600, marginBottom: "0.5rem" }}>
        <Cpu size={14} style={{ verticalAlign: "middle", marginRight: 6 }} />
        AI Model
      </h3>
      <p style={{ color: "var(--text-dim)", fontSize: "0.85rem", marginBottom: "0.75rem" }}>
        Select the LLM for copilot analysis (via OpenRouter).
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
        {models.map((m) => {
          const tier = TIER_LABELS[m.tier] || TIER_LABELS.standard;
          const isSelected = selected === m.id;
          return (
            <button
              key={m.id}
              onClick={() => handleSelect(m.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                padding: "0.5rem 0.75rem",
                borderRadius: "var(--radius)",
                border: `1px solid ${isSelected ? "var(--accent)" : "var(--border)"}`,
                background: isSelected ? "rgba(108,92,231,0.1)" : "transparent",
                color: "var(--text)",
                textAlign: "left",
                cursor: "pointer",
                transition: "all 0.15s",
              }}
            >
              {isSelected ? (
                <Check size={14} style={{ color: "var(--accent-light)", flexShrink: 0 }} />
              ) : (
                <div style={{ width: 14, flexShrink: 0 }} />
              )}
              <span style={{ flex: 1, fontSize: "0.85rem" }}>{m.name}</span>
              <span
                style={{
                  fontSize: "0.65rem",
                  fontWeight: 600,
                  color: tier.color,
                  padding: "0.1rem 0.4rem",
                  borderRadius: 100,
                  border: `1px solid ${tier.color}33`,
                }}
              >
                {tier.label}
              </span>
            </button>
          );
        })}
      </div>
      {selected && (
        <p style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginTop: "0.5rem", fontFamily: "monospace" }}>
          {selected}
        </p>
      )}
    </div>
  );
}
