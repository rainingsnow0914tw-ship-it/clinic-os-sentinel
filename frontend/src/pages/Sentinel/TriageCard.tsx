/**
 * TriageCard — Agent 2 前閘門鑑別診斷官 UI
 *
 * 輸入:醫生工作假設 + 病人紅旗/慢性病/長期用藥(從 fixture 帶,可看)
 * 輸出:
 *   - has_conflict 醒目顯示
 *   - conflict_summary
 *   - differentials list(附 PubMed 連結)
 */
import { useState } from "react";
import { sentinelApi, TriageRequest, TriageResponse } from "@/lib/sentinelApi";

interface Props {
  initial: TriageRequest;
}

function TriageCard({ initial }: Props) {
  const [hypothesis, setHypothesis] = useState(initial.working_hypothesis);
  const [showHeart, setShowHeart] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TriageResponse | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await sentinelApi.triage({
        working_hypothesis: hypothesis,
        flags: initial.flags,
        problems: initial.problems,
        medications: initial.medications,
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
        <h3>🚪 Agent 2 · 前閘門鑑別診斷官</h3>
        <span className="sentinel-card-sub">撞紅旗找盲點,只在矛盾夠強時喊,附 PubMed 來源</span>
      </div>

      <div className="sentinel-card-body">
        <label className="sentinel-label">醫生工作假設</label>
        <input
          value={hypothesis}
          onChange={(e) => setHypothesis(e.target.value)}
          className="sentinel-input"
        />

        <button onClick={() => setShowHeart(!showHeart)} className="sentinel-link-btn">
          {showHeart ? "▼ 收起" : "▶ 展開"} 病人心臟資料
          {" "}
          (flags:{initial.flags?.length || 0} · problems:{initial.problems?.length || 0} · meds:{initial.medications?.length || 0})
        </button>
        {showHeart && (
          <div className="sentinel-heart-panel">
            {initial.flags && initial.flags.length > 0 && (
              <div>
                <strong>紅旗:</strong>
                <ul>
                  {initial.flags.map((f, i) => (
                    <li key={i}>[{f.type}] {f.content}</li>
                  ))}
                </ul>
              </div>
            )}
            {initial.problems && initial.problems.length > 0 && (
              <div>
                <strong>慢性病:</strong>
                <ul>
                  {initial.problems.map((p, i) => (
                    <li key={i}>{p.name} {p.control_status && `[${p.control_status}]`}</li>
                  ))}
                </ul>
              </div>
            )}
            {initial.medications && initial.medications.length > 0 && (
              <div>
                <strong>長期用藥:</strong>
                <ul>
                  {initial.medications.map((m, i) => (
                    <li key={i}>{m.name} {!m.composition_certain && "⚠成分不明"}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        <button onClick={run} disabled={loading} className="sentinel-btn">
          {loading ? "Qwen 思考中..." : "跑前閘門"}
        </button>

        {error && <div className="sentinel-error">[FAIL] {error}</div>}

        {result && (
          <div className="sentinel-result">
            {result.has_conflict ? (
              <>
                <div className="sentinel-conflict">
                  <strong>⚠ 觸發矛盾:</strong> {result.conflict_summary}
                </div>
                {result.differentials.length === 0 ? (
                  <p className="sentinel-empty">(沒有鑑別)</p>
                ) : (
                  <div className="sentinel-differentials">
                    {result.differentials.map((d, i) => (
                      <div key={i} className="sentinel-differential">
                        <div className="sentinel-diagnosis">{i + 1}. {d.diagnosis}</div>
                        <div className="sentinel-reasoning">{d.reasoning}</div>
                        {d.source_url && (
                          <a href={d.source_url} target="_blank" rel="noopener noreferrer" className="sentinel-source">
                            📄 PubMed {d.source_pmid}
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div className="sentinel-no-conflict">✓ 無真實矛盾,不亂喊(對抗警示疲勞)</div>
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

export default TriageCard;
