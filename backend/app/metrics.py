"""Chỉ số pilot, tính từ lịch sử quyết định trong DB, tách theo source_type.

STOR (Straight-Through Organization Rate): tỷ lệ giao dịch đang có trong sổ mà engine tự tổ chức
đúng, kế toán không phải chỉnh cấu trúc (gán, tách, gộp, chọn ứng viên, xác nhận nhóm). Sửa số tiền,
ngày, MST không tính là chỉnh cấu trúc.

STOR phải đọc cùng silent_restructure_rate: tỷ lệ quyết định CONFIDENT của engine bị kế toán thay.
Engine có thể đẩy STOR lên bằng cách đoán; khi đó silent_restructure_rate tăng theo.

python -m app.metrics            # mọi hộ, dùng ADMIN_DATABASE_URL
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

import psycopg
from psycopg.rows import dict_row

CORE = ("transaction_type", "amount", "posting_date")


def _ratio(a, b):
    return round(a / b, 4) if b else None


def pilot_metrics(conn, customer_id=None) -> dict:
    where, args = ("AND g.customer_id = %s", (customer_id,)) if customer_id else ("", ())
    groups = conn.execute(f"""
        SELECT g.id, g.created_by, g.superseded_at,
          (SELECT m.source_type FROM item_decision d JOIN message m ON m.id = d.message_id
            WHERE d.group_id = g.id AND d.decision = 'anchor' ORDER BY d.created_at LIMIT 1) AS source_type,
          EXISTS (SELECT 1 FROM item_decision d WHERE d.decided_by = 'user' AND d.decision IN ('anchor', 'link')
            AND (d.group_id = g.id OR g.id = ANY(d.target_group_ids))) AS touched
        FROM message_group g WHERE true {where}""", args).fetchall()
    excluded = {r["group_id"]: r["excluded_reason"] for r in conn.execute(
        "SELECT group_id, excluded_reason FROM record WHERE status = 'EXCLUDED'"
        + (" AND customer_id = %s" if customer_id else ""), args).fetchall()}

    decisions = conn.execute(f"""
        SELECT d.*, m.source_type,
          EXISTS (SELECT 1 FROM item_decision u WHERE u.customer_id = d.customer_id AND u.item_ref = d.item_ref
            AND u.decided_by = 'user' AND u.created_at >= d.superseded_at
            AND coalesce(u.reason, '') NOT LIKE 'excluded:%%') AS replaced_by_user
        FROM item_decision d JOIN message m ON m.id = d.message_id
        WHERE d.decided_by = 'engine' {where.replace('g.', 'd.')}""", args).fetchall()

    records = conn.execute(f"""
        SELECT r.*, (SELECT m.source_type FROM item_decision d JOIN message m ON m.id = d.message_id
            WHERE d.group_id = r.group_id AND d.decision = 'anchor' ORDER BY d.created_at LIMIT 1) AS source_type
        FROM record r WHERE r.confirmed_at IS NOT NULL {where.replace('g.', 'r.')}""", args).fetchall()

    activity = conn.execute(f"""
        SELECT customer_id, count(DISTINCT date_trunc('minute', at)) AS minutes FROM activity_log a
        WHERE customer_id IS NOT NULL {where.replace('g.', 'a.')} GROUP BY customer_id""", args).fetchall()

    out: dict = defaultdict(lambda: defaultdict(int))
    for g in groups:
        src = g["source_type"] or "UNKNOWN"
        for key in (src, "ALL"):
            b = out[key]
            if g["id"] in excluded:
                b[f"excluded:{excluded[g['id']]}"] += 1
                continue
            if g["superseded_at"] is not None:
                continue
            b["transactions"] += 1
            if g["created_by"] == "engine" and not g["touched"]:
                b["straight_through"] += 1
    for d in decisions:
        for key in (d["source_type"], "ALL"):
            b = out[key]
            b["engine_decisions"] += 1
            if d["status"] == "AMBIGUOUS" or (d["decision"] == "unmatched" and d["needs_review"]):
                b["sent_to_review"] += 1
            if d["status"] == "CONFIDENT" and d["superseded_at"] is not None and d["replaced_by_user"]:
                b["silent_restructure"] += 1
    for r in records:
        ai, final = r["fields_ai"], r["fields_confirmed"] or {}
        for key in (r["source_type"] or "UNKNOWN", "ALL"):
            b = out[key]
            b["confirmed_records"] += 1
            missing = any((ai.get(k) or {}).get("value") is None for k in CORE)
            wrong = any((ai.get(k) or {}).get("value") is not None and final.get(k) != ai[k]["value"] for k in CORE)
            b["records_ai_missing_field"] += missing
            b["records_ai_wrong_field"] += wrong

    result = {}
    for key, b in out.items():
        result[key] = {
            **b,
            "STOR": _ratio(b["straight_through"], b["transactions"]),
            "silent_restructure_rate": _ratio(b["silent_restructure"], b["engine_decisions"]),
            "review_rate": _ratio(b["sent_to_review"], b["engine_decisions"]),
            "ai_wrong_field_rate": _ratio(b["records_ai_wrong_field"], b["confirmed_records"]),
        }
    result["active_minutes_by_customer"] = {str(a["customer_id"]): a["minutes"] for a in activity}
    return result


def main(argv):
    with psycopg.connect(os.environ["ADMIN_DATABASE_URL"], row_factory=dict_row) as conn:
        print(json.dumps(pilot_metrics(conn, argv[1] if len(argv) > 1 else None), ensure_ascii=False, indent=2,
                         default=str))


if __name__ == "__main__":
    main(sys.argv)
