/**
 * IntakeCard — Agent 1 入口偵查官 UI
 *
 * 輸入:醫生口述
 * 輸出:findings 按 section 分組顯示(main_complaint / extra / anomaly / suggested_question)
 */
import { useState } from "react";
import { sentinelApi, IntakeRequest, IntakeResponse } from "@/lib/sentinelApi";

interface Props {
  initial: IntakeRequest;
}

const SECTION_LABELS: Record<string, { label: string; bg: string }> = {
  main_complaint: { label: "主訴相關", bg: "#dbeafe" },
  extra: { label: "額外提及", bg: "#fef3c7" },
  anomaly: { label: "反常標記", bg: "#fee2e2" },
  suggested_question: { label: "建議追問", bg: "#dcfce7" },
};

function IntakeCard({ initial }: Props) {
  const [dictation, setDictation] = useState(initial.raw_dictation);
  const [hint, setHint] = useState(initial.chief_complaint_hint || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IntakeResponse | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await sentinelApi.intake({ raw_dictation: dictation, chief_complaint_hint: hint || null });
      setResult(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="sentinel-card">
      <div className="sentinel-card-header">
        <h3>🔍 Agent 1 · 入口偵查官</h3>
        <span className="sentinel-card-sub">原話全留 / 分類不過濾 / 標反常 / 補漏</span>
      </div>

      <div className="sentinel-card-body">
        <label className="sentinel-label">主訴提示</label>
        <input
          value={hint}
          onChange={(e) => setHint(e.target.value)}
          className="sentinel-input"
          placeholder="例:疲倦、左手無力"
        />

        <label className="sentinel-label">醫生口述原話</label>
        <textarea
          value={dictation}
          onChange={(e) => setDictation(e.target.value)}
          className="sentinel-textarea"
          rows={4}
        />

        <button onClick={run} disabled={loading} className="sentinel-btn">
          {loading ? "Qwen 思考中..." : "跑入口偵查官"}
        </button>

        {error && <div className="sentinel-error">[FAIL] {error}</div>}

        {result && (
          <div className="sentinel-result">
            {result.summary && (
              <div className="sentinel-summary">
                <strong>摘要:</strong> {result.summary}
              </div>
            )}
            {result.findings.length === 0 ? (
              <p className="sentinel-empty">(沒有發現)</p>
            ) : (
              <div className="sentinel-findings">
                {result.findings.map((f, i) => {
                  const meta = SECTION_LABELS[f.section] || { label: f.section, bg: "#f3f4f6" };
                  return (
                    <div key={i} className="sentinel-finding" style={{ background: meta.bg }}>
                      <div className="sentinel-finding-tag">{meta.label}</div>
                      <div className="sentinel-finding-text">{f.text}</div>
                      {f.linkage && <div className="sentinel-finding-link">↳ {f.linkage}</div>}
                    </div>
                  );
                })}
              </div>
            )}
            <div className="sentinel-tokens">
              {result.model_used} · in {result.input_tokens} / out {result.output_tokens} tokens
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default IntakeCard;
