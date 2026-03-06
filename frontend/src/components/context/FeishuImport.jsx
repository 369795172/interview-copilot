import { useState } from "react";
import { BookOpen, Check, Loader } from "lucide-react";
import useInterview from "../../hooks/useInterview";

export default function FeishuImport({ sessionId }) {
  const { importFeishu } = useInterview();
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleImport = async () => {
    if (!url.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await importFeishu(sessionId, url.trim());
      setResult(res);
    } catch (e) {
      setResult({ error: e.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h3 style={{ fontSize: "0.95rem", fontWeight: 600, marginBottom: "0.5rem" }}>
        <BookOpen size={14} style={{ verticalAlign: "middle", marginRight: 6 }} />
        Import Company Values from Feishu
      </h3>
      <p style={{ color: "var(--text-dim)", fontSize: "0.85rem", marginBottom: "0.75rem" }}>
        Paste a Feishu document URL containing company values, culture, or JD.
      </p>
      <div style={{ display: "flex", gap: "0.5rem" }}>
        <input
          style={{ flex: 1 }}
          placeholder="https://xxx.feishu.cn/docx/..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <button className="btn btn-primary" onClick={handleImport} disabled={loading || !url.trim()}>
          {loading ? <Loader size={14} className="spin" /> : "Import"}
        </button>
      </div>
      {result && (
        <div
          style={{
            marginTop: "0.75rem",
            padding: "0.5rem",
            borderRadius: "var(--radius)",
            background: result.error ? "rgba(225,112,85,0.1)" : "rgba(0,184,148,0.1)",
            fontSize: "0.85rem",
          }}
        >
          {result.error ? (
            <span style={{ color: "var(--danger)" }}>{result.error}</span>
          ) : (
            <span style={{ color: "var(--success)" }}>
              <Check size={14} style={{ verticalAlign: "middle", marginRight: 4 }} />
              Imported "{result.title}" ({result.chars} chars)
            </span>
          )}
        </div>
      )}
    </div>
  );
}
