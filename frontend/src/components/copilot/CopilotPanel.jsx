import { useEffect, useMemo, useRef, useState } from "react";
import { Sparkles, HelpCircle, AlertTriangle, ArrowRight, RefreshCw } from "lucide-react";
import SuggestionCard from "./SuggestionCard";
import TopicTracker from "./TopicTracker";
import useInterviewStore from "../../stores/interviewStore";

const ICON_MAP = {
  follow_up_question: HelpCircle,
  topic_coverage_update: RefreshCw,
  inconsistency_alert: AlertTriangle,
  real_time_insight: Sparkles,
  suggested_pivot: ArrowRight,
  anti_repetition_alert: AlertTriangle,
};

export default function CopilotPanel({ suggestions, sendMessage }) {
  const coverage = useInterviewStore((s) => s.coverage);
  const pinnedSuggestionIds = useInterviewStore((s) => s.pinnedSuggestionIds);
  const togglePinSuggestion = useInterviewStore((s) => s.togglePinSuggestion);
  const dismissSuggestion = useInterviewStore((s) => s.dismissSuggestion);
  const customGuidanceActive = useInterviewStore((s) => s.customGuidanceActive);
  const setCustomGuidanceActive = useInterviewStore((s) => s.setCustomGuidanceActive);

  const [manualSuggestion, setManualSuggestion] = useState("");
  const [manualPrompt, setManualPrompt] = useState("");
  const [showPromptEditor, setShowPromptEditor] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const refreshTimerRef = useRef(null);

  const orderedSuggestions = useMemo(() => {
    const pinned = [];
    const others = [];
    for (const item of suggestions) {
      if (pinnedSuggestionIds.includes(item._localId)) {
        pinned.push(item);
      } else {
        others.push(item);
      }
    }
    return [...pinned, ...others];
  }, [suggestions, pinnedSuggestionIds]);

  const submitManualSuggestion = () => {
    const content = manualSuggestion.trim();
    if (!content || !sendMessage) return;
    sendMessage({ type: "custom_suggestion", content, suggestion_type: "follow_up_question" });
    setManualSuggestion("");
  };

  const submitManualPrompt = () => {
    const content = manualPrompt.trim();
    if (!content || !sendMessage) return;
    sendMessage({ type: "custom_prompt", content });
    setCustomGuidanceActive(true);
    setManualPrompt("");
    setShowPromptEditor(false);
  };

  const requestRefresh = () => {
    if (!sendMessage || isRefreshing) return;
    sendMessage({ type: "request_analysis" });
    setIsRefreshing(true);
    if (refreshTimerRef.current) {
      window.clearTimeout(refreshTimerRef.current);
    }
    refreshTimerRef.current = window.setTimeout(() => {
      setIsRefreshing(false);
      refreshTimerRef.current = null;
    }, 2000);
  };

  useEffect(
    () => () => {
      if (refreshTimerRef.current) {
        window.clearTimeout(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    },
    []
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div
        style={{
          padding: "0.6rem 1rem",
          borderBottom: "1px solid var(--border)",
          fontWeight: 600,
          fontSize: "0.85rem",
          color: "var(--text-dim)",
          display: "flex",
          alignItems: "center",
          gap: "0.4rem",
          flexShrink: 0,
        }}
      >
        <Sparkles size={14} style={{ color: "var(--accent-light)" }} />
        AI Copilot
        {customGuidanceActive && (
          <span style={{ marginLeft: "auto", fontSize: "0.7rem", color: "var(--accent)" }}>
            custom guidance active
          </span>
        )}
        <button
          className="btn btn-outline btn-sm"
          onClick={requestRefresh}
          disabled={!sendMessage || isRefreshing}
          title="Manually refresh AI suggestions"
        >
          <RefreshCw
            size={12}
            className={isRefreshing ? "copilot-spin" : ""}
            style={{ marginRight: "0.2rem" }}
          />
          Refresh
        </button>
        <button
          className="btn btn-outline btn-sm"
          style={{ marginLeft: "0.5rem" }}
          onClick={() => setShowPromptEditor((v) => !v)}
        >
          Prompt
        </button>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "0.5rem" }}>
        {showPromptEditor && (
          <div style={{ marginBottom: "0.5rem", background: "var(--bg-card)", padding: "0.5rem", borderRadius: "var(--radius)" }}>
            <textarea
              value={manualPrompt}
              onChange={(e) => setManualPrompt(e.target.value)}
              placeholder="Add custom copilot guidance..."
              style={{ width: "100%", minHeight: 72, resize: "vertical" }}
            />
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "0.4rem" }}>
              <button className="btn btn-primary btn-sm" onClick={submitManualPrompt} disabled={!manualPrompt.trim()}>
                Apply
              </button>
            </div>
          </div>
        )}

        {/* Topic coverage tracker */}
        {coverage && <TopicTracker coverage={coverage} />}

        {/* Suggestions */}
        {orderedSuggestions.length === 0 && (
          <div style={{ padding: "1rem", color: "var(--text-dim)", textAlign: "center" }}>
            {coverage ? "正在生成面试建议..." : "请先上传候选人简历"}
          </div>
        )}
        {orderedSuggestions.map((s) => {
          const Icon = ICON_MAP[s.type] || Sparkles;
          return (
            <SuggestionCard
              key={s._localId}
              suggestion={s}
              icon={Icon}
              pinned={pinnedSuggestionIds.includes(s._localId)}
              onTogglePin={() => togglePinSuggestion(s._localId)}
              onDismiss={() => dismissSuggestion(s._localId)}
            />
          );
        })}
      </div>

      <div
        style={{
          borderTop: "1px solid var(--border)",
          padding: "0.45rem",
          display: "flex",
          gap: "0.4rem",
          background: "var(--bg-card)",
        }}
      >
        <input
          type="text"
          value={manualSuggestion}
          onChange={(e) => setManualSuggestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              submitManualSuggestion();
            }
          }}
          placeholder="Add manual question/suggestion..."
          style={{ flex: 1 }}
        />
        <button className="btn btn-primary btn-sm" onClick={submitManualSuggestion} disabled={!manualSuggestion.trim()}>
          Add
        </button>
      </div>
    </div>
  );
}
