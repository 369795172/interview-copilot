import { useEffect, useState, useCallback } from "react";
import { BarChart3 } from "lucide-react";
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

export default function ScoreCard({ sessionId, transcript }) {
  const { saveScore, updateScore } = useInterview();
  const [localScores, setLocalScores] = useState({});
  const [saving, setSaving] = useState(false);
  const coverage = useInterviewStore((s) => s.coverage);

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

  const handleScore = async (dimension, subDimension, score, note) => {
    const key = `${dimension}/${subDimension}`;
    const existing = localScores[key];

    setSaving(true);
    try {
      if (existing?.id) {
        await updateScore(sessionId, existing.id, { score, evidence_note: note });
        setLocalScores((prev) => ({ ...prev, [key]: { ...prev[key], score, note } }));
      } else {
        const result = await saveScore(sessionId, {
          dimension,
          sub_dimension: subDimension,
          score,
          evidence_note: note,
          transcript_entry_ids: [],
        });
        setLocalScores((prev) => ({ ...prev, [key]: { id: result.id, score, note } }));
      }
    } finally {
      setSaving(false);
    }
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
        <span style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
          <BarChart3 size={14} /> Evaluation
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
                value={localScores[`${dim.name}/${sub.name}`]?.score || null}
                onScore={(score, note) => handleScore(dim.name, sub.name, score, note)}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
