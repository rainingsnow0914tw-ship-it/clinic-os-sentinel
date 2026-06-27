import { Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from '@/pages/LoginPage';
import SelectClinicPage from '@/pages/SelectClinicPage';
import DashboardPage from '@/pages/DashboardPage';
import PatientsPage from '@/pages/PatientsPage';
import VisitPage from '@/pages/VisitPage';
import DrugsPage from '@/pages/DrugsPage';
import InventoryPage from '@/pages/InventoryPage';
import InvoicesPage from '@/pages/InvoicesPage';
import DocumentsPage from '@/pages/DocumentsPage';
import AIDraftsPage from '@/pages/AIDraftsPage';
import AgentTasksPage from '@/pages/AgentTasksPage';
import ReportsPage from '@/pages/ReportsPage';
import SettingsPage from '@/pages/SettingsPage';
import SentinelPatientsPage from '@/pages/SentinelPatients';
import SentinelPatientDetailPage from '@/pages/SentinelPatients/PatientDetail';
import SentinelNewVisitPage from '@/pages/SentinelPatients/NewVisitPage';
import AppShell from '@/components/AppShell';

/**
 * 路由總表
 *
 * 公開路由：
 *   /login
 *
 * 登入後（未選診所）：
 *   /select-clinic
 *
 * 登入後（已選診所，包在 AppShell 裡 → 有 sidebar / topbar）：
 *   /dashboard
 *   /patients          /patients/:id
 *   /visits/:id
 *   /drugs             /inventory
 *   /invoices
 *   /documents
 *   /ai-drafts         /agent-tasks
 *   /reports
 *   /settings/*
 *
 * Sprint 0 還沒接 auth guard，先用簡單路由結構，
 * Sprint 1 會加 ProtectedRoute 包 AppShell。
 */
function App() {
  return (
    <Routes>
      {/* hackathon demo: 開頁直接進 Sentinel 病人搜尋 */}
      <Route path="/" element={<Navigate to="/sentinel/patients" replace />} />

      {/* 公開頁 */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/select-clinic" element={<SelectClinicPage />} />

      {/* 主要功能（包在 AppShell 裡） */}
      <Route element={<AppShell />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/patients" element={<PatientsPage />} />
        <Route path="/patients/:patientId" element={<PatientsPage />} />
        <Route path="/visits/:visitId" element={<VisitPage />} />
        <Route path="/drugs" element={<DrugsPage />} />
        <Route path="/inventory" element={<InventoryPage />} />
        <Route path="/invoices" element={<InvoicesPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/ai-drafts" element={<AIDraftsPage />} />
        <Route path="/agent-tasks" element={<AgentTasksPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/settings/*" element={<SettingsPage />} />

        {/* Sentinel demo (hackathon 主秀) */}
        <Route path="/sentinel/patients" element={<SentinelPatientsPage />} />
        <Route path="/sentinel/patients/:patientId" element={<SentinelPatientDetailPage />} />
        <Route path="/sentinel/patients/:patientId/visit/new" element={<SentinelNewVisitPage />} />
      </Route>

      {/* 找不到路由 → 回 sentinel 搜尋 */}
      <Route path="*" element={<Navigate to="/sentinel/patients" replace />} />
    </Routes>
  );
}

export default App;
