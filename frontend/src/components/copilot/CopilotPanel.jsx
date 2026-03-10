import { useEffect, useState } from "react";
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

export default function CopilotPanel({ suggestions, sessionId }) {
  const coverage = useInterviewStore((s) => s.coverage);

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
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "0.5rem" }}>
        {/* Topic coverage tracker */}
        {coverage && <TopicTracker coverage={coverage} />}

        {/* Suggestions */}
        {suggestions.length === 0 && (
          <div style={{ padding: "1rem", color: "var(--text-dim)", textAlign: "center" }}>
            {coverage ? "正在生成面试建议..." : "请先上传候选人简历"}
          </div>
        )}
        {suggestions.map((s, i) => {
          const Icon = ICON_MAP[s.type] || Sparkles;
          return <SuggestionCard key={i} suggestion={s} icon={Icon} />;
        })}
      </div>
    </div>
  );
}
