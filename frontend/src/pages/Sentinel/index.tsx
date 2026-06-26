/**
 * SentinelPage — 哨兵 4 agent 主 demo 頁
 *
 * 結構:
 *   ┌──────────────────────────────────────┐
 *   │ Sentinel header + 健康狀態 + 中風老人載入鈕 │
 *   ├──────────────────────────────────────┤
 *   │ [Agent 1 Intake]  [Agent 2 Triage]   │
 *   │ [Agent 3 Audit]   [Agent 4 Education]│
 *   └──────────────────────────────────────┘
 *
 * 評審 / demo video 用這個頁面跑「中風老人」案例展示 4 agent 守門。
 */
import { useEffect, useState } from "react";
import { sentinelApi, SentinelHealth } from "@/lib/sentinelApi";
import IntakeCard from "./IntakeCard";
import TriageCard from "./TriageCard";
import AuditCard from "./AuditCard";
import EducationCard from "./EducationCard";
import {
  INTAKE_SAMPLE,
  TRIAGE_SAMPLE,
  AUDIT_SAMPLE,
  EDUCATION_SAMPLE,
} from "./strokePatientFixture";
import "@/styles/sentinel.css";

function SentinelPage() {
  const [health, setHealth] = useState<SentinelHealth | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  useEffect(() => {
    sentinelApi
      .health()
      .then(setHealth)
      .catch((e) => setHealthError(e?.message || String(e)));
  }, []);

  return (
    <div className="sentinel-page">
      <header className="sentinel-header">
        <h1>🛡️ Sentinel — Clinical Safety Agent Society</h1>
        <p className="sentinel-tagline">
          4 個 Qwen agent 守門員 · 補醫生盲點 · 對抗錨定偏誤與警示疲勞
        </p>
        <div className="sentinel-health">
          {healthError ? (
            <span className="sentinel-health-error">⚠ Backend 不通: {healthError}</span>
          ) : health ? (
            health.status === "ok" ? (
              <span className="sentinel-health-ok">
                ✓ {health.provider} · {health.model} · backend ready
              </span>
            ) : (
              <span className="sentinel-health-warn">
                ⚠ {health.status}: {health.reason || "(no reason)"}
              </span>
            )
          ) : (
            <span className="sentinel-health-loading">⏳ 檢查 backend...</span>
          )}
        </div>
        <div className="sentinel-demo-pill">
          📋 Demo case · 71 歲澳門男性 · 2024 缺血性中風後遺 · 高血壓 + 糖尿病 + 房顫 · warfarin + 銀杏成分不明
        </div>
      </header>

      <div className="sentinel-grid">
        <IntakeCard initial={INTAKE_SAMPLE} />
        <TriageCard initial={TRIAGE_SAMPLE} />
        <AuditCard initial={AUDIT_SAMPLE} />
        <EducationCard initial={EDUCATION_SAMPLE} />
      </div>

      <footer className="sentinel-footer">
        <p>
          🏆 Qwen Cloud Hackathon · Track 3 Agent Society · 截止 2026-07-09 · Built on Clinic OS
        </p>
      </footer>
    </div>
  );
}

export default SentinelPage;
