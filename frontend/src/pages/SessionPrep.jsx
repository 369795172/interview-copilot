import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Play, Upload, FileText, Github, BookOpen, Cpu, CheckCircle } from "lucide-react";
import useInterview from "../hooks/useInterview";
import useInterviewStore from "../stores/interviewStore";
import FeishuImport from "../components/context/FeishuImport";
import GitHubImport from "../components/context/GitHubImport";
import FileUpload from "../components/context/FileUpload";
import ModelSelector from "../components/context/ModelSelector";
import ContextSummary from "../components/context/ContextSummary";

export default function SessionPrep() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const { startSession } = useInterview();
  const [session, setSession] = useState(null);
  const [activeTab, setActiveTab] = useState("file");
  const [globalCtx, setGlobalCtx] = useState(null);

  useEffect(() => {
    fetch(`/api/sessions/${sessionId}`)
      .then((r) => r.json())
      .then(setSession)
      .catch(() => {});
    fetch("/api/context/global")
      .then((r) => r.json())
      .then(setGlobalCtx)
      .catch(() => {});
  }, [sessionId]);

  const handleStart = async () => {
    await startSession(sessionId);
    navigate(`/live/${sessionId}`);
  };

  const gcFeishu = globalCtx?.company_values_chars > 0;
  const gcProject = globalCtx?.project_background_chars > 0;

  const tabs = [
    { id: "file", label: "Candidate File", icon: Upload, ready: false },
    { id: "feishu", label: "Feishu Doc", icon: BookOpen, ready: gcFeishu },
    { id: "github", label: "Project", icon: Github, ready: gcProject },
    { id: "model", label: "AI Model", icon: Cpu, ready: false },
  ];

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "2rem 1.5rem" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <div>
          <h1 style={{ fontSize: "1.3rem", fontWeight: 700 }}>Session Preparation</h1>
          <p style={{ color: "var(--text-dim)", marginTop: 4 }}>
            {session?.role_title || "Loading..."}
          </p>
        </div>
        <button className="btn btn-primary" onClick={handleStart}>
          <Play size={16} /> Start Interview
        </button>
      </header>

      {/* Global context banner */}
      {globalCtx && (gcFeishu || gcProject) && (
        <div
          style={{
            display: "flex",
            gap: "1rem",
            padding: "0.6rem 1rem",
            marginBottom: "1rem",
            borderRadius: "var(--radius)",
            background: "rgba(116,185,255,0.08)",
            border: "1px solid rgba(116,185,255,0.18)",
            fontSize: "0.8rem",
            color: "var(--text-dim)",
            alignItems: "center",
            flexWrap: "wrap",
          }}
        >
          <span style={{ fontWeight: 600, color: "var(--accent)" }}>Global context loaded</span>
          {gcFeishu && (
            <span style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
              <CheckCircle size={12} style={{ color: "var(--success)" }} />
              Company values ({globalCtx.company_values_chars.toLocaleString()} chars)
            </span>
          )}
          {gcProject && (
            <span style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
              <CheckCircle size={12} style={{ color: "var(--success)" }} />
              Project background ({globalCtx.project_background_chars.toLocaleString()} chars)
            </span>
          )}
        </div>
      )}

      {/* Context Loading Tabs */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        {tabs.map((t) => (
          <button
            key={t.id}
            className={`btn ${activeTab === t.id ? "btn-primary" : "btn-outline"}`}
            onClick={() => setActiveTab(t.id)}
            style={{ position: "relative" }}
          >
            <t.icon size={14} /> {t.label}
            {t.ready && (
              <CheckCircle
                size={10}
                style={{
                  position: "absolute",
                  top: 2,
                  right: 2,
                  color: "var(--success)",
                }}
              />
            )}
          </button>
        ))}
      </div>

      <div className="card" style={{ marginBottom: "1.5rem", minHeight: 200 }}>
        {activeTab === "file" && <FileUpload sessionId={sessionId} />}
        {activeTab === "feishu" && <FeishuImport sessionId={sessionId} />}
        {activeTab === "github" && <GitHubImport sessionId={sessionId} />}
        {activeTab === "model" && <ModelSelector sessionId={sessionId} />}
      </div>

      <ContextSummary sessionId={sessionId} />
    </div>
  );
}
