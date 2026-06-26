/**
 * Firebase 初始化
 *
 * 從 .env.local 讀取設定，全 app 共用一個 instance。
 * Sprint 0 只是骨架，Sprint 1 才會真正接 Google Sign-In + getIdToken
 */
import { initializeApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider } from 'firebase/auth';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

// 沒填設定時不要直接 crash，只 warn（讓 Sprint 0 純前端開發也能跑起來）
const isConfigured = Boolean(firebaseConfig.apiKey && firebaseConfig.projectId);
if (!isConfigured) {
  console.warn(
    '[firebase] 尚未設定，登入功能會無法運作。請複製 .env.example → .env.local 並填入設定。'
  );
}

export const firebaseApp = isConfigured ? initializeApp(firebaseConfig) : null;
export const auth = firebaseApp ? getAuth(firebaseApp) : null;
export const googleProvider = new GoogleAuthProvider();
