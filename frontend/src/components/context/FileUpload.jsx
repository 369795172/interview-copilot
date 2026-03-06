import { useState, useRef } from "react";
import { Upload, FileText, Check, Loader } from "lucide-react";
import useInterview from "../../hooks/useInterview";

export default function FileUpload({ sessionId }) {
  const { uploadFile } = useInterview();
  const fileRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [fileName, setFileName] = useState("");

  const handleSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setFileName(file.name);
    handleUpload(file);
  };

  const handleUpload = async (file) => {
    setLoading(true);
    setResult(null);
    try {
      const res = await uploadFile(sessionId, file);
      setResult(res);
    } catch (e) {
      setResult({ error: e.message });
    } finally {
      setLoading(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) {
      setFileName(file.name);
      handleUpload(file);
    }
  };

  return (
    <div>
      <h3 style={{ fontSize: "0.95rem", fontWeight: 600, marginBottom: "0.5rem" }}>
        <FileText size={14} style={{ verticalAlign: "middle", marginRight: 6 }} />
        Upload Candidate File
      </h3>
      <p style={{ color: "var(--text-dim)", fontSize: "0.85rem", marginBottom: "0.75rem" }}>
        Upload a resume (PDF, DOCX, MD, TXT) or other candidate document.
      </p>

      <div
        onClick={() => fileRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
        style={{
          border: "2px dashed var(--border)",
          borderRadius: "var(--radius-lg)",
          padding: "2rem",
          textAlign: "center",
          cursor: "pointer",
          transition: "border-color 0.15s",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--accent)")}
        onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--border)")}
      >
        {loading ? (
          <Loader size={24} style={{ color: "var(--accent-light)", animation: "spin 1s linear infinite" }} />
        ) : (
          <>
            <Upload size={24} style={{ color: "var(--text-dim)", marginBottom: "0.5rem" }} />
            <p style={{ color: "var(--text-dim)", fontSize: "0.85rem" }}>
              Click or drag file here
            </p>
            <p style={{ color: "var(--text-dim)", fontSize: "0.75rem", marginTop: "0.25rem" }}>
              PDF, DOCX, MD, TXT
            </p>
          </>
        )}
      </div>

      <input ref={fileRef} type="file" accept=".pdf,.docx,.md,.txt" onChange={handleSelect} style={{ display: "none" }} />

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
              Uploaded "{result.file}" ({result.profile?.char_count || 0} chars)
            </span>
          )}
        </div>
      )}
    </div>
  );
}
