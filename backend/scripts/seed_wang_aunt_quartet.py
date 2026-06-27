"""
============================================================
scripts/seed_wang_aunt_quartet.py -- v0.3.1 §9 四幕劇 dataset
============================================================
Track 1 MemoryAgent 主秀 demo dataset:

王慧明 (王阿姨) / 68 F / TEST-W007, 4 次就診跨 9 個月:

  幕 1 (2025-09-20): 首診頭暈 BP 158/95, dx 原發性高血壓 stage 2
                     Rx amlodipine 5mg + 4 週追蹤
  幕 2 (2025-10-15): 4 週追蹤 BP 148/88, 繼續 amlodipine
  幕 3 (2026-02-15): 慢性追蹤 BP 148/86, 主訴頭痛 + 偶爾忘事 (anomaly to_observe),
                     開 ibuprofen 400mg PRN
                     ⚠ AI audit 警告: NSAID + amlodipine 4-8 週後可能拮抗
  幕 4 (2026-06-26): BP 158/94 (拮抗顯現), 健忘加重 + 跌倒一次,
                     "忘事" 升 confirmed (Phase 5 自動升級),
                     停 ibuprofen 改 acetaminophen + referral 神內

每個 visit 經過完整 backend pipeline:
- create Visit + VisitExamination + AiDraft
- take_heart_layer_snapshot(before_visit)
- evolve_heart_layer_after_visit (Phase 5 自動 4 通路演進)
- take_heart_layer_snapshot(after_visit)

跑完後 demo flow:
  打開王阿姨 detail -> 看心臟層 (1 confirmed flag 健忘 + 1 problem 高血壓 + 1 long-term med amlodipine + 多筆 BP/HR baseline trend)
  點幕 3 (2/15) 「🅱️ Mode B 事後諸葛」-> AI 看到後續 NSAID 拮抗發展, 提示「當時開 ibuprofen 後續 4 個月 BP 升回, 教育意義」
  點幕 4 (6/26) 「🅰️ Mode A 當時可獲得」-> AI 看到 to_observe 升 confirmed, 鑑別認知症狀

用法:
    cd backend && .venv/Scripts/python -m scripts.seed_wang_aunt_quartet

idempotent: 重跑會先刪 TEST-W007 + 該病人所有相關資料 (DemoDataMixin is_demo_data=True 過濾)
============================================================
"""

from __future__ import annotations

import logging
import sys
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import (
    AiDraft,
    Clinic,
    Drug,
    HeartLayerSnapshot,
    Patient,
    PatientBaseline,
    PatientFlag,
    PatientMedication,
    PatientProblem,
    Prescription,
    PrescriptionItem,
    SOURCE_MOCK,
    User,
    Visit,
    VisitExamination,
)
from app.services.heart_evolution import (
    evolve_heart_layer_after_visit,
    take_heart_layer_snapshot,
)

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


PATIENT_ID_NUMBER = "TEST-W007"
PATIENT_NAME = "王慧明 (王阿姨)"


# ============================================================
# 四幕劇 dataset
# ============================================================
# Rx 設計 (Norvasc=amlodipine, Brufen=ibuprofen, Panadol=acetaminophen)
# 格式: list of (drug_code, usage_text, daily_dose, days)
# total_quantity = daily_dose × days 由 helper 算
RX_ACT_1 = [("AMLODIPINE_5", "1# QD", 1, 30)]
RX_ACT_2 = [("AMLODIPINE_5", "1# QD (refill)", 1, 60)]
RX_ACT_3 = [
    ("AMLODIPINE_5", "1# QD", 1, 60),
    ("IBU_400",      "1# tid PRN (頭痛需要時)", 3, 14),
]
RX_ACT_4 = [
    ("AMLODIPINE_5", "1# QD", 1, 30),
    ("PARA_500",     "1# tid PRN (替代 ibuprofen)", 3, 14),
]


ACT_1 = {
    "name": "幕 1: 首診頭暈",
    "rx": RX_ACT_1,
    "visit_date": datetime(2025, 9, 20, 9, 30, tzinfo=timezone.utc),
    "chief_complaint": "最近常常頭暈, 已有 2 週",
    "hpi": "近 2 週反覆頭暈, 站立時為甚, 從沒測過 BP. 否認頭痛胸悶心悸",
    "physical_exam": "BP 158/95 sitting, HR 72 reg, 雙肺清, 心音正常, 神經學無 focal",
    "diagnosis": "原發性高血壓 stage 2 (新診斷)",
    "vital_signs": {
        "blood_pressure_systolic": 158,
        "blood_pressure_diastolic": 95,
        "heart_rate": 72,
        "temperature_c": 36.5,
        "respiratory_rate": 16,
    },
    "ai_drafts": {
        "intake": {
            "findings": [
                {"section": "main_complaint", "text": "頭暈 2 週, 站立加重"},
                {"section": "extra", "text": "從未測過 BP, 不知平常數值"},
                {"section": "suggested_question", "text": "問家族高血壓史 / 藥物使用 / 睡眠"},
            ],
            "summary": "頭暈為主, 首次發現 BP 升高",
            "model_used": "qwen3.7-max",
            "input_tokens": 380, "output_tokens": 120,
        },
        "triage": {
            "has_conflict": False,
            "conflict_summary": "",
            "differentials": [
                {"diagnosis": "原發性高血壓", "reasoning": "BP 158/95 stage 2 + 老年 + 無誘因, 首選"},
                {"diagnosis": "次發性高血壓 (排除診斷)", "reasoning": "腎/內分泌等次發因建議首診血常 + 尿常 + Cr 排除"},
            ],
            "closing_note": "首診標準流程, 排除次發後標 controlled trend",
            "model_used": "qwen3.7-max",
            "input_tokens": 400, "output_tokens": 200,
        },
        "audit": {
            "rule_engine_findings": [],
            "contextual_risks": [
                {
                    "drug": "amlodipine",
                    "risk": "老年單藥首選 CCB, 注意踝部水腫 / 反射性心悸",
                    "triggered_by": "新診斷高血壓 + 老年",
                    "needs_confirmation": False,
                }
            ],
            "unknowns": [],
            "closing_note": "amlodipine 5mg QD 起始劑量適合",
            "model_used": "qwen3.7-max",
            "input_tokens": 320, "output_tokens": 150,
        },
        "education": {
            "advice": (
                "1. 自測 BP 早晚各 1 次, 紀錄在本子上\n"
                "2. 4 週後回診評估 + 帶 BP 紀錄\n"
                "3. 減鹽 (每日 < 5g) / 規律運動 / 戒菸限酒\n"
                "4. 若出現胸痛 / 視力模糊 / 嚴重頭痛立即就醫"
            ),
            "reasoning": "新診斷高血壓首要建立 home BP monitoring 習慣",
            "closing_note": "請帶 BP 紀錄回診",
            "model_used": "qwen3.7-max",
            "input_tokens": 250, "output_tokens": 280,
        },
    },
}

ACT_2 = {
    "name": "幕 2: 4 週追蹤",
    "rx": RX_ACT_2,
    "visit_date": datetime(2025, 10, 15, 9, 30, tzinfo=timezone.utc),
    "chief_complaint": "頭暈減少, 自測 BP 平均 145/90",
    "hpi": "服 amlodipine 5mg QD 共 4 週, 自測 BP 早晚平均 145/90, 頭暈頻率明顯減少",
    "physical_exam": "BP 148/88 sitting, HR 75 reg, 無踝部水腫, 神清",
    "diagnosis": "原發性高血壓 (追蹤中, controlled trending)",
    "vital_signs": {
        "blood_pressure_systolic": 148,
        "blood_pressure_diastolic": 88,
        "heart_rate": 75,
        "temperature_c": 36.5,
        "respiratory_rate": 16,
    },
    "ai_drafts": {
        "intake": {
            "findings": [
                {"section": "main_complaint", "text": "頭暈頻率減少, 自測 BP 改善"},
                {"section": "extra", "text": "服藥 4 週順從性佳, 無副作用"},
            ],
            "summary": "amlodipine 追蹤反應良好",
            "model_used": "qwen3.7-max",
            "input_tokens": 320, "output_tokens": 100,
        },
        "triage": {
            "has_conflict": False,
            "conflict_summary": "",
            "differentials": [
                {"diagnosis": "原發性高血壓 (controlled trending)",
                 "reasoning": "BP 從 158/95 降至 148/88, 改善方向正確, 繼續單藥觀察"},
            ],
            "closing_note": "未達目標 < 140/90, 但趨勢正確, 暫不加藥",
            "model_used": "qwen3.7-max",
            "input_tokens": 350, "output_tokens": 150,
        },
        "audit": {
            "rule_engine_findings": [],
            "contextual_risks": [
                {
                    "drug": "amlodipine",
                    "risk": "繼續監測踝部水腫 / 牙齦增生",
                    "triggered_by": "持續 CCB 用藥",
                    "needs_confirmation": False,
                }
            ],
            "unknowns": [],
            "closing_note": "繼續 amlodipine 5mg QD",
            "model_used": "qwen3.7-max",
            "input_tokens": 280, "output_tokens": 100,
        },
        "education": {
            "advice": (
                "1. 繼續自測 BP + 紀錄\n"
                "2. 2 個月後追蹤\n"
                "3. 生活方式持續 (減鹽 + 運動)\n"
                "4. 即將進入冬季, BP 通常會微升, 注意保暖"
            ),
            "reasoning": "穩定追蹤期, 強化 lifestyle",
            "closing_note": "2 個月追蹤",
            "model_used": "qwen3.7-max",
            "input_tokens": 220, "output_tokens": 200,
        },
    },
}

ACT_3 = {
    "name": "幕 3: 慢性追蹤 + 開 ibuprofen",
    "rx": RX_ACT_3,
    "visit_date": datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
    "chief_complaint": "BP 還算穩, 但最近常頭痛 + 偶爾忘事",
    "hpi": (
        "近 1 個月頭痛頻繁 (約每週 3 次, 緊張型分布). 自測 BP 平均 148/88. "
        "家人提及偶爾忘東西 (e.g. 鑰匙位置), 但日常自理仍正常"
    ),
    "physical_exam": "BP 148/86 sitting, HR 78, 簡測 orientation OK, recall 3/3, 神經學 grossly normal",
    "diagnosis": "原發性高血壓 + 緊張性頭痛, 認知症狀待觀察 (open)",
    "vital_signs": {
        "blood_pressure_systolic": 148,
        "blood_pressure_diastolic": 86,
        "heart_rate": 78,
        "temperature_c": 36.7,
        "respiratory_rate": 17,
    },
    "ai_drafts": {
        "intake": {
            "findings": [
                {"section": "main_complaint", "text": "頭痛頻繁約每週 3 次, 緊張型"},
                {"section": "anomaly", "text": "偶爾忘東西"},
                {"section": "extra", "text": "BP 自測 148/88 已 4 個月穩定. 家人提及忘東西症狀"},
                {"section": "suggested_question", "text": "頭痛是否有誘因 / 視覺先兆 / 影響工作"},
            ],
            "summary": "頭痛 + 認知症狀新出現, 建議 MMSE + 頭痛日記",
            "model_used": "qwen3.7-max",
            "input_tokens": 480, "output_tokens": 180,
        },
        "triage": {
            "has_conflict": False,
            "conflict_summary": "",
            "differentials": [
                {"diagnosis": "緊張性頭痛", "reasoning": "頻率 + 分布符合, 高血壓控制中可能仍因壓力觸發"},
                {"diagnosis": "高血壓相關頭痛", "reasoning": "BP 148/86 未達標 < 140/90, 不排除"},
                {"diagnosis": "認知症狀: 鑑別正常老化 vs 早期 MCI",
                 "reasoning": "建議 MMSE / MoCA + 家屬詳問日常功能"},
            ],
            "closing_note": "頭痛 + 認知雙主訴, 短期 NSAID 控制頭痛 + 並行認知評估",
            "model_used": "qwen3.7-max",
            "input_tokens": 500, "output_tokens": 250,
        },
        "audit": {
            "rule_engine_findings": [
                {
                    "drug_a": "ibuprofen",
                    "drug_b": "amlodipine",
                    "severity": "moderate",
                    "description": (
                        "NSAID 長期使用 (4-8 週以上) 會減弱降壓藥 (含 CCB) 效果, "
                        "建議盡量短期 / 監測 BP / 老年腎功能風險"
                    ),
                    "source": "pharmacology + clinical pharmacology textbook",
                    "needs_confirmation": False,
                }
            ],
            "contextual_risks": [
                {
                    "drug": "ibuprofen",
                    "risk": "老年腎風險 + 胃黏膜傷害, 建議短期 < 7 天 + PPI 同用",
                    "triggered_by": "老年 + 已有 amlodipine 長期 + 無胃藥保護",
                    "needs_confirmation": False,
                },
                {
                    "drug": "acetaminophen",
                    "risk": "可考慮 acetaminophen 1g TID 替代 (對 BP / 腎較安全)",
                    "triggered_by": "NSAID 替代方案",
                    "needs_confirmation": False,
                },
            ],
            "unknowns": [],
            "closing_note": "醫師可評估後仍開 ibuprofen, 但建議標 < 7 天 + 監測 BP + 衛教 acetaminophen 替代",
            "model_used": "qwen3.7-max",
            "input_tokens": 550, "output_tokens": 300,
        },
        "education": {
            "advice": (
                "1. ibuprofen 400mg 只在頭痛時用, 不超過 7 天\n"
                "2. 自測 BP 增加頻率 (每日 2 次, 觀察 NSAID 影響)\n"
                "3. 認知症狀請家屬一起紀錄 (忘事頻率 / 場合 / 影響)\n"
                "4. 2 個月後回診評估 (帶 BP + 認知紀錄)\n"
                "5. 若頭痛持續或加重請提早回診"
            ),
            "reasoning": "NSAID 短期搭配 + 認知症狀 baseline 紀錄, 為下次評估準備",
            "closing_note": "2 個月追蹤 + 帶紀錄",
            "model_used": "qwen3.7-max",
            "input_tokens": 320, "output_tokens": 320,
        },
    },
}

ACT_4 = {
    "name": "幕 4: NSAID 拮抗顯現 + 認知症狀升 confirmed",
    "rx": RX_ACT_4,
    "visit_date": datetime(2026, 6, 26, 10, 0, tzinfo=timezone.utc),
    "chief_complaint": "最近頭暈又開始了 + 健忘越來越明顯 + 上週差點跌倒",
    "hpi": (
        "近 1 個月 BP 自測升至 155-160, 頭暈頻繁類似首診. 健忘明顯加重 "
        "(忘記吃藥 / 重複問同樣問題), 上週爬樓梯時差點跌倒但及時扶住. "
        "持續服 amlodipine 5mg QD + ibuprofen 400mg PRN (近 4 個月幾乎天天用)"
    ),
    "physical_exam": (
        "BP 158/94 sitting, 立位 152/88 (no orthostatic drop), HR 80 reg, "
        "MMSE 25/30 (recall 1/3, calculation 2 errors), 神經學無 focal deficit"
    ),
    "diagnosis": "BP 控制不良 (疑 NSAID 拮抗) + 認知功能下降 (MMSE 下降) + 跌倒高風險",
    "vital_signs": {
        "blood_pressure_systolic": 158,
        "blood_pressure_diastolic": 94,
        "heart_rate": 80,
        "temperature_c": 36.6,
        "respiratory_rate": 17,
        "oxygen_saturation": 97,
    },
    "ai_drafts": {
        "intake": {
            "findings": [
                {"section": "main_complaint", "text": "頭暈再起 + BP 自測 155-160"},
                {"section": "anomaly", "text": "偶爾忘東西明顯加重, 上週爬樓梯時差點跌倒"},
                {"section": "extra", "text": "ibuprofen 近 4 個月幾乎天天用 (超出原本 PRN 指示)"},
                {"section": "suggested_question", "text": "確認 ibuprofen 實際使用頻率 / 跌倒詳情"},
            ],
            "summary": "BP 失控 + 認知症狀升級 + NSAID 過度使用三重變化",
            "model_used": "qwen3.7-max",
            "input_tokens": 620, "output_tokens": 220,
        },
        "triage": {
            "has_conflict": True,
            "conflict_summary": "認知症狀升級 (MMSE 25/30) + 跌倒 + BP 控制不良三項同時出現, 必須鑑別腦血管事件",
            "differentials": [
                {"diagnosis": "高血壓控制不良 (NSAID 拮抗)",
                 "reasoning": "近 4 個月 ibuprofen 天天用, BP 從 148/86 升回 158/94 符合 NSAID 4-8 週拮抗時程"},
                {"diagnosis": "腦小血管病變 / 早期失智",
                 "reasoning": "MMSE 從正常降到 25, recall 1/3, 配合長期高血壓控制不良, 需要 brain MRI"},
                {"diagnosis": "TIA (排除診斷)",
                 "reasoning": "雖然此刻無 focal deficit, 但跌倒事件 + 認知變化, 建議 brain MRI + 神內 referral"},
                {"diagnosis": "直立性低血壓",
                 "reasoning": "立位無明顯 drop, 暫不支持, 但仍需衛教預防"},
            ],
            "closing_note": "建議 brain MRI + 神內 referral + 老醫 referral (跌倒風險評估)",
            "model_used": "qwen3.7-max",
            "input_tokens": 700, "output_tokens": 350,
        },
        "audit": {
            "rule_engine_findings": [
                {
                    "drug_a": "ibuprofen",
                    "drug_b": "amlodipine",
                    "severity": "moderate",
                    "description": (
                        "NSAID 長期 (近 4 個月) 拮抗 CCB 效果已實際顯現, "
                        "BP 從 148/86 升回 158/94, 強烈建議停用 ibuprofen"
                    ),
                    "source": "pharmacology",
                    "needs_confirmation": False,
                }
            ],
            "contextual_risks": [
                {
                    "drug": "acetaminophen",
                    "risk": "建議 acetaminophen 1g TID 取代 ibuprofen (對 BP / 腎較安全)",
                    "triggered_by": "停 NSAID 替代",
                    "needs_confirmation": False,
                },
                {
                    "drug": "amlodipine",
                    "risk": "停 NSAID 後 4 週 BP 仍 > 140/90 則考慮加 ARB / ACE-I 第二線",
                    "triggered_by": "BP 失控 + 認知保護需求",
                    "needs_confirmation": True,
                },
            ],
            "unknowns": [],
            "closing_note": "1. 停 ibuprofen 改 acetaminophen. 2. 監測 BP 4 週. 3. 神內 + 老醫 referral",
            "model_used": "qwen3.7-max",
            "input_tokens": 650, "output_tokens": 350,
        },
        "education": {
            "advice": (
                "1. 立即停 ibuprofen, 改 acetaminophen 1g 每 8 小時最多 3 次/天\n"
                "2. 跌倒預防: 浴室防滑墊 / 床邊夜燈 / 起身慢 (坐 30 秒再站)\n"
                "3. 認知症狀就醫指標: 走失 / 不認得家人 / 自理困難 / 個性改變\n"
                "4. 神內就診請帶藥單 + BP 紀錄 + 家屬陪同 (家屬補充病史關鍵)\n"
                "5. 4 週後本院追蹤 BP 是否回降"
            ),
            "reasoning": "停 NSAID 為首要 actionable 變化, 認知症狀需要專科 + 家屬參與",
            "closing_note": "4 週追蹤 BP + 等神內報告",
            "model_used": "qwen3.7-max",
            "input_tokens": 400, "output_tokens": 380,
        },
    },
}

ACTS = [ACT_1, ACT_2, ACT_3, ACT_4]


# ============================================================
# Helpers
# ============================================================
def cleanup_existing(db: Session, clinic_id: uuid.UUID) -> None:
    """idempotent: 砍掉既有 TEST-W007 + 相關資料."""
    p = db.scalars(
        select(Patient).where(
            Patient.clinic_id == clinic_id,
            Patient.id_number == PATIENT_ID_NUMBER,
        )
    ).first()
    if not p:
        return
    pid = p.id
    logger.info("既有 TEST-W007 (id=%s), 清掉 4 心臟表 + visits + snapshots", pid)

    visit_ids = [
        v.id for v in db.scalars(select(Visit).where(Visit.patient_id == pid)).all()
    ]
    if visit_ids:
        rx_ids = [
            r.id for r in db.scalars(select(Prescription).where(Prescription.visit_id.in_(visit_ids))).all()
        ]
        if rx_ids:
            db.execute(delete(PrescriptionItem).where(PrescriptionItem.prescription_id.in_(rx_ids)))
            db.execute(delete(Prescription).where(Prescription.id.in_(rx_ids)))
        db.execute(delete(HeartLayerSnapshot).where(HeartLayerSnapshot.visit_id.in_(visit_ids)))
        db.execute(delete(AiDraft).where(AiDraft.visit_id.in_(visit_ids)))
        db.execute(delete(VisitExamination).where(VisitExamination.visit_id.in_(visit_ids)))
        db.execute(delete(Visit).where(Visit.id.in_(visit_ids)))
    db.execute(delete(PatientBaseline).where(PatientBaseline.patient_id == pid))
    db.execute(delete(PatientFlag).where(PatientFlag.patient_id == pid))
    db.execute(delete(PatientMedication).where(PatientMedication.patient_id == pid))
    db.execute(delete(PatientProblem).where(PatientProblem.patient_id == pid))
    db.execute(delete(Patient).where(Patient.id == pid))
    db.flush()


def create_patient(db: Session, clinic_id: uuid.UUID) -> Patient:
    p = Patient(
        id=uuid.uuid4(),
        clinic_id=clinic_id,
        name=PATIENT_NAME,
        gender="F",
        date_of_birth=date(1957, 4, 12),  # 2025 年 68 歲
        phone="6000-W007",
        id_number=PATIENT_ID_NUMBER,
        source=SOURCE_MOCK,
        is_demo_data=True,
    )
    db.add(p)
    db.flush()
    return p


def play_act(db: Session, clinic: Clinic, owner: User, patient: Patient, act: dict) -> dict:
    """演一幕: 建 Visit + Examination + AiDraft + 拍 snapshot + 跑 evolve."""
    logger.info("=== %s @ %s ===", act["name"], act["visit_date"].date().isoformat())

    visit = Visit(
        id=uuid.uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        doctor_user_id=owner.id,
        visit_date=act["visit_date"],
        chief_complaint=act["chief_complaint"],
        hpi=act["hpi"],
        physical_exam=act["physical_exam"],
        diagnosis=act["diagnosis"],
        status="completed",
        source=SOURCE_MOCK,
        is_demo_data=True,
    )
    db.add(visit)

    exam = VisitExamination(
        id=uuid.uuid4(),
        clinic_id=clinic.id,
        visit_id=visit.id,
        patient_id=patient.id,
        vital_signs_json=act["vital_signs"],
        lab_results_json=None,
        xray_findings=None,
        ecg_findings=None,
        free_notes=None,
        source=SOURCE_MOCK,
        is_demo_data=True,
    )
    db.add(exam)

    db.flush()
    # before_visit snapshot
    take_heart_layer_snapshot(db, visit, "before_visit")

    # 寫 4 ai_drafts
    for agent_type, payload in act["ai_drafts"].items():
        db.add(AiDraft(
            id=uuid.uuid4(),
            clinic_id=clinic.id,
            patient_id=patient.id,
            visit_id=visit.id,
            agent_type=agent_type,
            payload_json=payload,
            status="accepted_with_visit",
            accepted_at=act["visit_date"],
            source=SOURCE_MOCK,
            is_demo_data=True,
        ))

    # Phase 7: 寫 Prescription + PrescriptionItem (司機指出王阿姨四幕劇缺處方)
    rx_list = act.get("rx") or []
    if rx_list:
        rx = Prescription(
            id=uuid.uuid4(),
            clinic_id=clinic.id,
            visit_id=visit.id,
            status="dispensed",
            source=SOURCE_MOCK,
            is_demo_data=True,
        )
        db.add(rx)
        db.flush()
        for drug_code, usage_text, daily_dose, days in rx_list:
            drug = db.scalars(select(Drug).where(Drug.code == drug_code)).first()
            if not drug:
                logger.warning("  drug code %r not found in drugs table, skip", drug_code)
                continue
            total_qty = int(daily_dose * days)
            db.add(PrescriptionItem(
                id=uuid.uuid4(),
                clinic_id=clinic.id,
                prescription_id=rx.id,
                drug_id=drug.id,
                usage_text=usage_text,
                daily_dose=daily_dose,
                days=days,
                total_quantity=total_qty,
                unit_price_at_time=0,
                total_price=0,
                source=SOURCE_MOCK,
                is_demo_data=True,
            ))
        logger.info("  Rx: %d items", len(rx_list))

    db.flush()
    # 跑 Phase 5 evolve
    evolution = evolve_heart_layer_after_visit(db, visit)

    db.flush()
    # after_visit snapshot
    take_heart_layer_snapshot(db, visit, "after_visit")

    logger.info(
        "  evolve: problems+%d meds+%d flags+%d (升 confirmed %d) baselines+%d",
        evolution.problems_added,
        evolution.medications_added,
        evolution.flags_added,
        evolution.flags_upgraded,
        evolution.baselines_added,
    )

    return {
        "visit_id": str(visit.id),
        "evolve": {
            "problems_added": evolution.problems_added,
            "medications_added": evolution.medications_added,
            "flags_added": evolution.flags_added,
            "flags_upgraded": evolution.flags_upgraded,
            "baselines_added": evolution.baselines_added,
        },
    }


# ============================================================
# Main
# ============================================================
def main() -> int:
    db = SessionLocal()
    try:
        clinic = db.scalars(select(Clinic).order_by(Clinic.created_at).limit(1)).first()
        if not clinic:
            logger.error("無 clinic, 請先跑 scripts/seed")
            return 1
        owner = db.scalars(select(User).order_by(User.created_at).limit(1)).first()
        if not owner:
            logger.error("無 owner user")
            return 1

        logger.info("clinic: %s (%s)", clinic.name, clinic.id)
        logger.info("owner : %s", owner.email)

        cleanup_existing(db, clinic.id)
        patient = create_patient(db, clinic.id)
        logger.info("建立 patient: %s (%s)", patient.name, patient.id)

        results = [play_act(db, clinic, owner, patient, act) for act in ACTS]

        db.commit()
        logger.info("\n=== 四幕劇 dataset 完成 ===")
        for i, (act, r) in enumerate(zip(ACTS, results), 1):
            ev = r["evolve"]
            logger.info(
                "  幕 %d (%s): problems+%d meds+%d flags+%d (升 %d) baselines+%d",
                i, act["visit_date"].date().isoformat(),
                ev["problems_added"], ev["medications_added"],
                ev["flags_added"], ev["flags_upgraded"], ev["baselines_added"],
            )

        # 終態驗證
        from sqlalchemy import func
        n_visits = db.scalar(select(func.count(Visit.id)).where(Visit.patient_id == patient.id))
        n_snaps = db.scalar(
            select(func.count(HeartLayerSnapshot.id))
            .where(HeartLayerSnapshot.patient_id == patient.id)
        )
        n_problems = db.scalar(
            select(func.count(PatientProblem.id))
            .where(PatientProblem.patient_id == patient.id)
        )
        n_meds = db.scalar(
            select(func.count(PatientMedication.id))
            .where(PatientMedication.patient_id == patient.id)
        )
        n_flags = db.scalar(
            select(func.count(PatientFlag.id))
            .where(PatientFlag.patient_id == patient.id)
        )
        confirmed_flags = db.scalars(
            select(PatientFlag).where(
                PatientFlag.patient_id == patient.id,
                PatientFlag.confidence_status == "confirmed",
            )
        ).all()
        n_baselines = db.scalar(
            select(func.count(PatientBaseline.id))
            .where(PatientBaseline.patient_id == patient.id)
        )

        logger.info(
            "\n終態: visits=%d snapshots=%d (預期 8 = 4 visit x 2) "
            "problems=%d meds=%d flags=%d (confirmed %d) baselines=%d",
            n_visits, n_snaps, n_problems, n_meds, n_flags,
            len(confirmed_flags), n_baselines,
        )
        for f in confirmed_flags:
            logger.info("  confirmed flag: %s", f.content[:60])

        return 0
    except Exception:
        db.rollback()
        logger.exception("seed_wang_aunt_quartet failed")
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
