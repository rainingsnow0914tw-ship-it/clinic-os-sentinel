"""
============================================================
scripts/extend_mock_patients.py -- 把 jimmy 60 病人擴成 100 (v0.3 Phase 2.3)
============================================================
司機 2026-06-27 指示「病例要一百份樣板」。

策略:
- 保留 jimmy 60 個不動
- 加 40 個新 patient (patient_061 ~ patient_100)
- 一半 jimmy 風格 demo 名字 + 一半中文澳門名 (對齊 v0.3.1 §10 「澳門特色」)
- chronic/allergy 分布刻意加強 (jimmy 60 個 39 None 太稀疏、demo 沒戲)
- 真澳門地址 (氹仔/新口岸/黑沙環)

idempotent: 重跑會先把 patient_061 ~ patient_100 移掉再加 (jimmy 60 不動)。
deterministic: 用 seed=20260627, 同樣 seed 同樣輸出。

寫 patient_007 王阿姨 (v0.3.1 §9 四幕劇主角) 在另一個 script
(extend_mock_wang_ayi.py, Phase 2.4 處理) -- 本檔不碰 patient_007 (jimmy 已存在的 patient)。

用法:
    python -m scripts.extend_mock_patients
    python -m scripts.extend_mock_patients --dry-run    # 只印 stats 不寫檔
============================================================
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from datetime import date

# Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


MOCK_PATH = Path(__file__).resolve().parent.parent / "seed_data" / "external_sources" / "mock_data.json"

SEED = 20260627
TARGET_TOTAL = 100   # 100 個 patient 總數
EXTEND_START = 61    # 從 patient_061 開始


# ─────────────────────────────────────────────────────────
# Name pools
# ─────────────────────────────────────────────────────────

# 澳門常見中文姓
SURNAMES_ZH = ["王", "李", "張", "陳", "林", "黃", "何", "吳", "周", "鄭",
               "梁", "高", "羅", "蘇", "葉", "馮", "余", "麥", "鍾", "歐陽"]

# 男女名字 (澳門/廣東風格)
GIVEN_M_ZH = ["志強", "家華", "偉文", "永鴻", "建邦", "俊傑", "祖兒", "嘉明",
              "天宇", "啟賢", "立群", "永康", "炳輝", "灝森", "兆豐"]
GIVEN_F_ZH = ["玉芳", "佩珊", "嘉怡", "美玲", "婉婷", "雅雯", "詠琪", "曉彤",
              "美琪", "麗珊", "詩雅", "凱琳", "依琳", "曉欣", "兆兒"]

# Jimmy 風格英文 demo 名
DEMO_LABELS = ["Generic Adult", "Generic Senior", "Generic Super Senior",
               "Generic Youth", "Generic Mid-Age", "Demo Comorbid",
               "Demo Polypharm", "Demo Geriatric", "Family Member",
               "Working Adult", "Retiree Case"]


# ─────────────────────────────────────────────────────────
# Medical pools
# ─────────────────────────────────────────────────────────

ALLERGENS = [
    "Penicillin",
    "NSAIDs (Ibuprofen)",
    "Sulfa drugs",
    "Aspirin",
    "Cephalosporin",
    "Erythromycin",
    "Seafood",
    "Latex",
    "Egg",
    "Peanut",
    "Iodine contrast",
]

CHRONIC_CONDITIONS_COMMON = [
    "Hypertension",
    "Type 2 Diabetes",
    "Hyperlipidemia",
    "Asthma",
    "COPD",
    "Osteoarthritis",
    "Atrial Fibrillation",
    "CKD Stage 3",
    "Hypothyroidism",
    "Anxiety Disorder",
    "Migraine",
    "GERD",
    "Heart Failure",
    "Dementia",
    "Depression",
    "Gout",
    "Osteoporosis",
]

CHRONIC_CONDITIONS_MALE_ONLY = ["BPH"]   # 攝護腺肥大

def chronic_pool(gender: str) -> list[str]:
    pool = list(CHRONIC_CONDITIONS_COMMON)
    if gender == "M":
        pool += CHRONIC_CONDITIONS_MALE_ONLY
    return pool


# ─────────────────────────────────────────────────────────
# Address pools (real Macau districts)
# ─────────────────────────────────────────────────────────

MACAU_DISTRICTS = [
    "氹仔花城大馬路", "新口岸宋玉生廣場", "黑沙環新街", "氹仔湖畔大廈",
    "祐漢新邨", "筷子基新街", "下環街", "高士德大馬路",
    "南灣大馬路", "提督馬路", "新馬路", "亞馬喇前地",
    "氹仔哥英布拉街", "路環石排灣", "外港新填海區",
]


def gen_address(idx: int, rng: random.Random) -> str:
    """生 1 條真澳門地址。"""
    district = rng.choice(MACAU_DISTRICTS)
    no = rng.randint(1, 199)
    floor = rng.choice(["", f" {rng.randint(2, 25)} 樓", f" {rng.randint(2, 25)} 樓 {chr(65 + rng.randint(0, 7))} 座"])
    return f"{district} {no} 號{floor}, 澳門"


def gen_dob(age_band: str, rng: random.Random) -> str:
    """依年齡組生 DOB ISO date。"""
    today = date(2026, 6, 27)
    if age_band == "young":
        age = rng.randint(20, 39)
    elif age_band == "middle":
        age = rng.randint(40, 59)
    elif age_band == "senior":
        age = rng.randint(60, 74)
    else:  # super_senior
        age = rng.randint(75, 92)
    birth_year = today.year - age
    birth_month = rng.randint(1, 12)
    birth_day = rng.randint(1, 28)
    return f"{birth_year:04d}-{birth_month:02d}-{birth_day:02d}"


def gen_name(use_chinese: bool, gender: str, demo_idx: int, rng: random.Random) -> str:
    """生 1 個名字 — 中文澳門名或 jimmy 風格 demo 名。"""
    if use_chinese:
        sur = rng.choice(SURNAMES_ZH)
        given = rng.choice(GIVEN_M_ZH if gender == "M" else GIVEN_F_ZH)
        return f"{sur}{given}"
    else:
        label = rng.choice(DEMO_LABELS)
        return f"{label} {demo_idx}"


def gen_allergies(profile: str, rng: random.Random) -> str:
    """依 profile 生 allergies 字串。"""
    if profile == "none":
        return "None"
    elif profile == "single":
        return rng.choice(ALLERGENS)
    elif profile == "multi":
        n = rng.randint(2, 3)
        return ", ".join(rng.sample(ALLERGENS, n))
    return "None"


def gen_chronic(profile: str, gender: str, rng: random.Random) -> str:
    """依 profile 生 chronic_conditions 字串 (含 gender filter)。"""
    if profile == "none":
        return "None"
    pool = chronic_pool(gender)
    if profile == "single":
        return rng.choice(pool)
    elif profile == "double":
        return ", ".join(rng.sample(pool, 2))
    elif profile == "triple":
        return ", ".join(rng.sample(pool, 3))
    return "None"


def build_patient(idx: int, rng: random.Random) -> dict:
    """生 1 個 patient_idx (idx = 61~100)。"""
    # 年齡組分布: senior 多 (demo 看老人 case 比較有戲)
    age_band = rng.choices(
        ["young", "middle", "senior", "super_senior"],
        weights=[2, 3, 4, 1],
    )[0]
    gender = rng.choice(["M", "F"])

    # 名字: 一半中文澳門 / 一半 jimmy 風格
    use_chinese = (idx % 2 == 0)
    name = gen_name(use_chinese, gender, idx - 60, rng)

    # Allergies 分布: 25% 有 (15% single / 10% multi), 75% None
    allergy_profile = rng.choices(
        ["none", "single", "multi"],
        weights=[75, 15, 10],
    )[0]

    # Chronic 分布: senior 70% 有, young 20% 有
    if age_band in ("senior", "super_senior"):
        chronic_profile = rng.choices(
            ["none", "single", "double", "triple"],
            weights=[30, 35, 25, 10],
        )[0]
    elif age_band == "middle":
        chronic_profile = rng.choices(
            ["none", "single", "double"],
            weights=[50, 35, 15],
        )[0]
    else:  # young
        chronic_profile = rng.choices(
            ["none", "single"],
            weights=[80, 20],
        )[0]

    return {
        "patient_ref": f"patient_{idx:03d}",
        "full_name": name,
        "gender": gender,
        "date_of_birth": gen_dob(age_band, rng),
        "phone": f"6{rng.randint(100, 999)}-{rng.randint(1000, 9999)}",
        "id_number": f"TEST-{idx:04d}",
        "address": gen_address(idx, rng),
        "emergency_contact_name": rng.choice(["Spouse", "Son", "Daughter", "Sibling", "Mom", "Dad"]),
        "emergency_contact_phone": f"6{rng.randint(100, 999)}-{rng.randint(1000, 9999)}",
        "allergies": gen_allergies(allergy_profile, rng),
        "chronic_conditions": gen_chronic(chronic_profile, gender, rng),
        "notes": f"Phase 2 extended ({age_band} {gender})",
        "is_demo_data": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="只印 stats 不寫檔")
    parser.add_argument("--mock-path", default=str(MOCK_PATH))
    args = parser.parse_args()

    rng = random.Random(SEED)

    mock_path = Path(args.mock_path)
    with mock_path.open(encoding="utf-8") as f:
        data = json.load(f)

    # 切出 jimmy 60 (patient_001 ~ patient_060), 移掉之前可能加過的 061+
    jimmy_60 = [p for p in data["patients"] if int(p["patient_ref"].split("_")[1]) <= 60]
    if len(jimmy_60) != 60:
        print(f"⚠️ jimmy patient count = {len(jimmy_60)}, 預期 60")

    # 生 40 個新 patient (patient_061 ~ patient_100)
    new_patients = [build_patient(i, rng) for i in range(EXTEND_START, TARGET_TOTAL + 1)]

    # 統計新增的分布
    n_with_allergy = sum(1 for p in new_patients if p["allergies"] != "None")
    n_with_chronic = sum(1 for p in new_patients if p["chronic_conditions"] != "None")
    n_chinese = sum(1 for p in new_patients if not p["full_name"].startswith(("Generic", "Demo", "Family", "Working", "Retiree")))

    print("=" * 60)
    print(f"擴 {len(new_patients)} 個新 patient (patient_{EXTEND_START:03d} ~ patient_{TARGET_TOTAL:03d})")
    print(f"  含 allergy : {n_with_allergy} / {len(new_patients)} ({n_with_allergy/len(new_patients)*100:.0f}%)")
    print(f"  含 chronic : {n_with_chronic} / {len(new_patients)} ({n_with_chronic/len(new_patients)*100:.0f}%)")
    print(f"  中文澳門名 : {n_chinese} / {len(new_patients)} ({n_chinese/len(new_patients)*100:.0f}%)")
    print("=" * 60)
    print("樣本 5 個:")
    for p in new_patients[:5]:
        print(f"  {p['patient_ref']} {p['full_name']} ({p['gender']}/{p['date_of_birth']})")
        print(f"    addr: {p['address']}")
        print(f"    allergy: {p['allergies']}")
        print(f"    chronic: {p['chronic_conditions']}")

    if args.dry_run:
        print("\n[DRY RUN] 不寫檔")
        return 0

    # 寫回
    data["patients"] = jimmy_60 + new_patients
    with mock_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] 寫回 {mock_path} (總 {len(data['patients'])} patient)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
