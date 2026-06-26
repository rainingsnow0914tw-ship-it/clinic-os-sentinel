/**
 * EducationCard — Agent 4 衛教出口官 UI
 *
 * 輸入:診斷 + 病人習慣 (key-value)
 * 輸出:advice + reasoning
 */
import { useState } from "react";
import { sentinelApi, EducationRequest, EducationResponse } from "@/lib/sentinelApi";

interface Props {
  initial: EducationRequest;
}

function EducationCard({ initial }: Props) {
  const [diagnosis, setDiagnosis] = useState(initial.diagnosis);
  const [habits, setHabits] = useState(JSON.stringify(initial.patient_habits || {}, null, 2));
  const [name, setName] = useState(initial.patient_name_hint || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EducationResponse | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      let parsedHabits = {};
      try {
        parsedHabits = JSON.parse(habits);
      } catch {
        setError("habits 不是合法 JSON");
        setLoading(false);
        return;
      }
      const r = await sentinelApi.education({
        diagnosis,
        patient_habits: parsedHabits,
        patient_name_hint: name || null,
      });
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
        <h3>💬 Agent 4 · 衛教出口官</h3>
        <span className="sentinel-card-sub">個人化生活醫囑 · 可解釋為什麼,不示範動作</span>
      </div>

      <div className="sentinel-card-body">
        <label className="sentinel-label">診斷</label>
        <input value={diagnosis} onChange={(e) => setDiagnosis(e.target.value)} className="sentinel-input" />

        <label className="sentinel-label">病人稱呼(可選)</label>
        <input value={name} onChange={(e) => setName(e.target.value)} className="sentinel-input" />

        <label className="sentinel-label">病人習慣 (JSON)</label>
        <textarea
          value={habits}
          onChange={(e) => setHabits(e.target.value)}
          className="sentinel-textarea"
          rows={4}
        />

        <button onClick={run} disabled={loading} className="sentinel-btn">
          {loading ? "Qwen 思考中..." : "跑衛教官"}
        </button>

        {error && <div className="sentinel-error">[FAIL] {error}</div>}

        {result && (
          <div className="sentinel-result">
            <div className="sentinel-advice">
              <h4>給病人的生活醫囑</h4>
              <p>{result.advice}</p>
            </div>
            {result.reasoning && (
              <div className="sentinel-reasoning-box">
                <h4>為什麼這樣建議</h4>
                <p>{result.reasoning}</p>
              </div>
            )}
            <div className="sentinel-closing">{result.closing_note}</div>
            <div className="sentinel-tokens">
              {result.model_used} · in {result.input_tokens} / out {result.output_tokens} tokens
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default EducationCard;
