import { NavLink, Outlet } from 'react-router-dom';

/**
 * AppShell — 主要功能頁的版型
 *
 * 結構：左側 sidebar 導覽 + 上方 topbar（顯示診所、user）+ 中間 main outlet
 * Sprint 0 只放骨架，Sprint 1 會接上實際的診所切換、user info、登出
 */

const NAV_ITEMS = [
  { to: '/sentinel/patients', label: '🛡️ 哨兵病人搜尋' },
  { to: '/dashboard', label: '🏠 首頁' },
  { to: '/patients', label: '👤 病人 (jimmy stub)' },
  { to: '/drugs', label: '💊 藥品主檔' },
  { to: '/inventory', label: '📦 庫存' },
  { to: '/invoices', label: '🧾 收據' },
  { to: '/documents', label: '📄 文件' },
  { to: '/ai-drafts', label: '🤖 AI 草稿' },
  { to: '/agent-tasks', label: '🦾 Agent 任務' },
  { to: '/reports', label: '📊 報表' },
  { to: '/settings/clinic', label: '⚙️ 設定' },
];

function AppShell() {
  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <h1>Clinic OS</h1>
        <nav>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => (isActive ? 'active' : '')}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <header className="app-topbar">
        <div style={{ flex: 1, color: '#6b7280' }}>
          {/* Sprint 1 會放診所選擇器 + 搜尋列 */}
          <span>目前診所：（Sprint 1 接入）</span>
        </div>
        <div style={{ color: '#6b7280' }}>
          {/* Sprint 1 會放使用者頭像與登出 */}
          <span>👋 訪客</span>
        </div>
      </header>

      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}

export default AppShell;
