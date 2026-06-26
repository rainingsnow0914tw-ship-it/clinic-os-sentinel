"""
============================================================
tests/test_permissions.py
============================================================
測試 has_permission() 的邏輯（owner-bypass / custom override / default matrix）。

跑法：
    cd backend
    pytest tests/test_permissions.py -v

⚠️ 這些測試不需要 DB，只是純邏輯驗證 — 故意設計成這樣，跑得快。
============================================================
"""

from types import SimpleNamespace

import pytest

from app.middleware.clinic_permission import has_permission


def make_membership(role: str, custom: dict | None = None):
    """產一個假的 membership 物件（不是 ORM，只要有對的欄位即可）"""
    return SimpleNamespace(
        role=role,
        custom_permissions_json=custom or {},
    )


# ============================================================
# Owner 永遠通過（即使 custom 設 false）
# ============================================================
def test_owner_bypasses_all_permissions():
    m = make_membership("owner")
    assert has_permission(m, "can_void_invoice") is True
    assert has_permission(m, "can_manage_users") is True
    assert has_permission(m, "non_existent_permission") is True


def test_owner_bypass_ignores_negative_custom():
    """owner 即使被誤把 custom 關 false，仍然通過（避免自我鎖死）"""
    m = make_membership("owner", {"can_void_invoice": False})
    assert has_permission(m, "can_void_invoice") is True


# ============================================================
# Doctor / Nurse / Reception 走預設矩陣
# ============================================================
def test_doctor_default_no_void_invoice():
    m = make_membership("doctor")
    assert has_permission(m, "can_void_invoice") is False


def test_nurse_default_can_manage_inventory():
    m = make_membership("nurse")
    assert has_permission(m, "can_manage_inventory") is True


def test_reception_default_no_revenue_report():
    m = make_membership("reception")
    assert has_permission(m, "can_view_revenue_report") is False


# ============================================================
# Custom 覆蓋
# ============================================================
def test_custom_can_open_extra_permission():
    """reception 預設不能作廢，但被 owner 個別開啟"""
    m = make_membership("reception", {"can_void_invoice": True})
    assert has_permission(m, "can_void_invoice") is True


def test_custom_can_close_default_permission():
    """nurse 預設能管庫存，但個別關掉"""
    m = make_membership("nurse", {"can_manage_inventory": False})
    assert has_permission(m, "can_manage_inventory") is False


# ============================================================
# 未知 permission key
# ============================================================
def test_unknown_permission_for_non_owner_is_false():
    """未定義的 permission 對非 owner 一律拒絕（最保守）"""
    m = make_membership("doctor")
    assert has_permission(m, "this_permission_does_not_exist") is False


# ============================================================
# 未知 role
# ============================================================
def test_unknown_role_falls_back_to_no_permission():
    """role 不在預設矩陣中（資料髒掉）→ 一律拒絕"""
    m = make_membership("intern")  # 預設矩陣沒這個
    assert has_permission(m, "can_manage_inventory") is False


# ============================================================
# Custom 為空 dict / None
# ============================================================
@pytest.mark.parametrize("custom", [None, {}, {"unrelated": True}])
def test_empty_or_unrelated_custom_uses_default(custom):
    m = make_membership("doctor", custom)
    assert has_permission(m, "can_view_revenue_report") is False
    assert has_permission(m, "can_manage_inventory") is False
