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
import { getPatientDetail, PatientDetail } from '@/services/sentinelApi';
import './styles.css';

function PatientDetailPage() {
  const { patientId } = useParams<{ patientId: string }>();
  const [detail, setDetail] = useState<PatientDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!patientId) return;
    setLoading(true);
    getPatientDetail(patientId)
      .then(setDetail)
      .catch((e) => setError(e?.message ?? '載入失敗'))
      .finally(() => setLoading(false));
  }, [patientId]);

  if (loading) return <div className="sentinel-page"><div className="loading">載入中...</div></div>;
  if (error)   return <div className="sentinel-page"><div className="error">⚠️ {error}</div></div>;
  if (!detail) return null;

  const hl = detail.heart_layer;

  return (
    <div className="sentinel-page">
      <Link to="/sentinel/patients" className="back-link">← 回搜尋</Link>

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
          detail.visits.map((v) => (
            <div className="visit-row" key={v.id}>
              <div className="visit-date">
                📅 {v.visit_date?.split('T')[0] ?? v.visit_date} · [{v.status}]
              </div>
              {v.chief_complaint && (
                <div className="visit-cc">主訴：{v.chief_complaint}</div>
              )}
              {v.diagnosis && (
                <div className="visit-dx">診斷：{v.diagnosis}</div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default PatientDetailPage;
