/**
 * Sentinel 病人搜尋頁 (v0.3.1 §5.1)
 *
 * 入口 page:醫生 -> 搜尋 -> 結果卡 -> 開啟病例 -> /sentinel/patients/:id
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
      setError(e?.message ?? '搜尋失敗');
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  // 第一次載入抓全部 (限 50)
  useEffect(() => {
    runSearch('');
  }, []);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    runSearch(q);
  }

  return (
    <div className="sentinel-page">
      <h2>🛡️ 哨兵 病人搜尋</h2>

      <form onSubmit={onSubmit} className="sentinel-search-row">
        <input
          type="text"
          placeholder="搜尋 姓名 / 電話 / 身份證號碼 (留空看全部)"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button type="submit" disabled={loading}>
          {loading ? '搜尋中...' : '🔍 搜尋'}
        </button>
      </form>

      {error && <div className="error">⚠️ {error}</div>}

      {!loading && items.length === 0 && (
        <div className="sentinel-empty">沒有符合條件的病人。</div>
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
              {p.has_red_flag && <span className="badge red">⚠ 紅旗</span>}
              {p.flag_count > 0 && (
                <span className="badge">紅旗 × {p.flag_count}</span>
              )}
              {p.chronic_count > 0 && (
                <span className="badge chronic">慢性病 × {p.chronic_count}</span>
              )}
              {p.flag_count === 0 && p.chronic_count === 0 && (
                <span className="badge">無心臟層紀錄</span>
              )}
            </div>
          </div>
          <div className="actions">
            <Link to={`/sentinel/patients/${p.id}`}>開啟病例 →</Link>
          </div>
        </div>
      ))}

      <div style={{ marginTop: 16, color: '#6b7280', fontSize: 12 }}>
        共 {items.length} 筆 · Sentinel demo dev-bypass 模式
      </div>
    </div>
  );
}

export default SentinelPatientsPage;
