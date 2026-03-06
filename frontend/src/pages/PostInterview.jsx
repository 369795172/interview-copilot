import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Download, ArrowLeft, CheckCircle } from "lucide-react";
import useInterview from "../hooks/useInterview";

export default function PostInterview() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const { exportSession } = useInterview();
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    exportSession(sessionId)
      .then(setResult)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [sessionId, exportSession]);

  const handleDownload = () => {
    if (!result?.markdown) return;
    const blob = new Blob([result.markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `interview-${sessionId.slice(0, 8)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const decisionStyle = (d) =>
    ({
      strong_hire: { bg: "rgba(0,184,148,0.15)", color: "var(--success)", label: "Strong Hire" },
      proceed: { bg: "rgba(108,92,231,0.15)", color: "var(--accent-light)", label: "Proceed" },
      borderline: { bg: "rgba(253,203,110,0.15)", color: "var(--warning)", label: "Borderline" },
      no_hire: { bg: "rgba(225,112,85,0.15)", color: "var(--danger)", label: "No Hire" },
    })[d] || { bg: "var(--bg-hover)", color: "var(--text-dim)", label: d };

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "2rem 1.5rem" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <button className="btn btn-outline btn-sm" onClick={() => navigate("/")}>
            <ArrowLeft size={14} />
          </button>
          <h1 style={{ fontSize: "1.3rem", fontWeight: 700 }}>Interview Review</h1>
        </div>
        <button className="btn btn-primary" onClick={handleDownload} disabled={!result?.markdown}>
          <Download size={16} /> Export Markdown
        </button>
      </header>

      {loading && <p style={{ color: "var(--text-dim)" }}>Loading...</p>}

      {result?.decision && (
        <div className="card" style={{ marginBottom: "1.5rem", display: "flex", alignItems: "center", gap: "1rem" }}>
          <CheckCircle size={24} style={{ color: decisionStyle(result.decision.decision).color }} />
          <div>
            <div style={{ fontSize: "1.1rem", fontWeight: 700 }}>
              <span
                className="badge"
                style={{
                  background: decisionStyle(result.decision.decision).bg,
                  color: decisionStyle(result.decision.decision).color,
                  fontSize: "0.9rem",
                  padding: "0.25rem 0.75rem",
                }}
              >
                {decisionStyle(result.decision.decision).label}
              </span>
            </div>
            <div style={{ color: "var(--text-dim)", marginTop: 4 }}>
              Weighted Score: {result.decision.weighted_score}/100
            </div>
          </div>
        </div>
      )}

      {result?.markdown && (
        <div className="card">
          <pre
            style={{
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              fontFamily: "inherit",
              fontSize: "0.85rem",
              lineHeight: 1.7,
              color: "var(--text)",
              maxHeight: "70vh",
              overflow: "auto",
            }}
          >
            {result.markdown}
          </pre>
        </div>
      )}
    </div>
  );
}
