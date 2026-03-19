import { useEffect, useState, useCallback, useRef } from "react";
import { BarChart3, Sparkles } from "lucide-react";

const AUTO_REFRESH_INITIAL_DELAY_MS = 5_000;   // First fetch 5s after transcript has content
const AUTO_REFRESH_INTERVAL_MS = 7 * 60_000;   // Then every 7 minutes
const MIN_TRANSCRIPT_FOR_SUGGEST = 3;
import DimensionRow from "./DimensionRow";
import useInterview from "../../hooks/useInterview";
import useInterviewStore from "../../stores/interviewStore";

const DIMENSIONS = [
  {
    name: "技术能力",
    weight: 0.4,
    subs: [
      { name: "编码与框架", weight: 0.1 },
      { name: "数据与性能", weight: 0.1 },
      { name: "存量系统协作", weight: 0.1 },
      { name: "工程质量", weight: 0.1 },
    ],
  },
  {
    name: "AI 时代适应度",
    weight: 0.25,
    subs: [
      { name: "AI 使用策略", weight: 0.1 },
      { name: "AI 输出校验", weight: 0.1 },
      { name: "Prompt 与上下文", weight: 0.05 },
    ],
  },
  {
    name: "性格稳定与职业可靠性",
    weight: 0.2,
    subs: [
      { name: "情绪稳定性", weight: 0.1 },
      { name: "言行一致与诚信", weight: 0.05 },
      { name: "稳定性与长期意愿", weight: 0.05 },
    ],
  },
  {
    name: "软实力",
    weight: 0.15,
    subs: [
      { name: "沟通", weight: 0.04 },
      { name: "自驱", weight: 0.04 },
      { name: "迭代", weight: 0.04 },
      { name: "格局", weight: 0.03 },
    ],
  },
];

export default function ScoreCard({ sessionId, transcript, autoRefresh = false }) {
  const { saveScore, updateScore, fetchScores, fetchSuggestions } = useInterview();
  const [localScores, setLocalScores] = useState({});
  const [suggestions, setSuggestions] = useState({});
  const [saving, setSaving] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const suggestingRef = useRef(false);
  const hasTriggeredInitialRef = useRef(false);
  const coverage = useInterviewStore((s) => s.coverage);

  useEffect(() => {
    if (!sessionId) return;
    fetchScores(sessionId).then((scores) => {
      const map = {};
      for (const s of scores || []) {
        const key = `${s.dimension}/${s.sub_dimension ?? ""}`;
        map[key] = { id: s.id, score: s.score, note: s.evidence_note ?? "" };
      }
      setLocalScores(map);
    });
  }, [sessionId, fetchScores]);

  const handleAiSuggest = useCallback(async () => {
    if (!sessionId) return;
    if (suggestingRef.current) return;
    suggestingRef.current = true;
    setSuggesting(true);
    try {
      const list = await fetchSuggestions(sessionId);
      const map = {};
      for (const s of list || []) {
        const key = `${s.dimension}/${s.sub_dimension ?? ""}`;
        map[key] = s;
      }
      setSuggestions(map);
    } finally {
      suggestingRef.current = false;
      setSuggesting(false);
    }
  }, [sessionId, fetchSuggestions]);

  // Auto-refresh: initial fetch 5s after transcript has content, then every 60s
  useEffect(() => {
    if (!autoRefresh || !sessionId || !Array.isArray(transcript) || transcript.length < MIN_TRANSCRIPT_FOR_SUGGEST) {
      hasTriggeredInitialRef.current = false;
      return;
    }
    const runFetch = () => {
      handleAiSuggest();
    };
    if (!hasTriggeredInitialRef.current) {
      hasTriggeredInitialRef.current = true;
      const t = setTimeout(runFetch, AUTO_REFRESH_INITIAL_DELAY_MS);
      const iv = setInterval(runFetch, AUTO_REFRESH_INTERVAL_MS);
      return () => {
        clearTimeout(t);
        clearInterval(iv);
      };
    }
    const iv = setInterval(runFetch, AUTO_REFRESH_INTERVAL_MS);
    return () => clearInterval(iv);
  }, [autoRefresh, sessionId, transcript?.length, handleAiSuggest]);

  // Compute weighted total from local scores
  const computeTotal = useCallback(() => {
    let total = 0;
    let maxTotal = 0;
    for (const dim of DIMENSIONS) {
      for (const sub of dim.subs) {
        const key = `${dim.name}/${sub.name}`;
        maxTotal += sub.weight * 5;
        if (localScores[key]?.score) {
          total += sub.weight * localScores[key].score;
        }
      }
    }
    return maxTotal > 0 ? Math.round((total / maxTotal) * 100) : 0;
  }, [localScores]);

  const handleScore = async (dimension, subDimension, score, note, transcriptEntryIds = []) => {
    const key = `${dimension}/${subDimension}`;
    const existing = localScores[key];

    setSaving(true);
    try {
      if (existing?.id) {
        await updateScore(sessionId, existing.id, {
          score,
          evidence_note: note,
          ...(transcriptEntryIds.length > 0 && { transcript_entry_ids: transcriptEntryIds }),
        });
        setLocalScores((prev) => ({ ...prev, [key]: { ...prev[key], score, note } }));
      } else {
        const result = await saveScore(sessionId, {
          dimension,
          sub_dimension: subDimension,
          score,
          evidence_note: note,
          transcript_entry_ids: transcriptEntryIds,
        });
        setLocalScores((prev) => ({ ...prev, [key]: { id: result.id, score, note } }));
      }
      setSuggestions((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    } finally {
      setSaving(false);
    }
  };

  const handleApplySuggestion = (dimension, subDimension, suggestion) => {
    const note = [suggestion.reasoning, ...(suggestion.key_evidence || [])].filter(Boolean).join(" | ");
    handleScore(
      dimension,
      subDimension,
      suggestion.suggested_score,
      note,
      suggestion.transcript_entry_ids || []
    );
  };

  const weightedTotal = computeTotal();

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
          justifyContent: "space-between",
          flexShrink: 0,
        }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <BarChart3 size={14} /> Evaluation
          <button
            className="btn btn-outline btn-sm"
            onClick={handleAiSuggest}
            disabled={suggesting}
            title={autoRefresh ? "AI 建议（后台每 7 分钟自动刷新）" : "AI 建议"}
            style={{ padding: "0.15rem 0.4rem", fontSize: "0.7rem" }}
          >
            <Sparkles size={11} /> {suggesting ? "..." : "AI 建议"}
          </button>
        </span>
        <span
          style={{
            fontFamily: "monospace",
            fontWeight: 700,
            fontSize: "1rem",
            color: weightedTotal >= 82 ? "var(--success)" : weightedTotal >= 72 ? "var(--accent-light)" : weightedTotal >= 65 ? "var(--warning)" : "var(--danger)",
          }}
        >
          {weightedTotal}/100
        </span>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "0.5rem" }}>
        {DIMENSIONS.map((dim) => (
          <div key={dim.name} style={{ marginBottom: "0.75rem" }}>
            <div
              style={{
                fontSize: "0.8rem",
                fontWeight: 700,
                color: "var(--accent-light)",
                marginBottom: "0.3rem",
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              <span>{dim.name}</span>
              <span style={{ fontSize: "0.7rem", color: "var(--text-dim)" }}>
                {Math.round(dim.weight * 100)}%
              </span>
            </div>
            {dim.subs.map((sub) => (
              <DimensionRow
                key={sub.name}
                dimension={dim.name}
                subDimension={sub.name}
                weight={sub.weight}
                value={localScores[`${dim.name}/${sub.name}`]?.score ?? null}
                suggestion={suggestions[`${dim.name}/${sub.name}`]}
                onScore={(score, note) => handleScore(dim.name, sub.name, score, note)}
                onApplySuggestion={(s) => handleApplySuggestion(dim.name, sub.name, s)}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
