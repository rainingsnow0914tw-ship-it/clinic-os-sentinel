"""
============================================================
schemas/sentinel.py — Sentinel 4 個 agent 的 I/O Pydantic schemas
============================================================
這份是 4 個 agent 跟 REST API 的契約。前端、demo 腳本、評審 test access
都靠這份 schema 對齊。

設計原則：
- request 帶最少必要欄位(demo 可以只給文字，不必接整個 clinic-os patients 表)
- response 帶 model_used + tokens，便於評審看技術深度(也省事計算 demo 預算)
- 4 個 agent 的 response 都有「來源連結」欄位(PubMed/openFDA)，對應鐵律 2
============================================================
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# 共用：病人心臟資料(縮版，從 4 心臟表組出來；demo 可手寫)
# ============================================================
class HeartFlag(BaseModel):
    """病人紅旗(對應 patient_flags 表)。"""

    type: Literal[
        "allergy",            # 過敏(永久)
        "pregnancy",          # 懷孕/哺乳(時效)
        "major_history",      # 重大病史(中風後遺症等，永久)
        "medical_directive",  # 醫療指示(DNR)
        "interaction_note",   # 醫病互動註記(只記客觀事實)
        "origin",             # 來源地/居住背景(沉睡)
    ]
    content: str
    severity: Literal["red", "yellow", "info"] | None = None
    source: Literal["self_report", "verified", "authoritative"] = "self_report"
    valid_until: str | None = None      # 時效型 ISO date
    notes: str | None = None


class HeartProblem(BaseModel):
    """慢性病(對應 patient_problems 表)。"""

    name: str                                   # 病名
    diagnosed_at: str | None = None             # 診斷時間 ISO
    control_status: Literal["controlled", "unstable", "worsening"] | None = None
    medications: list[str] = []                 # 對應用藥(藥名 list)


class HeartMedication(BaseModel):
    """長期用藥(對應 patient_medications 表)。"""

    name: str
    category: Literal[
        "chronic_disease_med",      # 慢性病藥
        "supplement",               # 保健品
        "tcm",                      # 中藥/中成藥
    ] = "chronic_disease_med"
    composition_certain: bool = True             # 成分明確 (False = 成分不明)
    for_problem: str | None = None               # 對應哪個慢性病


# ============================================================
# Agent 1：入口偵查官(Intake)
# ============================================================
class IntakeRequest(BaseModel):
    """
    醫生口述輸入。

    raw_dictation: 醫生剛剛說了什麼(原話)
    chief_complaint_hint: 主訴提示(可選，若前端已有單獨欄位可傳)
    patient_id / visit_id: 連到病人/就診 UUID(demo 可不帶)
    """

    raw_dictation: str = Field(..., min_length=1)
    chief_complaint_hint: str | None = None
    patient_id: UUID | None = None
    visit_id: UUID | None = None


class IntakeFinding(BaseModel):
    section: Literal["main_complaint", "extra", "anomaly", "suggested_question"]
    text: str
    linkage: str | None = None


class IntakeResponse(BaseModel):
    # 關掉 Pydantic V2 "model_" 保留前綴警告(model_used 是業務欄位非 ModelMetaclass)
    model_config = ConfigDict(protected_namespaces=())
    findings: list[IntakeFinding]
    summary: str = ""
    model_used: str
    input_tokens: int = 0
    output_tokens: int = 0


# ============================================================
# Agent 2：前閘門鑑別診斷官(Triage)
# ============================================================
class TriageRequest(BaseModel):
    """
    working_hypothesis: 醫生當前工作假設(例：「高血壓追蹤」)
    flags / problems / medications: 病人縱向真相(從心臟表組出)
    """

    working_hypothesis: str = Field(..., min_length=1)
    flags: list[HeartFlag] = []
    problems: list[HeartProblem] = []
    medications: list[HeartMedication] = []
    patient_id: UUID | None = None
    visit_id: UUID | None = None


class TriageDifferential(BaseModel):
    diagnosis: str
    reasoning: str
    source_pmid: str | None = None
    source_url: str | None = None


class TriageResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    has_conflict: bool                          # 有真實矛盾才會 True
    conflict_summary: str = ""                  # 觸發矛盾的紅旗 + 假設
    differentials: list[TriageDifferential] = []
    closing_note: str = "供查證參考，最終判斷由醫生。"
    model_used: str
    input_tokens: int = 0
    output_tokens: int = 0


# ============================================================
# Agent 3：後閘門處方審計官(Audit)
# ============================================================
class AuditRequest(BaseModel):
    new_prescription: list[str] = Field(..., min_length=1)   # 新處方藥名 list
    flags: list[HeartFlag] = []
    long_term_medications: list[HeartMedication] = []
    problems: list[HeartProblem] = []
    patient_id: UUID | None = None
    visit_id: UUID | None = None


class RuleEngineFinding(BaseModel):
    drug_a: str
    drug_b: str
    severity: str
    description: str
    source: str
    source_url: str | None = None
    needs_confirmation: bool


class ContextualRisk(BaseModel):
    """AI 第三層情境推理結果(必附來源或標 needs_confirmation)。"""

    drug: str
    risk: str
    triggered_by: str                           # 哪個紅旗/病史觸發
    source_url: str | None = None
    needs_confirmation: bool = True


class AuditResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    rule_engine_findings: list[RuleEngineFinding] = []
    contextual_risks: list[ContextualRisk] = []
    unknowns: list[str] = []                    # 成分不明保健品提醒
    closing_note: str = "供參考，最終處方由醫生確認。"
    model_used: str
    input_tokens: int = 0
    output_tokens: int = 0


# ============================================================
# Agent 4：衛教出口官(Education)
# ============================================================
class EducationRequest(BaseModel):
    diagnosis: str = Field(..., min_length=1)
    patient_habits: dict[str, Any] = {}         # {"diet": "煎炸", "sleep": "熬夜"}
    patient_name_hint: str | None = None        # 抬頭用，可選
    patient_id: UUID | None = None
    visit_id: UUID | None = None


class EducationResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    advice: str                                 # 個人化生活醫囑
    reasoning: str                              # 為什麼這樣建議(原理)
    closing_note: str = "此為輔助生活建議，請以醫生正式醫囑為準。"
    model_used: str
    input_tokens: int = 0
    output_tokens: int = 0
