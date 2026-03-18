import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Users, ChevronRight, Settings } from "lucide-react";
import useInterview from "./hooks/useInterview";

export default function App() {
  const navigate = useNavigate();
  const { createSession, createCandidate } = useInterview();
  const [sessions, setSessions] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [roleTitle, setRoleTitle] = useState("");
  const [candidateName, setCandidateName] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch("/api/sessions")
      .then((r) => r.json())
      .then(setSessions)
      .catch(() => {});
  }, []);

  const handleCreate = async () => {
    setLoading(true);
    try {
      let candidateId = null;
      if (candidateName.trim()) {
        const c = await createCandidate(candidateName.trim());
        candidateId = c.id;
      }
      const session = await createSession(roleTitle || "Interview", candidateId);
      navigate(`/prep/${session.id}`);
    } finally {
      setLoading(false);
    }
  };

  const statusLabel = (s) =>
    ({ preparing: "Preparing", active: "Live", completed: "Completed" })[s] || s;

  const statusColor = (s) =>
    ({ preparing: "var(--warning)", active: "var(--danger)", completed: "var(--success)" })[s] || "var(--text-dim)";

  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: "2rem 1.5rem" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "2rem" }}>
        <div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 700 }}>Interview Copilot</h1>
          <p style={{ color: "var(--text-dim)", marginTop: 4 }}>AI-powered interview assistant</p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <button
            className="btn btn-outline btn-sm"
            onClick={() => navigate("/settings")}
            title="Settings"
          >
            <Settings size={16} />
          </button>
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
            <Plus size={16} /> New Session
          </button>
        </div>
      </header>

      {showCreate && (
        <div className="card" style={{ marginBottom: "1.5rem" }}>
          <h3 style={{ marginBottom: "0.75rem" }}>Create Interview Session</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <input
              placeholder="Role title (e.g. Python Backend Engineer)"
              value={roleTitle}
              onChange={(e) => setRoleTitle(e.target.value)}
            />
            <input
              placeholder="Candidate name"
              value={candidateName}
              onChange={(e) => setCandidateName(e.target.value)}
            />
            <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
              <button className="btn btn-primary" onClick={handleCreate} disabled={loading}>
                {loading ? "Creating..." : "Create"}
              </button>
              <button className="btn btn-outline" onClick={() => setShowCreate(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        {sessions.length === 0 && !showCreate && (
          <div style={{ textAlign: "center", padding: "3rem", color: "var(--text-dim)" }}>
            <Users size={48} style={{ marginBottom: "1rem", opacity: 0.3 }} />
            <p>No interview sessions yet. Create one to get started.</p>
          </div>
        )}
        {sessions.map((s) => {
          const dest = s.status === "preparing" ? `/prep/${s.id}` : s.status === "active" ? `/live/${s.id}` : `/review/${s.id}`;
          return (
            <div
              key={s.id}
              className="card"
              style={{ cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center" }}
              onClick={() => navigate(dest)}
            >
              <div>
                <div style={{ fontWeight: 600 }}>{s.role_title || "Interview"}</div>
                <div style={{ color: "var(--text-dim)", fontSize: "0.85rem" }}>
                  {new Date(s.created_at).toLocaleDateString()}
                </div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                <span className="badge" style={{ background: `${statusColor(s.status)}22`, color: statusColor(s.status) }}>
                  {statusLabel(s.status)}
                </span>
                <ChevronRight size={16} style={{ color: "var(--text-dim)" }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
