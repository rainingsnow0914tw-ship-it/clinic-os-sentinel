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
import { createVisit, getPatientDetail, PatientDetail } from '@/services/sentinelApi';
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

  useEffect(() => {
    if (!patientId) return;
    getPatientDetail(patientId)
      .then(setPatient)
      .catch((e) => setError(e?.message ?? '載入病人資料失敗'))
      .finally(() => setLoading(false));
  }, [patientId]);

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

      const res = await createVisit(patientId, {
        chief_complaint: cc,
        hpi: hpi || undefined,
        physical_exam: pe || undefined,
        diagnosis: dx || undefined,
        vital_signs: Object.keys(vs).length ? vs : undefined,
        free_notes: freeNotes || undefined,
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
          <button type="submit" disabled={saving} className="btn-primary">
            {saving ? '建立中...' : '✅ 完成就診'}
          </button>
        </div>

        <div style={{ marginTop: 8, color: '#9ca3af', fontSize: 12 }}>
          Phase 4.1 草版: 寫進 DB 後立刻 completed. Phase 4.2 會加 4 agent 串通 + ai_drafts review.
        </div>
      </form>
    </div>
  );
}

export default NewVisitPage;
