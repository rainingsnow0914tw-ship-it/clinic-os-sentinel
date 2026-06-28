/**
 * Sentinel 病人搜尋頁 (v0.3.1 §5.1)
 *
 * 入口 page:醫生 -> 搜尋 -> 結果卡 -> 開啟病例 -> /sentinel/patients/:id
 * Bilingual labels (Qwen Cloud Hackathon 2026): 中文 UI + English overlay
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { searchPatients, PatientCard } from '@/services/sentinelApi';
import './styles.css';

function SentinelPatientsPage() {
  const [q, setQ] = useState('');
  const [items, setItems] = useState<PatientCard[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runSearch(query: string) {
    setLoading(true);
    setError(null);
    try {
      const data = await searchPatients(query);
      setItems(data.items);
    } catch (e: any) {
      setError(e?.message ?? '搜尋失敗 / Search failed');
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    runSearch('');
  }, []);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    runSearch(q);
  }

  return (
    <div className="sentinel-page">
      <h2>
        🛡️ 哨兵 病人搜尋
        <span className="bi-en">The Sentinel · Patient Search</span>
      </h2>

      <form onSubmit={onSubmit} className="sentinel-search-row">
        <input
          type="text"
          placeholder="搜尋 姓名 / 電話 / 身份證 (留空看全部) · Search by name / phone / ID (blank = show all)"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button type="submit" disabled={loading}>
          {loading ? (
            <span className="bi-stack">
              <span>搜尋中...</span>
              <span className="bi-en">Searching...</span>
            </span>
          ) : (
            <span className="bi-stack">
              <span>🔍 搜尋</span>
              <span className="bi-en">Search</span>
            </span>
          )}
        </button>
      </form>

      {error && <div className="error">⚠️ {error}</div>}

      {!loading && items.length === 0 && (
        <div className="sentinel-empty">
          沒有符合條件的病人。 · No matching patients.
        </div>
      )}

      {items.map((p) => (
        <div className="sentinel-card" key={p.id}>
          <div style={{ flex: 1 }}>
            <div className="name">
              {p.name}{' '}
              <span style={{ color: '#6b7280', fontWeight: 'normal', fontSize: 13 }}>
                ({p.gender ?? '?'} / {p.date_of_birth ?? '?'})
              </span>
            </div>
            <div className="meta">
              {p.id_number ?? '-'} · {p.phone ?? '-'}
            </div>
            <div className="badges">
              {p.has_red_flag && (
                <span className="badge red">
                  ⚠ 紅旗<span className="bi-en">Red flag</span>
                </span>
              )}
              {p.flag_count > 0 && (
                <span className="badge">
                  紅旗 × {p.flag_count}<span className="bi-en">Flags</span>
                </span>
              )}
              {p.chronic_count > 0 && (
                <span className="badge chronic">
                  慢性病 × {p.chronic_count}<span className="bi-en">Chronic</span>
                </span>
              )}
              {p.flag_count === 0 && p.chronic_count === 0 && (
                <span className="badge">
                  無心臟層紀錄<span className="bi-en">No heart layer</span>
                </span>
              )}
            </div>
          </div>
          <div className="actions">
            <Link to={`/sentinel/patients/${p.id}`}>
              <span className="bi-stack">
                <span>開啟病例 →</span>
                <span className="bi-en">Open chart</span>
              </span>
            </Link>
          </div>
        </div>
      ))}

      <div style={{ marginTop: 16, color: '#6b7280', fontSize: 12 }}>
        共 {items.length} 筆 / {items.length} results · Sentinel demo (dev-bypass mode)
      </div>
    </div>
  );
}

export default SentinelPatientsPage;
