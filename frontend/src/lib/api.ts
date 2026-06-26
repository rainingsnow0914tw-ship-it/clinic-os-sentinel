/**
 * API client
 *
 * 設計重點：
 * 1. 自動在 header 帶 Firebase ID Token（Authorization: Bearer xxx）
 * 2. 自動在 header 帶 X-Clinic-Id（從本地狀態取目前選中的診所）
 * 3. 統一錯誤處理：401 自動踢回 /login，403 顯示權限不足
 *
 * baseURL 來源：
 *   - 開發：留空 → 由 Vite proxy 把 /api 轉到 backend
 *   - 正式：VITE_API_BASE_URL（Cloud Run URL）
 */
import axios, { AxiosError } from 'axios';
import { auth } from './firebase';

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api';

export const apiClient = axios.create({
  baseURL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request 攔截器：自動加 Firebase token + clinic id
apiClient.interceptors.request.use(async (config) => {
  // 1. Firebase ID Token
  if (auth?.currentUser) {
    const idToken = await auth.currentUser.getIdToken();
    config.headers.Authorization = `Bearer ${idToken}`;
  }
  // 2. X-Clinic-Id（從 zustand store 拿，Sprint 1 會接上）
  const clinicId = localStorage.getItem('current_clinic_id');
  if (clinicId) {
    config.headers['X-Clinic-Id'] = clinicId;
  }
  return config;
});

// Response 攔截器：401 → 踢回 login
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Sprint 1 會改成 router.push，目前先用 location
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
