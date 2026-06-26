"""
============================================================
scripts/extend_visits_and_examinations.py -- 補 visit + examination dataset
============================================================
Phase 3 frontend 上後司機反饋「點開大部分病人都空白」-- 因為 jimmy 60 個
patient 只有 5 個 visit、我擴的 40 個新 patient 一個 visit 都沒有。

本 script 為**每個 patient** 生 1-3 個 visit + 對應 visit_examination
(vital signs / lab results 結構化)、根據 patient 慢性病做 chronic-aware
disease-specific 主訴 / 診斷 / 數據 (例：高血壓 BP 偏高、糖尿病 HbA1c 偏高)。

直接對 DB 操作 (不走 jimmy mock → seed_dev_data)、idempotent:
  - source='extended_mock' 區隔 jimmy 'mock'
  - 重跑會先刪 source='extended_mock' 再灌
  - reset_dev_data 守門 source='mock' 不會誤砍

用法:
    ENVIRONMENT=dev python -m scripts.extend_visits_and_examinations
    ENVIRONMENT=dev python -m scripts.extend_visits_and_examinations --dry-run
============================================================
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import (
    Clinic,
    Patient,
    PatientProblem,
    User,
    Visit,
    VisitExamination,
)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-5s | %(message)s")
log = logging.getLogger("extend_visits")

SEED = 20260627
SOURCE_TAG = "extended_mock"


# ─────────────────────────────────────────────────────────
# Chronic-aware pools
# ─────────────────────────────────────────────────────────

COMPLAINT_BY_CHRONIC = {
    # 重要: chief_complaint = 病人自述的「症狀 + 時長/頻率」, 不是醫師 follow-up 行為
    "Hypertension":          ["頭痛 2 天", "頭暈 3 天", "後腦痛 早上明顯",
                              "自測 BP 偏高 1 週", "頸部僵硬 1 週", "視力模糊 偶發 3 天"],
    "Type 2 Diabetes":       ["口渴 頻尿 加重 2 週", "腳麻 1 個月", "視力模糊 1 個月",
                              "傷口不癒合 2 週", "夜尿 增加 3 次/晚", "疲倦 3 週"],
    "Hyperlipidemia":        ["頸痛 1 週", "心悸 偶發", "頭暈 起身時"],
    "Asthma":                ["夜咳 1 週", "喘 2 天", "胸悶 一週",
                              "氣短 爬樓梯時 3 天", "咳嗽 帶白痰 3 天"],
    "COPD":                  ["喘 加重 1 週", "咳嗽 帶痰 2 週", "夜間呼吸困難 3 天"],
    "Osteoarthritis":        ["膝痛 加重 1 週", "上下樓梯腳痛 5 天",
                              "關節僵硬 早上明顯", "腰痛 3 天"],
    "Atrial Fibrillation":   ["心悸 3 天", "胸悶 偶發 1 週", "頭暈 1 週", "疲倦 加重"],
    "CKD Stage 3":           ["下肢水腫 3 天", "尿量減少 1 週",
                              "疲倦 3 週", "夜尿增加 4 次/晚"],
    "Hypothyroidism":        ["疲倦 1 個月", "怕冷 3 週",
                              "體重增加 2 公斤 1 個月", "便秘 2 週"],
    "Anxiety Disorder":      ["失眠 1 週", "心悸 加重 3 天",
                              "胸悶 焦慮時", "頭痛 緊張時"],
    "Migraine":              ["偏頭痛 3 天 反覆", "頭痛 怕光 怕吵 2 天",
                              "頭痛 + 嘔吐 1 天"],
    "GERD":                  ["胃酸逆流 1 週", "胸悶 餐後加重",
                              "喉嚨灼熱 半夜 1 週", "咳嗽 餐後 5 天"],
    "BPH":                   ["夜尿 4-5 次/晚", "排尿困難 1 個月", "尿流變細 2 週"],
    "Heart Failure":         ["喘 加重 3 天", "下肢水腫 1 週",
                              "夜間平躺呼吸困難 5 天", "疲倦 加重 2 週"],
    "Dementia":              ["健忘加重 1 月 (家屬陳述)", "走錯路 1 次",
                              "情緒易怒 2 週"],
    "Depression":            ["情緒低落 1 個月", "失眠 2 週",
                              "食慾減退 3 週", "對事物失去興趣"],
    "Gout":                  ["腳趾痛 急性 1 天", "膝紅腫熱痛 2 天",
                              "腳踝腫痛 半夜醒"],
    "Osteoporosis":          ["腰背痛 加重 2 週", "輕微跌倒後痛 3 天"],
}

DIAGNOSIS_BY_CHRONIC = {
    "Hypertension":          ["原發性高血壓 (控制中)", "原發性高血壓 (未達標)"],
    "Type 2 Diabetes":       ["第二型糖尿病 (控制中)", "第二型糖尿病 (HbA1c 偏高)"],
    "Hyperlipidemia":        ["高血脂症 (Statin 治療中)"],
    "Asthma":                ["氣喘 急性發作", "氣喘 (穩定追蹤)"],
    "COPD":                  ["COPD 急性惡化 (mild)", "COPD (穩定)"],
    "Osteoarthritis":        ["膝部骨關節炎"],
    "Atrial Fibrillation":   ["心房顫動 (rate-controlled)"],
    "CKD Stage 3":           ["慢性腎臟病第三期"],
    "Hypothyroidism":        ["甲狀腺機能低下"],
    "Anxiety Disorder":      ["廣泛性焦慮症"],
    "Migraine":              ["偏頭痛 (無先兆)"],
    "GERD":                  ["胃食道逆流"],
    "BPH":                   ["攝護腺肥大"],
    "Heart Failure":         ["鬱血性心衰竭 (NYHA II)"],
    "Dementia":              ["輕度認知障礙 (MCI)"],
    "Depression":            ["重度憂鬱症 (中度)"],
    "Gout":                  ["痛風 急性發作"],
    "Osteoporosis":          ["骨質疏鬆症"],
}

# 健康 / 無 chronic 病人的 generic CC pool (一律症狀 + 時長/頻率)
GENERIC_COMPLAINTS = [
    "咳嗽 3 天", "咳嗽 帶痰 5 天", "夜咳 1 週",
    "流鼻水 5 天", "鼻塞 3 天", "喉嚨痛 2 天", "聲音沙啞 4 天",
    "頭痛 2 天", "頭暈 3 天", "偏頭痛 1 天",
    "拉肚子 4 次/日 持續 2 天", "嘔吐 3 次 半天", "腹痛 + 拉肚子 1 天",
    "皮膚紅疹 2 天", "搔癢 1 週", "蕁麻疹 反覆 1 週",
    "腰痛 3 天", "膝痛 + 腫脹 2 天", "肩頸僵硬 1 週",
    "失眠 1 週", "疲倦 2 週",
    "輕度發燒 38.2 一天", "發燒 + 喉嚨痛 2 天",
    "耳痛 2 天", "眼睛紅 + 分泌物 3 天",
    "胃悶 餐後不適 1 週",
]
GENERIC_DIAGNOSES = [
    "急性上呼吸道感染", "急性鼻咽炎", "急性扁桃腺炎",
    "急性腸胃炎", "病毒性腸胃炎",
    "接觸性皮膚炎", "蕁麻疹", "過敏性鼻炎",
    "肌肉拉傷", "緊張型頭痛", "失眠症 評估",
    "外耳炎", "急性結膜炎", "胃食道逆流 (新診)",
]


# ─────────────────────────────────────────────────────────
# Vital signs profile (chronic-aware ranges)
# ─────────────────────────────────────────────────────────

def gen_vital_signs(chronic_set: set[str], age: int, rng: random.Random) -> dict[str, Any]:
    """根據 chronic 跟年齡生 vital signs。"""
    # BP base
    if "Hypertension" in chronic_set:
        sbp = rng.randint(140, 168)
        dbp = rng.randint(86, 102)
    elif "Heart Failure" in chronic_set:
        sbp = rng.randint(95, 125)
        dbp = rng.randint(60, 80)
    elif age >= 70:
        sbp = rng.randint(125, 145)
        dbp = rng.randint(72, 88)
    else:
        sbp = rng.randint(108, 130)
        dbp = rng.randint(65, 82)

    # HR
    if "Atrial Fibrillation" in chronic_set:
        hr = rng.randint(70, 110)
    elif "Heart Failure" in chronic_set:
        hr = rng.randint(85, 105)
    else:
        hr = rng.randint(62, 90)

    # T
    t = round(rng.uniform(36.4, 37.4), 1)

    # SpO2
    if "COPD" in chronic_set:
        spo2 = rng.randint(91, 96)
    elif "Asthma" in chronic_set:
        spo2 = rng.randint(94, 99)
    else:
        spo2 = rng.randint(97, 100)

    return {
        "blood_pressure_systolic": sbp,
        "blood_pressure_diastolic": dbp,
        "heart_rate": hr,
        "respiratory_rate": rng.randint(14, 20),
        "temperature_c": t,
        "oxygen_saturation": spo2,
    }


# ─────────────────────────────────────────────────────────
# Lab results (disease-specific)
# ─────────────────────────────────────────────────────────

def gen_lab_results(chronic_set: set[str], rng: random.Random) -> list[dict[str, Any]]:
    """根據 chronic 隨機生 1-4 個 lab result。"""
    labs: list[dict[str, Any]] = []

    if "Type 2 Diabetes" in chronic_set:
        hba1c = round(rng.uniform(6.5, 9.2), 1)
        labs.append({
            "name": "HbA1c",
            "value": hba1c,
            "unit": "%",
            "reference_range": "<6.0",
            "is_abnormal": hba1c >= 6.5,
        })
        glu = rng.randint(110, 220)
        labs.append({
            "name": "Fasting Glucose",
            "value": glu,
            "unit": "mg/dL",
            "reference_range": "70-99",
            "is_abnormal": glu > 99,
        })

    if "Hyperlipidemia" in chronic_set:
        ldl = rng.randint(95, 180)
        labs.append({
            "name": "LDL",
            "value": ldl,
            "unit": "mg/dL",
            "reference_range": "<100",
            "is_abnormal": ldl >= 100,
        })

    if "CKD Stage 3" in chronic_set:
        cr = round(rng.uniform(1.4, 2.2), 2)
        labs.append({
            "name": "Creatinine",
            "value": cr,
            "unit": "mg/dL",
            "reference_range": "0.7-1.3",
            "is_abnormal": True,
        })

    if "Hypothyroidism" in chronic_set:
        tsh = round(rng.uniform(2.8, 7.5), 2)
        labs.append({
            "name": "TSH",
            "value": tsh,
            "unit": "uIU/mL",
            "reference_range": "0.4-4.5",
            "is_abnormal": tsh > 4.5,
        })

    if "Gout" in chronic_set:
        uric = round(rng.uniform(6.5, 11.0), 1)
        labs.append({
            "name": "Uric Acid",
            "value": uric,
            "unit": "mg/dL",
            "reference_range": "<7.0",
            "is_abnormal": uric > 7.0,
        })

    if "Asthma" in chronic_set or "COPD" in chronic_set:
        # generic CBC
        wbc = round(rng.uniform(5.0, 13.0), 1)
        labs.append({
            "name": "WBC",
            "value": wbc,
            "unit": "10^3/uL",
            "reference_range": "4.0-10.0",
            "is_abnormal": wbc > 10.0,
        })

    # 健康人 / 沒 chronic 也偶爾有 CBC
    if not labs and rng.random() < 0.4:
        wbc = round(rng.uniform(5.0, 9.5), 1)
        labs.append({
            "name": "WBC",
            "value": wbc,
            "unit": "10^3/uL",
            "reference_range": "4.0-10.0",
            "is_abnormal": False,
        })
        hgb = round(rng.uniform(12.0, 15.5), 1)
        labs.append({
            "name": "Hemoglobin",
            "value": hgb,
            "unit": "g/dL",
            "reference_range": "12.0-16.0",
            "is_abnormal": False,
        })

    return labs


# ─────────────────────────────────────────────────────────
# Free-text findings (xray / ecg) -- 少數 visit 才生
# ─────────────────────────────────────────────────────────

XRAY_FINDINGS_POOL = [
    "Bilateral lung fields clear. No consolidation.",
    "右下肺輕度 infiltrate, suggest follow-up.",
    "Mild cardiomegaly noted. CT ratio ~0.52.",
    "雙肺紋理增加, no acute findings.",
    "Normal chest X-ray.",
]

ECG_FINDINGS_POOL = [
    "NSR, rate 78, no acute ST changes.",
    "Atrial fibrillation, controlled rate ~92.",
    "Sinus tachycardia, rate 105.",
    "NSR with LVH pattern.",
    "ECG within normal limits.",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    env = os.environ.get("ENVIRONMENT", "").lower()
    if env != "dev":
        log.error("ENVIRONMENT=dev required")
        return 1

    rng = random.Random(SEED)
    db: Session = SessionLocal()
    try:
        # 第一間 clinic + owner
        clinic = db.scalars(select(Clinic).order_by(Clinic.created_at).limit(1)).first()
        if not clinic:
            log.error("沒 clinic, 先跑 scripts/seed")
            return 1

        owner = db.scalars(
            select(User).order_by(User.created_at).limit(1)
        ).first()
        if not owner:
            log.error("沒 user")
            return 1

        # idempotent: 先刪 extended_mock 的 visit + examination
        if not args.dry_run:
            n_exam = db.execute(
                delete(VisitExamination).where(
                    VisitExamination.clinic_id == clinic.id,
                    VisitExamination.source == SOURCE_TAG,
                )
            ).rowcount
            n_visit = db.execute(
                delete(Visit).where(
                    Visit.clinic_id == clinic.id,
                    Visit.source == SOURCE_TAG,
                )
            ).rowcount
            log.info("先刪舊 extended: %d visits + %d examinations", n_visit, n_exam)

        # 拿所有 patient + 對應 chronic
        patients = db.scalars(
            select(Patient).where(
                Patient.clinic_id == clinic.id,
                Patient.is_demo_data.is_(True),
            )
        ).all()
        log.info("處理 %d patient", len(patients))

        chronics_by_pid: dict[UUID, set[str]] = {}
        for prob in db.scalars(
            select(PatientProblem).where(PatientProblem.clinic_id == clinic.id)
        ).all():
            chronics_by_pid.setdefault(prob.patient_id, set()).add(prob.problem_name)

        now = datetime(2026, 6, 27, tzinfo=timezone.utc)
        n_visit_added = 0
        n_exam_added = 0

        for p in patients:
            chronic_set = chronics_by_pid.get(p.id, set())
            # 計算年齡
            if p.date_of_birth:
                age = now.year - p.date_of_birth.year
            else:
                age = 50

            # visit 數 weighted by chronic count
            if len(chronic_set) >= 2:
                n_visits = rng.choice([2, 3, 3])
            elif len(chronic_set) == 1:
                n_visits = rng.choice([1, 2, 3])
            else:
                n_visits = rng.choice([1, 1, 2])

            # 生 visits (時間從舊到新分散在過去 1-18 個月)
            time_slots = sorted(
                rng.sample(range(1, 540), n_visits),  # 540 天 ≈ 18 個月
                reverse=True,  # 最舊在前
            )

            for slot_days in time_slots:
                visit_date = now - timedelta(days=slot_days)

                # chief_complaint + diagnosis
                if chronic_set:
                    pick_chronic = rng.choice(list(chronic_set))
                    cc = rng.choice(COMPLAINT_BY_CHRONIC.get(pick_chronic, GENERIC_COMPLAINTS))
                    dx = rng.choice(DIAGNOSIS_BY_CHRONIC.get(pick_chronic, GENERIC_DIAGNOSES))
                else:
                    cc = rng.choice(GENERIC_COMPLAINTS)
                    dx = rng.choice(GENERIC_DIAGNOSES)

                visit_uuid = uuid4()
                visit = Visit(
                    id=visit_uuid,
                    clinic_id=clinic.id,
                    patient_id=p.id,
                    doctor_user_id=owner.id,
                    visit_date=visit_date,
                    chief_complaint=cc,
                    diagnosis=dx,
                    status="completed",
                    source=SOURCE_TAG,
                    is_demo_data=True,
                )
                db.add(visit)
                n_visit_added += 1

                # examination
                vital = gen_vital_signs(chronic_set, age, rng)
                labs = gen_lab_results(chronic_set, rng)
                xray = rng.choice(XRAY_FINDINGS_POOL) if rng.random() < 0.15 else None
                ecg = rng.choice(ECG_FINDINGS_POOL) if "Atrial Fibrillation" in chronic_set or rng.random() < 0.08 else None

                exam = VisitExamination(
                    id=uuid4(),
                    clinic_id=clinic.id,
                    visit_id=visit_uuid,
                    patient_id=p.id,
                    vital_signs_json=vital,
                    lab_results_json=labs if labs else None,
                    xray_findings=xray,
                    ecg_findings=ecg,
                    free_notes=None,
                    source=SOURCE_TAG,
                    is_demo_data=True,
                )
                db.add(exam)
                n_exam_added += 1

        # 順手補 jimmy 5 個既有 visit 的 examination (它們的 source='mock' 不在我刪除範圍)
        # 這樣 demo 點 jimmy 病人也看得到 vital signs
        jimmy_visits_no_exam = db.scalars(
            select(Visit)
            .outerjoin(
                VisitExamination,
                VisitExamination.visit_id == Visit.id,
            )
            .where(
                Visit.clinic_id == clinic.id,
                Visit.source == "mock",
                VisitExamination.id.is_(None),
            )
        ).all()
        n_jimmy_exam = 0
        for v in jimmy_visits_no_exam:
            chronic_set = chronics_by_pid.get(v.patient_id, set())
            p = db.get(Patient, v.patient_id)
            age = (now.year - p.date_of_birth.year) if (p and p.date_of_birth) else 50
            vital = gen_vital_signs(chronic_set, age, rng)
            labs = gen_lab_results(chronic_set, rng)
            exam = VisitExamination(
                id=uuid4(),
                clinic_id=clinic.id,
                visit_id=v.id,
                patient_id=v.patient_id,
                vital_signs_json=vital,
                lab_results_json=labs if labs else None,
                xray_findings=None,
                ecg_findings=None,
                free_notes=None,
                source=SOURCE_TAG,
                is_demo_data=True,
            )
            db.add(exam)
            n_jimmy_exam += 1
            n_exam_added += 1

        if args.dry_run:
            db.rollback()
            log.info("[DRY RUN] 不寫 DB, 預計 +%d visits +%d examinations (jimmy 補 +%d)",
                     n_visit_added, n_exam_added, n_jimmy_exam)
        else:
            db.commit()
            log.info("=" * 60)
            log.info("Extend visits + examinations 完成")
            log.info("  visits             + %d", n_visit_added)
            log.info("  visit_examinations + %d (其中 jimmy 補 %d)", n_exam_added, n_jimmy_exam)
            log.info("=" * 60)
        return 0
    except Exception:
        db.rollback()
        log.exception("extend_visits 失敗, rollback")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
