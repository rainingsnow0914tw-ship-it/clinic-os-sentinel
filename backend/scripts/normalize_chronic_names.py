"""
============================================================
scripts/normalize_chronic_names.py -- 修 patient_problems 英中混雜
============================================================
問題: seed_heart_layer.py 從 jimmy mock_data.json 的 chronic_conditions
字串直接灌 (英文如 'Hypertension'), 但 Phase 5 evolve_heart_layer 從
visit.diagnosis 推導用的是中文 (e.g. '原發性高血壓'). 結果同 patient
可能有英中重複 chronic + UI 顯示英文摘要看起來詭異.

修兩件事:
1. patient_problems.problem_name 套 CHRONIC_NAME_MAP normalize 成中文
2. 同 patient 同 normalized name -> keep 1 個 (優先保留 source='inferred_from_visit')

用法:
    cd backend && .venv/Scripts/python -m scripts.normalize_chronic_names
"""

from __future__ import annotations

import logging
import sys
from collections import defaultdict

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import PatientProblem

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# 對齊 Phase 5 evolve_heart_layer.CHRONIC_DISEASE_KEYWORDS 的 canonical names
CHRONIC_NAME_MAP: dict[str, tuple[str, str | None]] = {
    "hypertension": ("原發性高血壓", "I10"),
    "htn": ("原發性高血壓", "I10"),
    "primary hypertension": ("原發性高血壓", "I10"),

    "diabetes": ("第二型糖尿病", "E11.9"),
    "type 2 diabetes": ("第二型糖尿病", "E11.9"),
    "t2dm": ("第二型糖尿病", "E11.9"),
    "type ii diabetes": ("第二型糖尿病", "E11.9"),

    "hyperlipidemia": ("高脂血症", "E78.5"),
    "dyslipidemia": ("高脂血症", "E78.5"),

    "osteoarthritis": ("骨關節炎", "M19.9"),
    "oa": ("骨關節炎", "M19.9"),
    "knee oa": ("膝部骨關節炎", "M17.9"),

    "heart failure": ("慢性心衰竭", "I50.9"),
    "chf": ("慢性心衰竭", "I50.9"),
    "congestive heart failure": ("慢性心衰竭", "I50.9"),

    "asthma": ("支氣管哮喘", "J45.909"),
    "bronchial asthma": ("支氣管哮喘", "J45.909"),

    "gerd": ("胃食道逆流症", "K21.9"),
    "reflux disease": ("胃食道逆流症", "K21.9"),

    "copd": ("慢性阻塞性肺病", "J44.9"),

    "dementia": ("失智症", "F03"),
    "mci": ("輕度認知障礙", "G31.84"),
    "mild cognitive impairment": ("輕度認知障礙", "G31.84"),

    "migraine": ("偏頭痛", "G43.909"),

    "anxiety disorder": ("廣泛性焦慮症", "F41.1"),
    "generalized anxiety disorder": ("廣泛性焦慮症", "F41.1"),
    "anxiety": ("廣泛性焦慮症", "F41.1"),

    "atrial fibrillation": ("心房顫動", "I48.0"),
    "afib": ("心房顫動", "I48.0"),

    "ckd": ("慢性腎臟病", "N18.9"),
    "ckd stage 3": ("慢性腎臟病第三期", "N18.30"),
    "chronic kidney disease": ("慢性腎臟病", "N18.9"),

    "gout": ("痛風", "M10.9"),

    "osteoporosis": ("骨質疏鬆症", "M81.0"),

    "depression": ("重度憂鬱症", "F33.1"),
    "major depression": ("重度憂鬱症", "F33.1"),
    "mdd": ("重度憂鬱症", "F33.1"),

    "bph": ("良性攝護腺肥大", "N40.0"),
    "benign prostatic hyperplasia": ("良性攝護腺肥大", "N40.0"),

    "cad": ("冠狀動脈疾病", "I25.10"),
    "coronary artery disease": ("冠狀動脈疾病", "I25.10"),

    "hypothyroidism": ("甲狀腺功能低下", "E03.9"),
}


# 已是中文且 canonical 的 -> 保留原樣 (這些是 Phase 5 evolve 出來的, 不要動)
ALREADY_CANONICAL_CN = {
    "原發性高血壓", "第二型糖尿病", "高脂血症", "骨關節炎",
    "膝部骨關節炎", "慢性心衰竭", "支氣管哮喘", "胃食道逆流症",
    "慢性阻塞性肺病", "失智症", "輕度認知障礙", "偏頭痛",
    "廣泛性焦慮症", "心房顫動", "慢性腎臟病", "慢性腎臟病第三期",
    "痛風", "骨質疏鬆症", "重度憂鬱症", "良性攝護腺肥大",
    "冠狀動脈疾病", "甲狀腺功能低下", "甲狀腺功能亢進",
}


def normalize(name: str) -> tuple[str, str | None] | None:
    """回 (canonical_chinese, icd10) 或 None 若已是中文 canonical."""
    if name in ALREADY_CANONICAL_CN:
        return None   # 已是中文, 不動
    key = name.lower().strip()
    return CHRONIC_NAME_MAP.get(key)


def main() -> int:
    db = SessionLocal()
    try:
        all_problems = db.scalars(select(PatientProblem)).all()
        logger.info("total patient_problems: %d", len(all_problems))

        # 第一輪: 套翻譯 (update problem_name + icd10)
        updated = 0
        unknown_names: set[str] = set()
        for p in all_problems:
            mapped = normalize(p.problem_name)
            if mapped is None:
                if p.problem_name not in ALREADY_CANONICAL_CN:
                    unknown_names.add(p.problem_name)
                continue
            canonical, icd = mapped
            if p.problem_name != canonical:
                logger.info("  normalize: %r -> %r", p.problem_name, canonical)
                p.problem_name = canonical
                if icd and not p.icd10_code:
                    p.icd10_code = icd
                updated += 1

        logger.info("translation step: updated %d rows", updated)

        if unknown_names:
            logger.warning("不在 map 內、保留原樣的 chronic name:")
            for n in sorted(unknown_names):
                logger.warning("  %r", n)

        db.flush()

        # 第二輪: dedup 同 patient 同 problem_name
        # 抓全部 (含剛剛 normalize 過的) 重抓一次
        all_problems = db.scalars(select(PatientProblem)).all()
        by_pat_name: dict[tuple, list[PatientProblem]] = defaultdict(list)
        for p in all_problems:
            by_pat_name[(p.patient_id, p.problem_name)].append(p)

        deleted = 0
        for (pid, name), group in by_pat_name.items():
            if len(group) < 2:
                continue
            # 排序: source='inferred_from_visit' 最後 (優先保留)、created_at desc
            # 因為 inferred_from_visit 是 Phase 5 evolve 出來的, 比較新且有 visit 證據
            def keep_priority(p: PatientProblem) -> int:
                # 越大優先保留
                if p.problem_source == "inferred_from_visit":
                    return 3
                if p.problem_source == "verified":
                    return 2
                if p.problem_source == "authoritative":
                    return 1
                return 0
            group.sort(key=keep_priority, reverse=True)
            keep = group[0]
            for dup in group[1:]:
                logger.info(
                    "  dedup patient=%s name=%r keep id=%s (source=%s) delete id=%s (source=%s)",
                    pid, name, keep.id, keep.problem_source, dup.id, dup.problem_source,
                )
                db.delete(dup)
                deleted += 1

        logger.info("dedup step: deleted %d duplicate rows", deleted)

        db.commit()
        logger.info("DONE: translated=%d deduped=%d", updated, deleted)
        return 0
    except Exception:
        db.rollback()
        logger.exception("normalize failed")
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
