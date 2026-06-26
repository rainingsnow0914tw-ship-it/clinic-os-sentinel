/**
 * AuditCard — Agent 3 後閘門處方審計官 UI
 *
 * 輸入:新處方藥名 list + 病人心臟(紅旗 / 慢性病 / 長期用藥)
 * 輸出:
 *   - 規則引擎結果(事實查表)
 *   - AI 第三層情境推理風險
 *   - 成分不明保健品提醒
 */
import { useState } from "react";
import { sentinelApi, AuditRequest, AuditResponse } from "@/lib/sentinelApi";

interface Props {
  initial: AuditRequest;
}

const SEVERITY_COLOR: Record<string, string> = {
  contraindicated: "#dc2626",
  major: "#ea580c",
  moderate: "#d97706",
  minor: "#65a30d",
  unknown: "#6b7280",
};

function AuditCard({ initial }: Props) {
  const [prescription, setPrescription] = useState(initial.new_prescription.join(", "));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AuditResponse | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const drugs = prescription.split(",").map((s) => s.trim()).filter(Boolean);
      const r = await sentinelApi.audit({
        new_prescription: drugs,
        flags: initial.flags,
        long_term_medications: initial.long_term_medications,
        problems: initial.problems,
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
        <h3>🛡️ Agent 3 · 後閘門處方審計官</h3>
        <span className="sentinel-card-sub">三層界線:事實查表(規則引擎) + AI 第三層情境推理</span>
      </div>

      <div className="sentinel-card-body">
        <label className="sentinel-label">新處方(逗號分隔)</label>
        <input
          value={prescription}
          onChange={(e) => setPrescription(e.target.value)}
          className="sentinel-input"
          placeholder="例:ibuprofen 400mg, paracetamol 500mg"
        />

        <button onClick={run} disabled={loading} className="sentinel-btn">
          {loading ? "Qwen + 規則引擎處理中..." : "跑後閘門"}
        </button>

        {error && <div className="sentinel-error">[FAIL] {error}</div>}

        {result && (
          <div className="sentinel-result">
            <h4>📋 規則引擎(事實查表)</h4>
            {result.rule_engine_findings.length === 0 ? (
              <p className="sentinel-empty">(沒有藥物對藥物層級的命中)</p>
            ) : (
              <div className="sentinel-rules">
                {result.rule_engine_findings.map((r, i) => (
                  <div key={i} className="sentinel-rule">
                    <div className="sentinel-rule-pair">
                      {r.drug_a} × {r.drug_b}
                      <span
                        className="sentinel-severity"
                        style={{ background: SEVERITY_COLOR[r.severity] || "#6b7280" }}
                      >
                        {r.severity}
                      </span>
                      {r.needs_confirmation && <span className="sentinel-confirm">⚠ 需確認</span>}
                    </div>
                    <div className="sentinel-rule-desc">{r.description}</div>
                    {r.source_url && (
                      <a href={r.source_url} target="_blank" rel="noopener noreferrer" className="sentinel-source">
                        📄 {r.source}
                      </a>
                    )}
                  </div>
                ))}
              </div>
            )}

            <h4 style={{ marginTop: 16 }}>🧠 AI 第三層情境風險</h4>
            {result.contextual_risks.length === 0 ? (
              <p className="sentinel-empty">(無具體情境風險)</p>
            ) : (
              <div className="sentinel-risks">
                {result.contextual_risks.map((r, i) => (
                  <div key={i} className="sentinel-risk">
                    <div className="sentinel-risk-drug">💊 {r.drug}</div>
                    <div className="sentinel-risk-text">{r.risk}</div>
                    <div className="sentinel-risk-trigger">觸發:{r.triggered_by}</div>
                  </div>
                ))}
              </div>
            )}

            {result.unknowns.length > 0 && (
              <>
                <h4 style={{ marginTop: 16 }}>❓ 不確定提醒</h4>
                <ul className="sentinel-unknowns">
                  {result.unknowns.map((u, i) => (
                    <li key={i}>{u}</li>
                  ))}
                </ul>
              </>
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

export default AuditCard;
