import { useState } from "react";
import { Github, FolderOpen, Check, Loader } from "lucide-react";
import useInterview from "../../hooks/useInterview";

export default function GitHubImport({ sessionId }) {
  const { importGitHub } = useInterview();
  const [mode, setMode] = useState("github"); // github | local
  const [repoUrl, setRepoUrl] = useState("");
  const [localPath, setLocalPath] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleImport = async () => {
    setLoading(true);
    setResult(null);
    try {
      const res = await importGitHub(
        sessionId,
        mode === "github" ? repoUrl.trim() : null,
        mode === "local" ? localPath.trim() : null
      );
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
        <Github size={14} style={{ verticalAlign: "middle", marginRight: 6 }} />
        Import Project Background
      </h3>
      <p style={{ color: "var(--text-dim)", fontSize: "0.85rem", marginBottom: "0.75rem" }}>
        Provide a GitHub repo URL or a local project directory.
      </p>

      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.5rem" }}>
        <button
          className={`btn btn-sm ${mode === "github" ? "btn-primary" : "btn-outline"}`}
          onClick={() => setMode("github")}
        >
          <Github size={12} /> GitHub
        </button>
        <button
          className={`btn btn-sm ${mode === "local" ? "btn-primary" : "btn-outline"}`}
          onClick={() => setMode("local")}
        >
          <FolderOpen size={12} /> Local
        </button>
      </div>

      <div style={{ display: "flex", gap: "0.5rem" }}>
        {mode === "github" ? (
          <input
            style={{ flex: 1 }}
            placeholder="https://github.com/owner/repo"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
          />
        ) : (
          <input
            style={{ flex: 1 }}
            placeholder="/path/to/project"
            value={localPath}
            onChange={(e) => setLocalPath(e.target.value)}
          />
        )}
        <button
          className="btn btn-primary"
          onClick={handleImport}
          disabled={loading || (mode === "github" ? !repoUrl.trim() : !localPath.trim())}
        >
          {loading ? <Loader size={14} /> : "Import"}
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
              Imported "{result.name}" ({result.chars} chars)
            </span>
          )}
        </div>
      )}
    </div>
  );
}
