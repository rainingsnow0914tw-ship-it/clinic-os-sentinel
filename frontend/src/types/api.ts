/**
 * API 類型定義
 *
 * 與 backend Pydantic schemas 對齊。
 * Sprint 0 只放最小骨架，每個 Sprint 補對應的類型。
 *
 * 未來如果要更嚴謹，可以考慮 OpenAPI codegen（FastAPI 自帶 /openapi.json），
 * 但 Sprint 0 先手寫，避免過早工具化。
 */

// ─── 角色與權限 ───────────────────────────────────────────────
export type ClinicRole = 'owner' | 'doctor' | 'nurse' | 'reception';

export interface CustomPermissions {
  can_manage_inventory?: boolean;
  can_view_revenue_report?: boolean;
  can_manage_users?: boolean;
  can_void_invoice?: boolean;
}

// ─── User & Clinic ──────────────────────────────────────────
export interface User {
  id: string;
  name: string;
  email: string;
  phone?: string | null;
  status: 'active' | 'suspended' | 'deleted';
  created_at: string;
}

export interface Clinic {
  id: string;
  name: string;
  address?: string | null;
  phone?: string | null;
  email?: string | null;
  receipt_header?: string | null;
  logo_url?: string | null;
  timezone: string;
  currency: string;
}

export interface ClinicMembership {
  id: string;
  clinic_id: string;
  user_id: string;
  role: ClinicRole;
  custom_permissions_json: CustomPermissions;
  is_active: boolean;
}

// ─── 共用 ──────────────────────────────────────────────────
export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ApiError {
  detail: string;
  code?: string;
}
