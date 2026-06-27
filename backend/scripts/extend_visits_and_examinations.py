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

# CC ↔ Dx 必須配對 (司機醫師糾正: 流鼻水→急性腸胃炎這種亂配不可)
# 結構: list[tuple(chief_complaint, diagnosis)]

CHRONIC_CASES: dict[str, list[tuple[str, str]]] = {
    "Hypertension": [
        ("頭痛 2 天", "原發性高血壓 (未達標)"),
        ("後腦痛 早上明顯 1 週", "原發性高血壓 (控制不佳)"),
        ("自測 BP 偏高 1 週", "原發性高血壓 (控制中)"),
        ("頭暈 3 天 起身明顯", "原發性高血壓 (姿勢性低血壓需排除)"),
        ("頸部僵硬 + 頭痛 1 週", "原發性高血壓 (緊張型頭痛合併)"),
    ],
    "Type 2 Diabetes": [
        ("口渴 頻尿 加重 2 週", "第二型糖尿病 (HbA1c 偏高)"),
        ("腳麻 1 個月", "第二型糖尿病 + 周邊神經病變"),
        ("視力模糊 1 個月", "第二型糖尿病 (需轉介眼科檢視網膜)"),
        ("傷口不癒合 2 週", "第二型糖尿病 (血糖控制不佳 + 傷口感染)"),
        ("疲倦 3 週 + 夜尿增加", "第二型糖尿病 (血糖控制不佳)"),
    ],
    "Hyperlipidemia": [
        ("健檢 LDL 偏高 (家屬建議來)", "高血脂症 (新診)"),
        ("胸悶 偶發 1 週", "高血脂症 (Statin 治療中, 排除心因性)"),
    ],
    "Asthma": [
        ("夜咳 1 週", "氣喘 (夜間發作型)"),
        ("喘 2 天 加重", "氣喘 急性發作"),
        ("氣短 爬樓梯時 3 天", "氣喘 (穩定追蹤、運動誘發)"),
        ("胸悶 一週", "氣喘 (穩定追蹤)"),
    ],
    "COPD": [
        ("喘 加重 1 週", "COPD 急性惡化 (mild)"),
        ("咳嗽 帶痰 黃綠 2 週", "COPD 急性惡化 (細菌感染合併)"),
        ("夜間呼吸困難 3 天", "COPD (穩定、需評估 SpO2)"),
    ],
    "Osteoarthritis": [
        ("膝痛 加重 1 週", "膝部骨關節炎 (急性發作)"),
        ("上下樓梯腳痛 5 天", "膝部骨關節炎"),
        ("關節僵硬 早上明顯", "膝部骨關節炎 (晨僵)"),
    ],
    "Atrial Fibrillation": [
        ("心悸 3 天", "心房顫動 (rate-controlled, 抗凝血藥追蹤)"),
        ("胸悶 偶發 1 週", "心房顫動 (新發、需排除心衰)"),
        ("頭暈 1 週 + 疲倦", "心房顫動 (rate 控制不佳)"),
    ],
    "CKD Stage 3": [
        ("下肢水腫 3 天", "慢性腎臟病第三期 (水腫加重)"),
        ("尿量減少 1 週", "慢性腎臟病第三期 (脫水可能)"),
        ("疲倦 3 週 + 夜尿增加", "慢性腎臟病第三期 (穩定追蹤)"),
    ],
    "Hypothyroidism": [
        ("疲倦 1 個月", "甲狀腺機能低下 (TSH 偏高、需調藥)"),
        ("怕冷 3 週 + 體重增加", "甲狀腺機能低下 (劑量不足)"),
        ("便秘 2 週", "甲狀腺機能低下 (合併症)"),
    ],
    "Anxiety Disorder": [
        ("失眠 1 週", "廣泛性焦慮症 (合併失眠)"),
        ("心悸 加重 3 天", "廣泛性焦慮症 (排除心因性後)"),
        ("胸悶 焦慮時", "廣泛性焦慮症 (恐慌發作合併)"),
    ],
    "Migraine": [
        ("偏頭痛 3 天 反覆", "偏頭痛 (無先兆、急性發作)"),
        ("頭痛 + 怕光怕吵 2 天", "偏頭痛 (典型發作)"),
        ("頭痛 + 嘔吐 1 天", "偏頭痛 (急性、需排除其他)"),
    ],
    "GERD": [
        ("胃酸逆流 1 週", "胃食道逆流 (持續性)"),
        ("胸悶 餐後加重", "胃食道逆流 (典型症狀)"),
        ("咳嗽 餐後 5 天", "胃食道逆流 (LPR 喉咽逆流)"),
    ],
    "BPH": [
        ("夜尿 4-5 次/晚", "攝護腺肥大 (LUTS 加重)"),
        ("排尿困難 1 個月", "攝護腺肥大 (尿流不暢)"),
        ("尿流變細 2 週", "攝護腺肥大 (進展中)"),
    ],
    "Heart Failure": [
        ("喘 加重 3 天", "鬱血性心衰竭 (NYHA III, 急性惡化)"),
        ("下肢水腫 1 週", "鬱血性心衰竭 (水腫加重)"),
        ("夜間平躺呼吸困難 5 天", "鬱血性心衰竭 (端坐呼吸)"),
    ],
    "Dementia": [
        ("健忘加重 1 月 (家屬陳述)", "輕度認知障礙 (MCI 進展)"),
        ("走錯路 1 次", "輕度認知障礙 (定向感下降)"),
        ("情緒易怒 2 週", "輕度認知障礙 (行為症狀)"),
    ],
    "Depression": [
        ("情緒低落 1 個月", "重度憂鬱症 (中度)"),
        ("失眠 2 週 + 食慾減退", "重度憂鬱症 (典型症狀)"),
        ("對事物失去興趣", "重度憂鬱症 (Anhedonia)"),
    ],
    "Gout": [
        ("腳趾痛 急性 1 天 紅腫熱", "痛風 急性發作 (典型蹠趾關節)"),
        ("膝紅腫熱痛 2 天", "痛風 急性發作 (非典型膝關節)"),
        ("腳踝腫痛 半夜醒", "痛風 急性發作"),
    ],
    "Osteoporosis": [
        ("腰背痛 加重 2 週", "骨質疏鬆症 (壓迫性骨折需排除)"),
        ("輕微跌倒後痛 3 天", "骨質疏鬆症 (跌倒後評估)"),
    ],
}

# 健康 / 急性問題 pool (CC + 對應 Dx 配對)
GENERIC_CASES: list[tuple[str, str]] = [
    # 呼吸道
    ("咳嗽 3 天", "急性上呼吸道感染"),
    ("咳嗽 帶白痰 5 天", "急性支氣管炎"),
    ("夜咳 1 週", "感染後咳嗽 (Post-infectious cough)"),
    ("流鼻水 5 天", "急性鼻咽炎"),
    ("鼻塞 + 流鼻水 3 天", "過敏性鼻炎"),
    ("喉嚨痛 2 天", "急性扁桃腺炎"),
    ("聲音沙啞 4 天", "急性咽喉炎"),
    ("發燒 + 喉嚨痛 2 天", "急性扁桃腺炎"),
    ("輕度發燒 38.2 一天", "病毒性發燒症候群"),
    # 腸胃
    ("拉肚子 4 次/日 持續 2 天", "急性腸胃炎"),
    ("嘔吐 3 次 半天 + 腹痛", "病毒性腸胃炎"),
    ("腹痛 + 拉肚子 1 天", "急性腸胃炎 (food poisoning 疑似)"),
    ("胃悶 餐後不適 1 週", "胃食道逆流 (新診)"),
    # 皮膚
    ("皮膚紅疹 2 天", "接觸性皮膚炎"),
    ("搔癢 + 紅疹 1 週", "蕁麻疹"),
    ("蕁麻疹 反覆 1 週", "慢性蕁麻疹 (待查過敏原)"),
    # 神經 / 肌肉骨骼
    ("頭痛 2 天", "緊張型頭痛"),
    ("頭暈 3 天", "前庭功能失調 (BPPV 需排除)"),
    ("偏頭痛 1 天", "偏頭痛 (急性發作)"),
    ("腰痛 3 天 搬重物後", "急性下背痛 (肌肉拉傷)"),
    ("膝痛 + 腫脹 2 天", "膝關節扭傷"),
    ("肩頸僵硬 1 週", "頸椎症候群 / 緊張型頭痛"),
    # 五官
    ("耳痛 2 天", "急性外耳炎"),
    ("眼睛紅 + 分泌物 3 天", "急性結膜炎"),
    # 其他
    ("失眠 1 週", "失眠症 (壓力相關)"),
    ("疲倦 2 週", "慢性疲倦 (待查、需 CBC + TSH)"),
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

                # chief_complaint + diagnosis (tuple pair, 保證對得上)
                # chronic patient: 70% 看 chronic 相關、30% 也來看急性問題 (高血壓也會感冒)
                if chronic_set and rng.random() < 0.7:
                    pick_chronic = rng.choice(list(chronic_set))
                    cases = CHRONIC_CASES.get(pick_chronic, GENERIC_CASES)
                    cc, dx = rng.choice(cases)
                else:
                    cc, dx = rng.choice(GENERIC_CASES)

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
