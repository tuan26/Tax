"""Cổng duy nhất để gửi dữ liệu ra dịch vụ AI nước ngoài. Mặc định đóng (fail-closed).

Chỉ cho đi khi đồng thời: cấu hình FOREIGN_AI_ENABLED bật (sau khi có ý kiến pháp lý),
dữ liệu thuộc loại được phép (synthetic hoặc đã duyệt ẩn danh), và payload không còn
mẫu thông tin nhạy cảm nào. Mọi lần thử, kể cả bị chặn, đều được ghi vào ai_call.
"""

from __future__ import annotations

import hashlib
import json
import re

ALLOWED_DATA_CLASSES = {"synthetic", "approved_anonymized"}

PII_PATTERNS = {
    "phone": re.compile(r"(?<!\d)(?:\+?84|0)(?:\d[\s.-]?){8,9}\d(?!\d)"),
    "national_id": re.compile(r"(?<!\d)\d{12}(?!\d)"),
    "bank_account": re.compile(r"(?<!\d)\d{8,16}(?!\d)"),
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
}


class OutboundBlocked(Exception):
    pass


def pii_found(payload) -> list[str]:
    text = json.dumps(payload, ensure_ascii=False) if not isinstance(payload, str) else payload
    return [name for name, p in PII_PATTERNS.items() if p.search(text)]


def send_to_foreign_ai(db, tenant_id, settings, provider: str, payload, data_class: str, client=None):
    """Ghi log trong transaction riêng trước khi quyết định, để lần bị chặn không mất log khi
    transaction của nơi gọi bị rollback."""
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    reason = None
    if not settings.foreign_ai_enabled:
        reason = "foreign_ai_disabled"
    elif data_class not in ALLOWED_DATA_CLASSES:
        reason = f"data_class_not_allowed:{data_class}"
    else:
        found = pii_found(payload)
        if found:
            reason = "pii_detected:" + ",".join(found)
    if reason is None and client is None:
        reason = "no_client_configured"
    with db.tx(tenant_id, actor_kind="system") as conn:
        conn.execute(
            "INSERT INTO ai_call (tenant_id, provider, destination, allowed, reason, payload_sha256) "
            "VALUES (%s, %s, 'foreign', %s, %s, %s)",
            (tenant_id, provider, reason is None, reason or "allowed", digest),
        )
    if reason:
        raise OutboundBlocked(reason)
    return client(payload)
