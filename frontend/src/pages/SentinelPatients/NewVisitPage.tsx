/**
 * 新就診頁 (Phase 4.1)
 *
 * /sentinel/patients/:id/visit/new
 * 醫師填 SOAP-like 完整病歷 (CC/HPI/PE/Dx + vital signs), 寫進 DB
 * 後 redirect 回 detail page.
 *
 * Phase 4.2 會加: 4 agent 串通 (intake/triage/audit/education) + ai_drafts
 * Phase 4.3 會加: ai_drafts review (accept/dismiss)
 */
import { FormEvent, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  createVisit,
  getPatientDetail,
  listWatchlist,
  PatientDetail,
  runIntake,
  runTriage,
  runEducation,
  runAudit,
  IntakeResponse,
  TriageResponse,
  EducationResponse,
  AuditResponse,
  WatchlistItem,
} from '@/services/sentinelApi';
import './styles.css';

function NewVisitPage() {
  const { patientId } = useParams<{ patientId: string }>();
  const navigate = useNavigate();
  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // form state
  const [cc, setCc] = useState('');
  const [hpi, setHpi] = useState('');
  const [pe, setPe] = useState('');
  const [dx, setDx] = useState('');
  const [sbp, setSbp] = useState('');
  const [dbp, setDbp] = useState('');
  const [hr, setHr] = useState('');
  const [temp, setTemp] = useState('');
  const [spo2, setSpo2] = useState('');
  const [freeNotes, setFreeNotes] = useState('');
  const [rxInput, setRxInput] = useState('');   // Phase 4.2b: 處方一行一個

  // Phase 4.2a/b: sentinel agent panel
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [intakeResult, setIntakeResult] = useState<IntakeResponse | null>(null);
  const [triageResult, setTriageResult] = useState<TriageResponse | null>(null);
  const [educationResult, setEducationResult] = useState<EducationResponse | null>(null);
  const [auditResult, setAuditResult] = useState<AuditResponse | null>(null);

  // Phase 7.2: 醫師個人 watchlist (banner 提醒)
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);

  useEffect(() => {
    if (!patientId) return;
    getPatientDetail(patientId)
      .then(setPatient)
      .catch((e) => setError(e?.message ?? '載入病人資料失敗'))
      .finally(() => setLoading(false));
  }, [patientId]);

  useEffect(() => {
    // Phase 7.2: 載入醫師 watchlist
    listWatchlist()
      .then((r) => setWatchlist(r.items))
      .catch(() => {
        /* watchlist 失敗不阻塞新就診 */
      });
  }, []);

  async function runAiSuggestions() {
    if (!patient) return;
    if (!cc.trim()) {
      setAiError('CC 必填才能跑 AI');
      return;
    }
    setAiLoading(true);
    setAiError(null);
    setIntakeResult(null);
    setTriageResult(null);
    setEducationResult(null);
    setAuditResult(null);
    try {
      // 並行 call sentinel agents (Qwen 每個 5-15s, 並行加快)
      const hl = patient.heart_layer;
      const workingHypothesis = dx.trim() || cc;
      const rxList = rxInput.split('\n').map((s) => s.trim()).filter(Boolean);

      const [intakeRes, triageRes, eduRes, auditRes] = await Promise.allSettled([
        runIntake(`${cc}${hpi ? '。' + hpi : ''}`, cc),
        runTriage(workingHypothesis, hl.flags, hl.problems, hl.medications),
        dx.trim() ? runEducation(dx, patient.name) : Promise.reject(new Error('skip: dx 空')),
        rxList.length > 0
          ? runAudit(rxList, hl.flags, hl.medications, hl.problems)
          : Promise.reject(new Error('skip: 處方空')),
      ]);
      if (intakeRes.status === 'fulfilled') setIntakeResult(intakeRes.value);
      if (triageRes.status === 'fulfilled') setTriageResult(triageRes.value);
      if (eduRes.status === 'fulfilled') setEducationResult(eduRes.value);
      if (auditRes.status === 'fulfilled') setAuditResult(auditRes.value);

      // 抓 error 顯示 (skip 不算錯)
      const errs = [intakeRes, triageRes, eduRes, auditRes]
        .filter((r) => r.status === 'rejected')
        .map((r: any) => r.reason?.message ?? String(r.reason))
        .filter((m) => !m.startsWith('skip:'));
      if (errs.length === 4) {
        setAiError(`所有 agent 都失敗：${errs.join(' | ')}`);
      } else if (errs.length > 0) {
        setAiError(`部分 agent 失敗：${errs.join(' | ')}`);
      }
    } catch (e: any) {
      setAiError(e?.message ?? 'AI 跑失敗');
    } finally {
      setAiLoading(false);
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!patientId) return;
    if (!cc.trim()) {
      setError('主訴 (CC) 必填');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const vs: Record<string, number> = {};
      if (sbp) vs.blood_pressure_systolic = parseInt(sbp);
      if (dbp) vs.blood_pressure_diastolic = parseInt(dbp);
      if (hr) vs.heart_rate = parseInt(hr);
      if (temp) vs.temperature_c = parseFloat(temp);
      if (spo2) vs.oxygen_saturation = parseInt(spo2);

      // Phase 4.2c: 把 AI panel 結果 dump 成 ai_drafts (status='accepted_with_visit')
      const aiDrafts: { agent_type: 'intake' | 'triage' | 'audit' | 'education'; payload: any }[] = [];
      if (intakeResult) aiDrafts.push({ agent_type: 'intake', payload: intakeResult });
      if (triageResult) aiDrafts.push({ agent_type: 'triage', payload: triageResult });
      if (auditResult) aiDrafts.push({ agent_type: 'audit', payload: auditResult });
      if (educationResult) aiDrafts.push({ agent_type: 'education', payload: educationResult });

      const rxLines = rxInput.split('\n').map((s) => s.trim()).filter(Boolean);

      const res = await createVisit(patientId, {
        chief_complaint: cc,
        hpi: hpi || undefined,
        physical_exam: pe || undefined,
        diagnosis: dx || undefined,
        vital_signs: Object.keys(vs).length ? vs : undefined,
        free_notes: freeNotes || undefined,
        ai_drafts: aiDrafts.length > 0 ? aiDrafts : undefined,
        prescription_lines: rxLines.length > 0 ? rxLines : undefined,
      });
      // 寫進 DB 完成 → 回 detail 頁
      navigate(`/sentinel/patients/${patientId}?new_visit=${res.visit_id}`);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e?.message ?? '建立失敗');
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="sentinel-page"><div className="loading">載入中...</div></div>;
  if (!patient) return <div className="sentinel-page"><div className="error">病人不存在</div></div>;

  // 心臟層快速摘要 (給醫師寫病歷時參考)
  const hl = patient.heart_layer;
  const redFlags = hl.flags.filter((f) => f.severity === 'red');

  return (
    <div className="sentinel-page">
      <Link to={`/sentinel/patients/${patientId}`} className="back-link">← 回病例</Link>

      <div className="detail-header">
        <div className="name">
          🩺 新就診：{patient.name}{' '}
          <span style={{ color: '#6b7280', fontWeight: 'normal', fontSize: 14 }}>
            ({patient.gender ?? '?'} / {patient.date_of_birth ?? '?'})
          </span>
        </div>
        <div className="meta">
          {patient.id_number ?? '-'} · 今天 {new Date().toISOString().split('T')[0]}
        </div>

        {/* 心臟層 quick reference */}
        {(redFlags.length > 0 || hl.problems.length > 0) && (
          <div className="quick-ref">
            {redFlags.length > 0 && (
              <div className="quick-ref-row red">
                ⚠ 紅旗: {redFlags.map((f) => f.content).join('、')}
              </div>
            )}
            {hl.problems.length > 0 && (
              <div className="quick-ref-row">
                💢 慢性病: {hl.problems.map((p) => p.problem_name).join('、')}
              </div>
            )}
            {hl.medications.length > 0 && (
              <div className="quick-ref-row">
                💊 長期用藥: {hl.medications.slice(0, 3).map((m) => `${m.medication_name} ${m.dosage ?? ''}`.trim()).join('、')}
                {hl.medications.length > 3 && ` ...+${hl.medications.length - 3}`}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Phase 7.2: 醫師 watchlist banner (AI 反訓練醫生) */}
      {watchlist.length > 0 && (
        <details className="doctor-watchlist-banner" open>
          <summary>
            📌 你過去學到的 ({watchlist.length} 條 watchlist)
            <span className="watchlist-hint">寫病歷時順手對照</span>
          </summary>
          <ul className="watchlist-list">
            {watchlist.map((w) => (
              <li key={w.id} className="watchlist-item">
                <div className="watchlist-pattern">
                  <strong>📌 {w.pattern}</strong>
                  {w.triggered_count > 0 && (
                    <span className="watchlist-trigger-count">已撞 {w.triggered_count} 次</span>
                  )}
                </div>
                <div className="watchlist-lesson">{w.lesson_text}</div>
              </li>
            ))}
          </ul>
        </details>
      )}

      {error && <div className="error" style={{ marginBottom: 12 }}>⚠️ {error}</div>}

      <form onSubmit={onSubmit} className="new-visit-form">
        <label>
          <span className="field-label">CC 主訴 <span className="required">*</span></span>
          <input
            type="text"
            placeholder="例: 頭痛 2 天"
            value={cc}
            onChange={(e) => setCc(e.target.value)}
            required
          />
        </label>

        <label>
          <span className="field-label">HPI 現病史</span>
          <textarea
            rows={3}
            placeholder="例: 病人 2 天前出現後腦脹痛, 晨起明顯, 無噁心嘔吐, 自測 BP 158/95"
            value={hpi}
            onChange={(e) => setHpi(e.target.value)}
          />
        </label>

        <label>
          <span className="field-label">PE 查體</span>
          <textarea
            rows={3}
            placeholder="例: 神清, BP 158/95, HR 78, 心音清晰、無雜音, 雙肺呼吸音清"
            value={pe}
            onChange={(e) => setPe(e.target.value)}
          />
        </label>

        <fieldset className="vital-fieldset">
          <legend>生命徵象</legend>
          <div className="vital-grid">
            <label>
              <span className="field-label">收縮壓 SBP</span>
              <input type="number" placeholder="120" value={sbp} onChange={(e) => setSbp(e.target.value)} />
            </label>
            <label>
              <span className="field-label">舒張壓 DBP</span>
              <input type="number" placeholder="80" value={dbp} onChange={(e) => setDbp(e.target.value)} />
            </label>
            <label>
              <span className="field-label">心率 HR</span>
              <input type="number" placeholder="78" value={hr} onChange={(e) => setHr(e.target.value)} />
            </label>
            <label>
              <span className="field-label">體溫 °C</span>
              <input type="number" step="0.1" placeholder="36.7" value={temp} onChange={(e) => setTemp(e.target.value)} />
            </label>
            <label>
              <span className="field-label">SpO₂ %</span>
              <input type="number" placeholder="98" value={spo2} onChange={(e) => setSpo2(e.target.value)} />
            </label>
          </div>
        </fieldset>

        <label>
          <span className="field-label">IMP 診斷</span>
          <input
            type="text"
            placeholder="例: 原發性高血壓 (未達標)"
            value={dx}
            onChange={(e) => setDx(e.target.value)}
          />
        </label>

        <label>
          <span className="field-label">Rx 處方 (一行一個藥, 跑 AI audit 用 / Phase 4.2c 才會寫進 DB)</span>
          <textarea
            rows={3}
            placeholder={'例:\nAmlodipine 5mg qd\nIbuprofen 400mg tid prn'}
            value={rxInput}
            onChange={(e) => setRxInput(e.target.value)}
          />
        </label>

        <label>
          <span className="field-label">補充筆記 (free notes)</span>
          <textarea
            rows={2}
            placeholder="其他補充"
            value={freeNotes}
            onChange={(e) => setFreeNotes(e.target.value)}
          />
        </label>

        <div className="form-actions">
          <Link to={`/sentinel/patients/${patientId}`} className="btn-cancel">取消</Link>
          <button
            type="button"
            onClick={runAiSuggestions}
            disabled={aiLoading || !cc.trim()}
            className="btn-ai"
            title="並行跑 sentinel intake/triage/education，每個 Qwen 5-15s"
          >
            {aiLoading ? '🤖 AI 跑中... (5-30s)' : '🤖 跑 AI 建議'}
          </button>
          <button type="submit" disabled={saving} className="btn-primary">
            {saving ? '建立中...' : '✅ 完成就診'}
          </button>
        </div>

        <div style={{ marginTop: 8, color: '#9ca3af', fontSize: 12 }}>
          Phase 4.2a/b: 「跑 AI 建議」並行 call sentinel 4 agent (intake/triage/audit/education),
          Qwen3.7-max 結果在下方 panel。Phase 4.2c 會加 ai_drafts table 寫入 + 接受寫進病歷。
        </div>
      </form>

      {/* AI 建議 panel */}
      {(aiError || intakeResult || triageResult || educationResult || auditResult) && (
        <div className="ai-panel">
          <h3>🤖 Sentinel AI 建議</h3>
          {aiError && <div className="error" style={{ marginBottom: 8 }}>⚠️ {aiError}</div>}

          {auditResult && (
            <div className="ai-section ai-section-audit">
              <div className="ai-section-title">
                🚨 後閘門 (Audit) · {auditResult.model_used}
              </div>
              {auditResult.contextual_risks.length > 0 && (
                <ul className="ai-findings">
                  {auditResult.contextual_risks.map((r, i) => (
                    <li key={`ctx-${i}`}>
                      {r.needs_confirmation && <span className="ai-section-tag" style={{ background: '#fee2e2', color: '#991b1b' }}>⚠ 需確認</span>}
                      <strong>{r.drug}</strong>: {r.risk}
                      <div className="ai-refs">triggered by: {r.triggered_by}</div>
                    </li>
                  ))}
                </ul>
              )}
              {auditResult.rule_engine_findings.length > 0 && (
                <div style={{ marginTop: 6 }}>
                  <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 4 }}>規則引擎發現:</div>
                  <ul className="ai-findings">
                    {auditResult.rule_engine_findings.map((f, i) => (
                      <li key={`rule-${i}`}>
                        <span className="ai-section-tag" style={{ background: '#fef3c7', color: '#92400e' }}>{f.severity}</span>
                        {f.drug_a} ↔ {f.drug_b}: {f.evidence}
                        {f.recommendation && <div className="ai-refs">建議: {f.recommendation}</div>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {auditResult.contextual_risks.length === 0 &&
                auditResult.rule_engine_findings.length === 0 && (
                  <div style={{ color: '#6b7280', fontSize: 12 }}>(無風險、處方 OK)</div>
                )}
              {auditResult.unknowns.length > 0 && (
                <div className="ai-note">未知藥物: {auditResult.unknowns.join(', ')}</div>
              )}
              <div className="ai-note">{auditResult.closing_note}</div>
            </div>
          )}

          {intakeResult && (
            <div className="ai-section ai-section-intake">
              <div className="ai-section-title">
                🚪 入口偵查官 (Intake) · {intakeResult.model_used}
              </div>
              {intakeResult.summary && <div className="ai-summary">{intakeResult.summary}</div>}
              {intakeResult.findings.length > 0 ? (
                <ul className="ai-findings">
                  {intakeResult.findings.map((f, i) => (
                    <li key={i}>
                      <span className="ai-section-tag">{f.section}</span> {f.text}
                    </li>
                  ))}
                </ul>
              ) : (
                <div style={{ color: '#6b7280', fontSize: 12 }}>(沒 finding)</div>
              )}
            </div>
          )}

          {triageResult && (
            <div className="ai-section ai-section-triage">
              <div className="ai-section-title">
                🚦 前閘門 (Triage) · {triageResult.model_used}
              </div>
              {triageResult.has_conflict && (
                <div className="ai-conflict">⚠ 矛盾: {triageResult.conflict_summary}</div>
              )}
              {triageResult.differentials.length > 0 ? (
                <ul className="ai-findings">
                  {triageResult.differentials.map((d, i) => (
                    <li key={i}>
                      <strong>{d.name}</strong>: {d.reason}
                      {d.references && d.references.length > 0 && (
                        <div className="ai-refs">refs: {d.references.join(', ')}</div>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <div style={{ color: '#6b7280', fontSize: 12 }}>(無鑑別建議)</div>
              )}
              <div className="ai-note">{triageResult.closing_note}</div>
            </div>
          )}

          {educationResult && (
            <div className="ai-section ai-section-edu">
              <div className="ai-section-title">
                📚 衛教官 (Education) · {educationResult.model_used}
              </div>
              <div className="ai-advice">{educationResult.advice}</div>
            </div>
          )}

          <div style={{ marginTop: 8, color: '#9ca3af', fontSize: 11 }}>
            * 醫師可看 AI 建議後修改上方 form 再 ✅ 完成就診 (AI 不會自動寫進病歷, ADR-006 精神)
          </div>
        </div>
      )}
    </div>
  );
}

export default NewVisitPage;
