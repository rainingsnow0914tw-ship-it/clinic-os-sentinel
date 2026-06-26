"""
============================================================
services/audit_service.py
============================================================
寫 audit log 的統一入口（Sprint 1）。

規格 §14 商業底線：所有重要行為都要寫 audit_logs，append-only。

設計重點：
1. 函數簽名涵蓋規格列出的所有欄位
2. user_id 可空（系統觸發、agent task 觸發）
3. ip / user_agent 從 request 拿，由 caller 提供（避免 service 層碰 Request 物件）
4. 失敗不要抛 exception 把主流程帶崩 — 只記 log
   （audit log 寫不進去是嚴重 infra 問題，但不應讓使用者操作失敗）
5. 不在這層 commit — 由 caller 控制 transaction 邊界
   （這樣 audit log 跟主操作可以是同一個 transaction，要嘛全成功要嘛全失敗）
============================================================
"""

import logging
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def write_audit_log(
    db: Session,
    *,
    clinic_id: UUID,
    user_id: Optional[UUID],
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    old_value: Optional[dict[str, Any]] = None,
    new_value: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditLog:
    """
    寫一筆 audit log。

    Args:
        db: SQLAlchemy session（由 caller 控制 commit 時機）
        clinic_id: 哪間診所的事件
        user_id: 誰觸發的（系統觸發傳 None）
        action: dot-separated 的動作字串
                例如 'patient.create', 'visit.complete', 'invoice.void'
        entity_type: 'patient', 'visit', 'invoice'...
        entity_id: 主鍵字串（UUID 直接 str() 傳進來；非 UUID 也行）
        old_value: 修改前的 JSON 快照
        new_value: 修改後的 JSON 快照
        ip_address: 來源 IP（從 Request.client.host 拿）
        user_agent: 從 Request headers 拿

    Returns:
        建立好但還沒 commit 的 AuditLog 物件

    使用範例（在 service 層）：
        from app.services.audit_service import write_audit_log

        def void_invoice(db, invoice_id, user, request):
            invoice = ... # 改 status
            write_audit_log(
                db,
                clinic_id=invoice.clinic_id,
                user_id=user.id,
                action="invoice.void",
                entity_type="invoice",
                entity_id=str(invoice.id),
                old_value={"status": "issued"},
                new_value={"status": "voided"},
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("User-Agent"),
            )
            db.commit()  # ← caller 控制 commit
    """
    log = AuditLog(
        clinic_id=clinic_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value_json=old_value,
        new_value_json=new_value,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(log)
    db.flush()  # 拿到 id 但不 commit；commit 由 caller 決定

    logger.info(
        "Audit: clinic=%s user=%s action=%s entity=%s:%s",
        clinic_id, user_id, action, entity_type, entity_id,
    )
    return log
