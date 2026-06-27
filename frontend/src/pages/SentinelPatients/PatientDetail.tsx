/**
 * Sentinel 病例瀏覽頁 (v0.3.1 §5.2)
 *
 * 顯示:
 * - 病人 demographics
 * - 心臟層摘要 (4 段:flags / problems / medications / baselines)
 * - 就診歷史 timeline
 *
 * UI 規則 (v0.3.1 §7.3):
 * - to_observe flag = 淡色 (badge.observe)
 * - confirmed flag  = 亮紅 (badge.confirmed)
 */
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  addWatchlist,
  getPatientDetail,
  PatientDetail,
  reviewVisit,
  ReviewModeKind,
  ReviewResponse,
} from '@/services/sentinelApi';
import './styles.css';

interface ReviewState {
  loading?: boolean;
  result?: ReviewResponse;
  mode?: ReviewModeKind;
  error?: string;
}

function PatientDetailPage() {
  const { patientId } = useParams<{ patientId: string }>();
  const [detail, setDetail] = useState<PatientDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Phase 6: per-visit review state (Mode A/B 並存, switch 蓋掉前一個)
  const [reviewMap, setReviewMap] = useState<Record<string, ReviewState>>({});

  useEffect(() => {
    if (!patientId) return;
    setLoading(true);
    getPatientDetail(patientId)
      .then(setDetail)
      .catch((e) => setError(e?.message ?? '載入失敗'))
      .finally(() => setLoading(false));
  }, [patientId]);

  async function handleReview(visitId: string, mode: ReviewModeKind) {
    setReviewMap((m) => ({ ...m, [visitId]: { loading: true, mode } }));
    try {
      const result = await reviewVisit(visitId, mode);
      setReviewMap((m) => ({ ...m, [visitId]: { loading: false, result, mode } }));
    } catch (e: any) {
      setReviewMap((m) => ({
        ...m,
        [visitId]: { loading: false, mode, error: e?.message ?? '回顧失敗' },
      }));
    }
  }

  if (loading) return <div className="sentinel-page"><div className="loading">載入中...</div></div>;
  if (error)   return <div className="sentinel-page"><div className="error">⚠️ {error}</div></div>;
  if (!detail) return null;

  const hl = detail.heart_layer;

  return (
    <div className="sentinel-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <Link to="/sentinel/patients" className="back-link">← 回搜尋</Link>
        <Link to={`/sentinel/patients/${detail.id}/visit/new`} className="btn-primary" style={{ textDecoration: 'none' }}>
          ➕ 新就診
        </Link>
      </div>

      <div className="detail-header">
        <div className="name">
          {detail.name}{' '}
          <span style={{ color: '#6b7280', fontWeight: 'normal', fontSize: 14 }}>
            ({detail.gender ?? '?'} / {detail.date_of_birth ?? '?'})
          </span>
        </div>
        <div className="meta">
          {detail.id_number ?? '-'} · {detail.phone ?? '-'}
        </div>
      </div>

      {/* 心臟層 4 段 */}
      <div className="heart-section">
        <h3>
          🚨 紅旗 / Flags
          <span className="count">共 {hl.flags.length} 條</span>
        </h3>
        {hl.flags.length === 0 ? (
          <div style={{ color: '#9ca3af', fontSize: 13 }}>(無紅旗)</div>
        ) : (
          <ul className="heart-list">
            {hl.flags.map((f) => (
              <li key={f.id}>
                <div className="label">
                  <span className="name-text">{f.content}</span>
                  <div className="sub">
                    {f.flag_type} · 來源 {f.flag_source}
                  </div>
                </div>
                <div className="badges">
                  {f.severity === 'red' && <span className="badge red">{f.severity}</span>}
                  {f.severity && f.severity !== 'red' && (
                    <span className="badge">{f.severity}</span>
                  )}
                  <span
                    className={`badge ${
                      f.confidence_status === 'confirmed' ? 'confirmed' : 'observe'
                    }`}
                  >
                    {f.confidence_status}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="heart-section">
        <h3>
          💢 慢性病 / Problems
          <span className="count">共 {hl.problems.length} 條</span>
        </h3>
        {hl.problems.length === 0 ? (
          <div style={{ color: '#9ca3af', fontSize: 13 }}>(無慢性病紀錄)</div>
        ) : (
          <ul className="heart-list">
            {hl.problems.map((p) => (
              <li key={p.id}>
                <div className="label">
                  <span className="name-text">{p.problem_name}</span>
                  <div className="sub">
                    {p.icd10_code && <>ICD-10 {p.icd10_code} · </>}
                    狀態 {p.control_status}
                    {p.diagnosed_at && <> · 診斷 {p.diagnosed_at}</>}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="heart-section">
        <h3>
          💊 長期用藥 / Medications
          <span className="count">共 {hl.medications.length} 條</span>
        </h3>
        {hl.medications.length === 0 ? (
          <div style={{ color: '#9ca3af', fontSize: 13 }}>(無長期用藥紀錄)</div>
        ) : (
          <ul className="heart-list">
            {hl.medications.map((m) => (
              <li key={m.id}>
                <div className="label">
                  <span className="name-text">{m.medication_name}</span>
                  <div className="sub">
                    {m.category}
                    {m.dosage && <> · {m.dosage}</>}
                    {m.frequency && <> · {m.frequency}</>}
                  </div>
                </div>
                {!m.is_active && <span className="badge">已停</span>}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="heart-section">
        <h3>
          📊 基線 / Baselines
          <span className="count">共 {hl.baselines.length} 條</span>
        </h3>
        {hl.baselines.length === 0 ? (
          <div style={{ color: '#9ca3af', fontSize: 13 }}>(無基線紀錄)</div>
        ) : (
          <ul className="heart-list">
            {hl.baselines.map((b) => (
              <li key={b.id}>
                <div className="label">
                  <span className="name-text">{b.value_text}</span>
                  <div className="sub">
                    {b.category}
                    {b.measured_at && <> · 測 {b.measured_at}</>}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* 就診歷史 timeline */}
      <div className="timeline-section">
        <h3>📅 就診歷史 (共 {detail.visits.length} 次)</h3>
        {detail.visits.length === 0 ? (
          <div style={{ color: '#9ca3af', fontSize: 13 }}>(尚無就診紀錄)</div>
        ) : (
          detail.visits.map((v) => {
            const vs = v.vital_signs;
            const labs = v.lab_results ?? [];
            return (
              <div className="visit-row" key={v.id}>
                <div className="visit-date">
                  📅 {v.visit_date?.split('T')[0] ?? v.visit_date} · [{v.status}]
                </div>
                {v.chief_complaint && (
                  <div className="visit-cc"><strong>CC 主訴：</strong>{v.chief_complaint}</div>
                )}
                {v.hpi && (
                  <div className="visit-hpi"><strong>HPI 現病史：</strong>{v.hpi}</div>
                )}
                {v.physical_exam && (
                  <div className="visit-pe"><strong>PE 查體：</strong>{v.physical_exam}</div>
                )}
                {v.diagnosis && (
                  <div className="visit-dx"><strong>IMP 診斷：</strong>{v.diagnosis}</div>
                )}

                {/* 生命徵象 */}
                {vs && (
                  <div className="vital-signs">
                    {vs.blood_pressure_systolic != null && vs.blood_pressure_diastolic != null && (
                      <span className="vs-chip">
                        BP {vs.blood_pressure_systolic}/{vs.blood_pressure_diastolic}
                      </span>
                    )}
                    {vs.heart_rate != null && (
                      <span className="vs-chip">HR {vs.heart_rate}</span>
                    )}
                    {vs.temperature_c != null && (
                      <span className="vs-chip">T {vs.temperature_c}°C</span>
                    )}
                    {vs.oxygen_saturation != null && (
                      <span className="vs-chip">SpO₂ {vs.oxygen_saturation}%</span>
                    )}
                    {vs.respiratory_rate != null && (
                      <span className="vs-chip">RR {vs.respiratory_rate}</span>
                    )}
                  </div>
                )}

                {/* 實驗室 */}
                {labs.length > 0 && (
                  <div className="lab-list">
                    <div className="lab-title">🧪 實驗室數據</div>
                    {labs.map((lab, i) => (
                      <div key={i} className={`lab-row ${lab.is_abnormal ? 'abnormal' : ''}`}>
                        <span className="lab-name">{lab.name}</span>
                        <span className="lab-value">
                          {lab.value} {lab.unit}
                        </span>
                        {lab.reference_range && (
                          <span className="lab-ref">(正常 {lab.reference_range})</span>
                        )}
                        {lab.is_abnormal && <span className="lab-flag">↑↓</span>}
                      </div>
                    ))}
                  </div>
                )}

                {/* 影像 / ECG */}
                {v.xray_findings && (
                  <div className="finding-block">
                    <strong>🩻 X-ray:</strong> {v.xray_findings}
                  </div>
                )}
                {v.ecg_findings && (
                  <div className="finding-block">
                    <strong>📈 ECG:</strong> {v.ecg_findings}
                  </div>
                )}

                {/* Rx 處方 */}
                {v.prescription_items && v.prescription_items.length > 0 && (
                  <div className="rx-list">
                    <div className="rx-title">💊 Rx 處方</div>
                    {v.prescription_items.map((rx, i) => (
                      <div key={i} className="rx-row">
                        <span className="rx-no">{i + 1}.</span>
                        <span className="rx-name">{rx.drug_name}</span>
                        {rx.usage_text && (
                          <span className="rx-usage">{rx.usage_text}</span>
                        )}
                        {rx.days && rx.total_quantity != null && (
                          <span className="rx-meta">
                            × {rx.days}D ({rx.total_quantity}{rx.unit ?? ''})
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Phase 6: AI 回顧 (Track 1 MemoryAgent 主秀, 司機 6/28 簡化成單按鈕) */}
                <div className="review-section">
                  <div className="review-header">
                    🔁 <strong>AI 回顧此次就診</strong>
                    <span className="review-hint">(模擬當時情境 + 注入歷次 visit, 找出當時就該想到的盲點)</span>
                  </div>
                  <div className="review-buttons">
                    <button
                      className="btn-review btn-mode-a"
                      onClick={() => handleReview(v.id, 'at_the_time')}
                      disabled={reviewMap[v.id]?.loading}
                    >
                      🔁 跑 AI 回顧 (約 30-60 秒)
                    </button>
                  </div>

                  {reviewMap[v.id]?.loading && (
                    <div className="review-loading">
                      ⏳ 跑 4 agent 並行中... (Qwen3.7-max, 約 5-45 秒)
                    </div>
                  )}
                  {reviewMap[v.id]?.error && (
                    <div className="review-error">⚠️ {reviewMap[v.id].error}</div>
                  )}
                  {reviewMap[v.id]?.result && !reviewMap[v.id]?.loading && (
                    <ReviewResultPanel result={reviewMap[v.id]!.result!} />
                  )}
                </div>

                {/* Phase 4.2d: 當時 AI 建議 (折疊) */}
                {v.ai_drafts && v.ai_drafts.length > 0 && (
                  <details className="ai-drafts-record">
                    <summary>📋 當時 AI 建議 ({v.ai_drafts.length} 條 / {v.ai_drafts[0].status})</summary>
                    {v.ai_drafts.map((d) => {
                      const p = d.payload || {};
                      return (
                        <div key={d.id} className="ai-draft-row">
                          <div className="ai-draft-tag">{d.agent_type}</div>
                          {d.agent_type === 'intake' && (
                            <div>
                              {p.summary && <div className="ai-draft-text">{p.summary}</div>}
                              {p.findings && p.findings.length > 0 && (
                                <ul className="ai-draft-list">
                                  {p.findings.map((f: any, i: number) => (
                                    <li key={i}><span className="ai-section-tag">{f.section}</span>{f.text}</li>
                                  ))}
                                </ul>
                              )}
                            </div>
                          )}
                          {d.agent_type === 'triage' && (
                            <div>
                              {p.has_conflict && <div className="ai-conflict">⚠ {p.conflict_summary}</div>}
                              {p.differentials && p.differentials.length > 0 && (
                                <ul className="ai-draft-list">
                                  {p.differentials.map((diff: any, i: number) => (
                                    <li key={i}><strong>{diff.name}</strong>: {diff.reason}</li>
                                  ))}
                                </ul>
                              )}
                            </div>
                          )}
                          {d.agent_type === 'audit' && (
                            <div>
                              {p.contextual_risks && p.contextual_risks.length > 0 && (
                                <ul className="ai-draft-list">
                                  {p.contextual_risks.map((r: any, i: number) => (
                                    <li key={i}>
                                      {r.needs_confirmation && <span className="ai-section-tag" style={{ background: '#fee2e2', color: '#991b1b' }}>⚠</span>}
                                      <strong>{r.drug}</strong>: {r.risk}
                                    </li>
                                  ))}
                                </ul>
                              )}
                              {(!p.contextual_risks || p.contextual_risks.length === 0) && (
                                <div className="ai-draft-text">(無風險)</div>
                              )}
                            </div>
                          )}
                          {d.agent_type === 'education' && (
                            <div className="ai-draft-text" style={{ whiteSpace: 'pre-wrap' }}>{p.advice}</div>
                          )}
                        </div>
                      );
                    })}
                  </details>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

/**
 * Phase 6: Mode A/B 回顧結果 panel.
 *
 * 上半: mode header + heart_layer_source + summary
 * 中段: 4 agent panel (intake/triage/audit/education, 可能 null)
 * 下緣: mode_disclaimer (Mode B 提醒不究責)
 */
function ReviewResultPanel({ result }: { result: ReviewResponse }) {
  const mode = result.mode;
  const modeColor = '#1d4ed8';
  const [savedLessonId, setSavedLessonId] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveBusy, setSaveBusy] = useState(false);

  // 從 audit findings 萃取 watchlist pattern + lesson
  function extractLesson(): { pattern: string; lesson: string } | null {
    const audit: any = result.audit;
    if (!audit) return null;
    const rf = audit.rule_engine_findings?.[0];
    const cr = audit.contextual_risks?.[0];
    if (!rf && !cr) return null;

    let pattern = '';
    if (rf?.drug_a && rf?.drug_b) {
      pattern = `${rf.drug_a} + ${rf.drug_b} interaction`;
    } else if (cr?.triggered_by) {
      pattern = cr.triggered_by;
    } else {
      pattern = audit.closing_note?.slice(0, 60) || 'AI 教育要點';
    }
    const lessonParts: string[] = [];
    if (rf?.description) lessonParts.push(rf.description);
    if (cr?.risk) lessonParts.push(`情境風險: ${cr.risk}`);
    if (audit.closing_note) lessonParts.push(`建議: ${audit.closing_note}`);
    const lesson = lessonParts.join('\n').slice(0, 1000);

    return pattern && lesson ? { pattern, lesson } : null;
  }

  async function handleAddWatchlist() {
    const ext = extractLesson();
    if (!ext) return;
    setSaveBusy(true);
    setSaveError(null);
    try {
      const item = await addWatchlist({
        pattern: ext.pattern,
        lesson_text: ext.lesson,
        source_visit_id: result.visit_id,
        source_mode: mode.mode,
      });
      setSavedLessonId(item.id);
    } catch (e: any) {
      setSaveError(e?.message ?? '加入失敗');
    } finally {
      setSaveBusy(false);
    }
  }

  const canSave = !!result.audit && !savedLessonId;
  return (
    <div className="review-result">
      <div className="review-mode-header" style={{ borderLeftColor: modeColor }}>
        <div>
          <span className="review-mode-badge" style={{ background: modeColor }}>
            AI 回顧
          </span>
          <span className="review-source">當時心臟層來源: {mode.heart_layer_source}</span>
        </div>
        {mode.summary_text && (
          <div className="review-summary">
            <strong>AI 看到的當時心臟層 + 歷次 visit:</strong>
            <pre>{mode.summary_text}</pre>
          </div>
        )}
      </div>

      {result.intake && (
        <div className="review-agent intake">
          <div className="review-agent-title">🔍 入口偵查官 (intake)</div>
          {result.intake.summary && <div>{result.intake.summary}</div>}
          {result.intake.findings && result.intake.findings.length > 0 && (
            <ul>
              {result.intake.findings.map((f: any, i: number) => (
                <li key={i}>
                  <span className="ai-section-tag">{f.section}</span>{f.text}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {result.triage && (
        <div className="review-agent triage">
          <div className="review-agent-title">⚖️ 前閘門 (triage)</div>
          {result.triage.has_conflict && (
            <div className="ai-conflict">⚠ {result.triage.conflict_summary}</div>
          )}
          {result.triage.differentials && result.triage.differentials.length > 0 && (
            <ul>
              {result.triage.differentials.map((d: any, i: number) => (
                <li key={i}>
                  <strong>{d.diagnosis || d.name}</strong>: {d.reasoning || d.reason}
                  {d.source_url && (
                    <> · <a href={d.source_url} target="_blank" rel="noreferrer">來源</a></>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {result.audit && (
        <div className="review-agent audit">
          <div className="review-agent-title">🛡️ 後閘門 (audit)</div>
          {result.audit.rule_engine_findings && result.audit.rule_engine_findings.length > 0 && (
            <>
              <div className="review-agent-subtitle">規則引擎:</div>
              <ul>
                {result.audit.rule_engine_findings.map((r: any, i: number) => (
                  <li key={i}>
                    <strong>{r.drug_a} × {r.drug_b}</strong> ({r.severity}): {r.description || r.evidence}
                  </li>
                ))}
              </ul>
            </>
          )}
          {result.audit.contextual_risks && result.audit.contextual_risks.length > 0 && (
            <>
              <div className="review-agent-subtitle">情境風險:</div>
              <ul>
                {result.audit.contextual_risks.map((r: any, i: number) => (
                  <li key={i}>
                    {r.needs_confirmation && (
                      <span className="ai-section-tag" style={{ background: '#fee2e2', color: '#991b1b' }}>⚠</span>
                    )}
                    <strong>{r.drug}</strong>: {r.risk}
                    {r.triggered_by && <> (觸發: {r.triggered_by})</>}
                  </li>
                ))}
              </ul>
            </>
          )}
          {result.audit.unknowns && result.audit.unknowns.length > 0 && (
            <div>成分不明: {result.audit.unknowns.join(', ')}</div>
          )}
        </div>
      )}

      {result.education && (
        <div className="review-agent education">
          <div className="review-agent-title">📚 衛教 (education)</div>
          <div style={{ whiteSpace: 'pre-wrap' }}>{result.education.advice}</div>
        </div>
      )}

      {result.skipped && result.skipped.length > 0 && (
        <div className="review-skipped">
          ⓘ 略過: {result.skipped.join(' / ')}
        </div>
      )}

      <div className="review-disclaimer" style={{ borderLeftColor: modeColor }}>
        💡 {result.mode_disclaimer}
      </div>

      {/* Phase 7.2: AI 回顧後加進醫師 watchlist (AI 反訓練醫生) */}
      {result.audit && (
        <div className="watchlist-action">
          {savedLessonId ? (
            <div className="watchlist-saved">
              ✅ 已加進你的 watchlist。下次新就診頁頂部會 banner 提醒。
            </div>
          ) : (
            <button
              className="btn-add-watchlist"
              disabled={saveBusy || !canSave}
              onClick={handleAddWatchlist}
            >
              📌 把這個教訓加進我的 watchlist
            </button>
          )}
          {saveError && <div className="watchlist-error">⚠️ {saveError}</div>}
        </div>
      )}
    </div>
  );
}

export default PatientDetailPage;
