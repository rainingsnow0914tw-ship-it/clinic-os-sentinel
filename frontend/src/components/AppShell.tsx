import { NavLink, Outlet } from 'react-router-dom';

/**
 * AppShell — 主要功能頁的版型
 *
 * Sentinel hackathon scope: 只有 🛡️ 哨兵病人搜尋 是 live demo, 其他 jimmy v1
 * Sprint 1/2 stub 留著當 future modules placeholder, 灰色 + Coming soon 標,
 * 避免評審誤解以為都做完了。
 */

const LIVE_NAV = {
  to: '/sentinel/patients',
  zh: '🛡️ 哨兵病人搜尋',
  en: 'The Sentinel · Patient Search',
};

const FUTURE_MODULES = [
  { zh: '🏠 首頁', en: 'Home' },
  { zh: '👤 病人主檔', en: 'Patient master' },
  { zh: '💊 藥品主檔', en: 'Drug master' },
  { zh: '📦 庫存', en: 'Inventory' },
  { zh: '🧾 收據', en: 'Invoices' },
  { zh: '📄 文件', en: 'Documents' },
  { zh: '🤖 AI 草稿', en: 'AI drafts' },
  { zh: '🦾 Agent 任務', en: 'Agent tasks' },
  { zh: '📊 報表', en: 'Reports' },
  { zh: '⚙️ 設定', en: 'Settings' },
];

function AppShell() {
  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <h1>
          Clinic OS
          <span className="sidebar-sub">Qwen Cloud Hackathon 2026</span>
        </h1>

        <nav>
          <div className="nav-section-label">
            🟢 Live demo
            <span className="bi-en">In this submission</span>
          </div>
          <NavLink
            to={LIVE_NAV.to}
            className={({ isActive }) => (isActive ? 'active nav-live' : 'nav-live')}
          >
            <div>{LIVE_NAV.zh}</div>
            <div className="bi-en">{LIVE_NAV.en}</div>
          </NavLink>

          <div className="nav-section-label nav-section-future">
            🚧 Future modules
            <span className="bi-en">Not in hackathon scope</span>
          </div>
          {FUTURE_MODULES.map((m) => (
            <span
              key={m.zh}
              className="nav-soon"
              title="Out of hackathon scope — not implemented in this submission"
            >
              <div>{m.zh}</div>
              <div className="bi-en">{m.en}</div>
            </span>
          ))}
        </nav>
      </aside>

      <header className="app-topbar">
        <div style={{ flex: 1, color: '#6b7280' }}>
          <span>
            Demo clinic / 示範診所: 千問哨兵示範診所 (Qwen Sentinel Demo Clinic)
          </span>
        </div>
        <div style={{ color: '#6b7280' }}>
          <span>👋 Judge mode / 評審模式 (dev-bypass, no login)</span>
        </div>
      </header>

      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}

export default AppShell;
