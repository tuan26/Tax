"""Phát hiện và ghép chứng từ: chạy rule, ghép tay, đóng và mở lại, tin nhắn đòi chứng từ.

Phát hiện chỉ đóng khi:
- kế toán ghép chứng từ và xác nhận (resolution = matched),
- kế toán xác nhận đã có chứng từ ở nơi khác (has_document),
- kế toán bỏ qua kèm ghi chú (status DISMISSED),
- hoặc điều kiện của rule không còn (no_longer_applies), ví dụ bản ghi bị loại khỏi sổ.
"""

from __future__ import annotations

from datetime import date

from psycopg.types.json import Jsonb

from .domain.rules import RuleRecord, evaluate, match_evidence
from .review import ReviewError, effective_fields, finding_inputs

OPEN_STATES = ("OPEN", "REQUESTED")


def _active_records(conn, customer_id):
    return conn.execute("SELECT * FROM record WHERE customer_id = %s AND status = 'ACTIVE' ORDER BY created_at, id",
                        (customer_id,)).fetchall()


def _texts(conn, customer_id) -> dict[str, str]:
    return {str(r["id"]): r["text"] for r in conn.execute(
        "SELECT id, text FROM message WHERE customer_id = %s AND kind = 'text'", (customer_id,)).fetchall()}


def confirmed_matches(conn, customer_id):
    return conn.execute("SELECT * FROM match WHERE customer_id = %s AND status = 'CONFIRMED'",
                        (customer_id,)).fetchall()


def run_rules(conn, tenant_id, customer_id):
    rows = _active_records(conn, customer_id)
    texts = _texts(conn, customer_id)
    usable = []
    for i, r in enumerate(rows):
        fields = finding_inputs(r)
        if fields is None:
            continue
        ev_texts = [texts[e] for e in r["evidence_items"] if "#" not in e and e in texts]
        usable.append(RuleRecord(str(r["id"]), r["evidence_kind"], fields, list(r["evidence_items"]), ev_texts, i))
    matched = {str(m["payment_record_id"]) for m in confirmed_matches(conn, customer_id)}
    drafts = {d.fingerprint: d for d in evaluate(usable, matched)}
    existing = {f["fingerprint"]: f for f in conn.execute(
        "SELECT * FROM finding WHERE customer_id = %s", (customer_id,)).fetchall()}

    for fp, d in drafts.items():
        row = existing.get(fp)
        if row is None:
            conn.execute(
                "INSERT INTO finding (tenant_id, customer_id, rule_id, rule_version, fingerprint, severity, record_id,"
                " title, detail, amount, evidence) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (tenant_id, customer_id, d.rule_id, d.rule_version, fp, d.severity, d.record_id, d.title, d.detail,
                 d.amount, Jsonb(d.evidence)))
        elif row["status"] == "RESOLVED" and row["resolution"] == "no_longer_applies":
            conn.execute("UPDATE finding SET status='OPEN', resolution=NULL, resolution_note=NULL, decided_at=NULL,"
                         " decided_by=NULL, detail=%s, amount=%s, evidence=%s, updated_at=now() WHERE id=%s",
                         (d.detail, d.amount, Jsonb(d.evidence), row["id"]))
        elif row["status"] in OPEN_STATES and (row["detail"] != d.detail or row["evidence"] != d.evidence):
            conn.execute("UPDATE finding SET detail=%s, amount=%s, evidence=%s, updated_at=now() WHERE id=%s",
                         (d.detail, d.amount, Jsonb(d.evidence), row["id"]))
    for fp, row in existing.items():
        if fp not in drafts and row["status"] in OPEN_STATES:
            conn.execute("UPDATE finding SET status='RESOLVED', resolution='no_longer_applies',"
                         " resolution_note='Bản ghi đã thay đổi, chờ duyệt lại hoặc đã bị loại', decided_at=now(),"
                         " updated_at=now() WHERE id=%s", (row["id"],))


def _finding(conn, finding_id):
    f = conn.execute("SELECT * FROM finding WHERE id = %s", (finding_id,)).fetchone()
    if f is None:
        raise ReviewError("Không tìm thấy phát hiện")
    return f


def _record(conn, record_id):
    r = conn.execute("SELECT * FROM record WHERE id = %s", (record_id,)).fetchone()
    if r is None:
        raise ReviewError("Không tìm thấy giao dịch")
    return r


def match_candidates(conn, finding_id) -> list[dict]:
    """Chứng từ có thể đi kèm khoản chi. Chỉ là danh sách gợi ý để kế toán chọn, không tự ghép."""
    f = _finding(conn, finding_id)
    if f["rule_id"] != "DQ-01":
        return []
    payment = effective_fields(_record(conn, f["record_id"]))
    out = []
    for r in _active_records(conn, f["customer_id"]):
        if r["evidence_kind"] != "document" or str(r["id"]) == str(f["record_id"]):
            continue
        doc = effective_fields(r)
        ev = match_evidence(payment, doc)
        score = sum(1 for e in ev if e["ok"])
        when = doc.get("document_date") or doc.get("posting_date")
        gap = abs((date.fromisoformat(when) - date.fromisoformat(payment["posting_date"])).days) \
            if when and payment.get("posting_date") else 999
        if score == 0 or (not ev[0]["ok"] and gap > 14):
            continue
        out.append({"record_id": r["id"], "fields": doc, "evidence": ev, "score": score, "gap": gap,
                    "evidence_items": r["evidence_items"]})
    return sorted(out, key=lambda c: (-c["score"], c["gap"]))


def confirm_match(conn, finding_id, document_record_id, user_id):
    f = _finding(conn, finding_id)
    if f["rule_id"] != "DQ-01" or f["status"] not in OPEN_STATES:
        raise ReviewError("Chỉ ghép chứng từ cho phát hiện 'khoản chi chưa có chứng từ' đang mở")
    doc = _record(conn, document_record_id)
    if str(doc["customer_id"]) != str(f["customer_id"]) or doc["status"] != "ACTIVE":
        raise ReviewError("Chứng từ không thuộc hộ này hoặc đã bị loại")
    if doc["evidence_kind"] != "document":
        raise ReviewError("Chỉ ghép được với chứng từ (hóa đơn, phiếu)")
    payment = _record(conn, f["record_id"])
    evidence = match_evidence(effective_fields(payment), effective_fields(doc))
    match_id = conn.execute(
        "INSERT INTO match (tenant_id, customer_id, payment_record_id, document_record_id, match_type, evidence,"
        " status, created_by, user_id) VALUES (%s,%s,%s,%s,'payment_document',%s,'CONFIRMED','user',%s) RETURNING id",
        (f["tenant_id"], f["customer_id"], f["record_id"], document_record_id, Jsonb(evidence), user_id)
    ).fetchone()["id"]
    conn.execute("UPDATE finding SET status='RESOLVED', resolution='matched', match_id=%s, decided_at=now(),"
                 " decided_by=%s, updated_at=now() WHERE id=%s", (match_id, user_id, finding_id))
    run_rules(conn, f["tenant_id"], f["customer_id"])
    return match_id


def undo_match(conn, match_id, user_id):
    m = conn.execute("SELECT * FROM match WHERE id = %s", (match_id,)).fetchone()
    if m is None or m["status"] != "CONFIRMED":
        raise ReviewError("Không có ghép nào đang hiệu lực")
    conn.execute("UPDATE match SET status='UNDONE', undone_at=now(), undone_by=%s WHERE id=%s", (user_id, match_id))
    conn.execute("UPDATE finding SET status='OPEN', resolution=NULL, match_id=NULL, decided_at=NULL, decided_by=NULL,"
                 " updated_at=now() WHERE match_id=%s", (match_id,))
    run_rules(conn, m["tenant_id"], m["customer_id"])


def decide(conn, finding_id, action: str, note: str | None, user_id):
    f = _finding(conn, finding_id)
    if f["status"] not in OPEN_STATES:
        raise ReviewError("Phát hiện đã được xử lý; mở lại trước nếu muốn đổi")
    if action == "request":
        conn.execute("UPDATE finding SET status='REQUESTED', requested_at=now(), updated_at=now() WHERE id=%s",
                     (finding_id,))
    elif action == "has_document":
        conn.execute("UPDATE finding SET status='RESOLVED', resolution='has_document', resolution_note=%s,"
                     " decided_at=now(), decided_by=%s, updated_at=now() WHERE id=%s", (note, user_id, finding_id))
    elif action == "not_needed":
        if not note or not note.strip():
            raise ReviewError("Ghi lý do không cần xử lý")
        conn.execute("UPDATE finding SET status='DISMISSED', resolution_note=%s, decided_at=now(), decided_by=%s,"
                     " updated_at=now() WHERE id=%s", (note.strip(), user_id, finding_id))
    else:
        raise ReviewError("Thao tác không hợp lệ")


def reopen(conn, finding_id, user_id):
    f = _finding(conn, finding_id)
    if f["status"] in OPEN_STATES:
        raise ReviewError("Phát hiện đang mở")
    if f["resolution"] == "matched":
        raise ReviewError("Phát hiện đã đóng bằng ghép chứng từ; bỏ ghép để mở lại")
    conn.execute("UPDATE finding SET status='OPEN', resolution=NULL, resolution_note=NULL, decided_at=NULL,"
                 " decided_by=NULL, updated_at=now() WHERE id=%s", (finding_id,))
    run_rules(conn, f["tenant_id"], f["customer_id"])


def request_text(conn, finding_ids: list) -> str:
    rows = conn.execute("SELECT * FROM finding WHERE id = ANY(%s) ORDER BY created_at", (finding_ids,)).fetchall()
    if not rows:
        raise ReviewError("Chọn ít nhất một phát hiện")
    lines = ["Anh/chị vui lòng gửi giúp em chứng từ cho các khoản sau:"]
    for i, f in enumerate(rows, 1):
        lines.append(f"{i}. {f['detail'].split('. Kiểm tra')[0].split('. Nên')[0].rstrip('.')}")
    lines.append("Nếu khoản nào không có hóa đơn, anh/chị nhắn giúp em là mua của ai và mua gì. Em cảm ơn.")
    return "\n".join(lines)
