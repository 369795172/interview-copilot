import { Tag } from "lucide-react";

export default function EvidenceTag({ text, onClick, active }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "0.2rem",
        padding: "0.15rem 0.4rem",
        borderRadius: 100,
        border: `1px solid ${active ? "var(--accent)" : "var(--border)"}`,
        background: active ? "rgba(108,92,231,0.15)" : "transparent",
        color: active ? "var(--accent-light)" : "var(--text-dim)",
        fontSize: "0.7rem",
        cursor: "pointer",
        transition: "all 0.1s",
      }}
    >
      <Tag size={10} />
      {text}
    </button>
  );
}
