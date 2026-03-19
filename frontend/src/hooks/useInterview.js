import { useCallback } from "react";
import useInterviewStore from "../stores/interviewStore";

const API = "";

export default function useInterview() {
  const createSession = useCallback(async (roleTitle, candidateId) => {
    const res = await fetch(`${API}/api/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role_title: roleTitle, candidate_id: candidateId }),
    });
    const data = await res.json();
    useInterviewStore.getState().setSession(data.id, { status: data.status, roleTitle: data.role_title });
    return data;
  }, []);

  const startSession = useCallback(async (sessionId) => {
    const res = await fetch(`${API}/api/sessions/${sessionId}/start`, { method: "POST" });
    const data = await res.json();
    useInterviewStore.getState().setStatus("active");
    return data;
  }, []);

  const endSession = useCallback(async (sessionId) => {
    const res = await fetch(`${API}/api/sessions/${sessionId}/end`, { method: "POST" });
    const data = await res.json();
    useInterviewStore.getState().setStatus("completed");
    return data;
  }, []);

  const createCandidate = useCallback(async (name) => {
    const res = await fetch(`${API}/api/sessions/candidates`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    return res.json();
  }, []);

  const fetchCoverage = useCallback(async (sessionId) => {
    const res = await fetch(`${API}/api/sessions/${sessionId}/evaluation/coverage`);
    const data = await res.json();
    useInterviewStore.getState().setCoverage(data);
    return data;
  }, []);

  const fetchTranscript = useCallback(async (sessionId) => {
    const res = await fetch(`${API}/api/sessions/${sessionId}/transcript`);
    const data = await res.json();
    useInterviewStore.getState().setTranscript(data || []);
    return data;
  }, []);

  const fetchHistory = useCallback(async (sessionId) => {
    const res = await fetch(`${API}/api/sessions/${sessionId}/history`);
    const data = await res.json();
    return data || [];
  }, []);

  const fetchScores = useCallback(async (sessionId) => {
    const res = await fetch(`${API}/api/sessions/${sessionId}/evaluation/scores`);
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  }, []);

  const fetchSuggestions = useCallback(async (sessionId) => {
    const res = await fetch(`${API}/api/sessions/${sessionId}/evaluation/suggest`, {
      method: "POST",
    });
    const data = await res.json();
    return data?.suggestions ?? [];
  }, []);

  const saveScore = useCallback(async (sessionId, scoreData) => {
    const res = await fetch(`${API}/api/sessions/${sessionId}/evaluation/scores`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(scoreData),
    });
    return res.json();
  }, []);

  const updateScore = useCallback(async (sessionId, scoreId, updates) => {
    const res = await fetch(`${API}/api/sessions/${sessionId}/evaluation/scores/${scoreId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
    return res.json();
  }, []);

  const exportSession = useCallback(async (sessionId) => {
    const res = await fetch(`${API}/api/sessions/${sessionId}/export`);
    return res.json();
  }, []);

  const importFeishu = useCallback(async (sessionId, url) => {
    const res = await fetch(`${API}/api/context/${sessionId}/feishu`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await res.json();
    if (!res.ok) {
      return { error: data.detail || `HTTP ${res.status}` };
    }
    return data;
  }, []);

  const importGitHub = useCallback(async (sessionId, repoUrl, localPath) => {
    const res = await fetch(`${API}/api/context/${sessionId}/github`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_url: repoUrl, local_path: localPath }),
    });
    return res.json();
  }, []);

  const uploadFile = useCallback(async (sessionId, file) => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${API}/api/context/${sessionId}/upload`, {
      method: "POST",
      body: fd,
    });
    return res.json();
  }, []);

  return {
    createSession,
    startSession,
    endSession,
    createCandidate,
    fetchCoverage,
    fetchTranscript,
    fetchHistory,
    fetchScores,
    fetchSuggestions,
    saveScore,
    updateScore,
    exportSession,
    importFeishu,
    importGitHub,
    uploadFile,
  };
}
