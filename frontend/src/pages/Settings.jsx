import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import useSettingsStore from "../stores/settingsStore";

const BLOCKED_KEYS = new Set([
  "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
  "Escape", "Tab", "CapsLock", "Enter",
]);

function keyLabel(key) {
  const map = {
    Alt: "Alt",
    Control: "Ctrl",
    Meta: "⌘",
    Shift: "Shift",
  };
  return map[key] ?? key;
}

export default function Settings() {
  const navigate = useNavigate();
  const interviewerShortcutKey = useSettingsStore((s) => s.interviewerShortcutKey);
  const setInterviewerShortcutKey = useSettingsStore((s) => s.setInterviewerShortcutKey);
  const [capturing, setCapturing] = useState(false);
  const [displayKey, setDisplayKey] = useState(interviewerShortcutKey);
  const captureRef = useRef(null);

  useEffect(() => {
    setDisplayKey(interviewerShortcutKey);
  }, [interviewerShortcutKey]);

  useEffect(() => {
    if (!capturing) return;

    const handleKeyDown = (e) => {
      e.preventDefault();
      e.stopPropagation();
      const key = e.key;
      const code = e.code;
      if (BLOCKED_KEYS.has(key) || BLOCKED_KEYS.has(code)) return;
      const resolved = ["Alt", "Control", "Meta", "Shift"].includes(key) ? key : (e.key?.length === 1 ? e.key.toLowerCase() : code);
      setInterviewerShortcutKey(resolved);
      setDisplayKey(resolved);
      setCapturing(false);
    };

    window.addEventListener("keydown", handleKeyDown, { capture: true });
    return () => window.removeEventListener("keydown", handleKeyDown, { capture: true });
  }, [capturing, setInterviewerShortcutKey]);

  return (
    <div style={{ maxWidth: 560, margin: "0 auto", padding: "2rem 1.5rem" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <button className="btn btn-outline btn-sm" onClick={() => navigate("/")}>
            <ArrowLeft size={14} />
          </button>
          <h1 style={{ fontSize: "1.3rem", fontWeight: 700 }}>Settings</h1>
        </div>
      </header>

      <div className="card">
        <h3 style={{ marginBottom: "0.5rem", fontSize: "1rem" }}>Interview</h3>
        <p style={{ color: "var(--text-dim)", fontSize: "0.85rem", marginBottom: "1rem" }}>
          Hold-to-speak: hold the shortcut key (or screen button) to temporarily record as Interviewer. Release to return to Candidate.
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <label style={{ fontSize: "0.85rem", fontWeight: 500 }}>Hold-to-speak shortcut</label>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <button
              ref={captureRef}
              type="button"
              className={`btn ${capturing ? "btn-primary" : "btn-outline"}`}
              onClick={() => setCapturing(true)}
              style={{
                minWidth: 120,
                fontFamily: "monospace",
                fontSize: "0.9rem",
              }}
            >
              {capturing ? "Press any key..." : keyLabel(displayKey) || displayKey}
            </button>
            <span style={{ fontSize: "0.8rem", color: "var(--text-dim)" }}>
              {capturing ? "Press the key you want to hold during the interview" : "Click to change"}
            </span>
          </div>
          <p style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginTop: "0.25rem" }}>
            Tip: If using Chinese IME, prefer Alt or Ctrl to avoid conflicts with letter keys.
          </p>
        </div>
      </div>
    </div>
  );
}
