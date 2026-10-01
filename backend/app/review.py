"""Thao tác của kế toán. Mỗi thao tác chỉ thêm quyết định mới (decided_by = user) và đánh dấu
quyết định cũ hết hiệu lực, rồi tính lại bản ghi. Không có thao tác xóa."""

from __future__ import annotations

from datetime import date


from psycopg.types.json import Jsonb

from .domain.grouping import AMBIGUOUS, CONFIDENT, NONE_CANDIDATE, UNMATCHED
from .domain.money import find_amounts
from .pipeline import insert_decision, insert_group, renormalize


class ReviewError(Exception):
    """Thao tác không hợp lệ với trạng thái hiện tại."""


EDITABLE_FIELDS = ("transaction_type", "amount", "document_date", "posting_date", "description")
REQUIRED_TO_CONFIRM = ("transaction_type", "amount", "posting_date")


def _decision(conn, decision_id):
    d = conn.execute("SELECT * FROM item_decision WHERE id = %s AND superseded_at IS NULL", (decision_id,)).fetchone()
    if d is None:
        raise ReviewError("Quyết định không tồn tại hoặc đã được xử lý")
    return d


def _supersede_decision(conn, decision_id):
    conn.execute("UPDATE item_decision SET superseded_at = now() WHERE id = %s AND superseded_at IS NULL",
                 (decision_id,))


def _active_group(conn, group_id):
    g = conn.execute("SELECT * FROM message_group WHERE id = %s AND superseded_at IS NULL", (group_id,)).fetchone()
    if g is None:
        raise ReviewError("Nhóm không tồn tại hoặc đã được gộp/tách")
    return g


def _anchors(conn, group_id):
    return conn.execute(
        "SELECT * FROM item_decision WHERE group_id = %s AND decision = 'anchor' AND superseded_at IS NULL"
        " ORDER BY created_at", (group_id,)).fetchall()


def _supersede_empty_group(conn, group_id):
    if not _anchors(conn, group_id):
        conn.execute("UPDATE message_group SET superseded_at = now() WHERE id = %s AND superseded_at IS NULL",
                     (group_id,))


def _ctx(d):
    return d["tenant_id"], d["customer_id"]


def resolve_ambiguous(conn, decision_id, choice: str, user_id):
    """Kế toán chọn một ứng viên cho liên kết mơ hồ."""
    d = _decision(conn, decision_id)
    if d["status"] != AMBIGUOUS or d["decision"] != "link":
        raise ReviewError("Chỉ chọn ứng viên cho liên kết đang mơ hồ")
    if choice not in (d["candidates"] or []):
        raise ReviewError("Lựa chọn không nằm trong danh sách ứng viên")
    tenant, customer = _ctx(d)
    _supersede_decision(conn, decision_id)
    if choice == NONE_CANDIDATE:
        if d["attachment_id"] is not None:
            gid = insert_group(conn, tenant, customer, "document", CONFIDENT, created_by="user")
            insert_decision(conn, tenant, customer, d["item_ref"], "anchor", CONFIDENT, role="anchor", group_id=gid,
                            decided_by="user", user_id=user_id)
        else:
            insert_decision(conn, tenant, customer, d["item_ref"], "unmatched", UNMATCHED, reason="dismissed_by_user",
                            decided_by="user", user_id=user_id)
    else:
        targets = choice.split("+")
        for t in targets:
            _active_group(conn, t)
        insert_decision(conn, tenant, customer, d["item_ref"], "link", CONFIDENT, role=d["role"], targets=targets,
                        data=d["data"], decided_by="user", user_id=user_id)
    renormalize(conn, tenant, customer)


def dismiss(conn, decision_id, user_id):
    """Kế toán đã xem item không thuộc nhóm nào và xác nhận bỏ qua."""
    d = _decision(conn, decision_id)
    if d["decision"] != "unmatched" or not d["needs_review"]:
        raise ReviewError("Chỉ bỏ qua được item đang chờ xem")
    tenant, customer = _ctx(d)
    _supersede_decision(conn, decision_id)
    insert_decision(conn, tenant, customer, d["item_ref"], "unmatched", UNMATCHED, reason="reviewed",
                    decided_by="user", user_id=user_id)
    renormalize(conn, tenant, customer)


def assign_item(conn, tenant_id, customer_id, item_ref: str, group_id, user_id, role: str | None = None):
    """Gán item vào một nhóm có sẵn, hoặc tách ra thành giao dịch riêng khi group_id là None."""
    active = conn.execute(
        "SELECT * FROM item_decision WHERE customer_id = %s AND item_ref = %s AND superseded_at IS NULL",
        (customer_id, item_ref)).fetchall()
    if not active:
        raise ReviewError("Item không tồn tại")
    is_attachment = "#" in item_ref
    if group_id is not None:
        g = _active_group(conn, group_id)
        if str(g["customer_id"]) != str(customer_id):
            raise ReviewError("Nhóm thuộc hộ khác")
    touched = set()
    for d in active:
        _supersede_decision(conn, d["id"])
        if d["decision"] == "anchor":
            touched.add(d["group_id"])
    for gid in touched:
        _supersede_empty_group(conn, gid)

    if group_id is None:
        kind = "document" if is_attachment else "self_declared"
        facts = {}
        if not is_attachment:
            msg = conn.execute("SELECT text FROM message WHERE id = %s", (item_ref,)).fetchone()
            amounts = find_amounts(msg["text"] or "")
            facts = {"type": None, "amount": amounts[0].value if len(amounts) == 1 else None, "relative": None}
        gid = insert_group(conn, tenant_id, customer_id, kind, CONFIDENT, facts=facts, created_by="user")
        insert_decision(conn, tenant_id, customer_id, item_ref, "anchor", CONFIDENT, role="anchor", group_id=gid,
                        decided_by="user", user_id=user_id)
    elif is_attachment:
        insert_decision(conn, tenant_id, customer_id, item_ref, "anchor", CONFIDENT, role="anchor",
                        group_id=group_id, decided_by="user", user_id=user_id)
    else:
        msg = conn.execute("SELECT text FROM message WHERE id = %s", (item_ref,)).fetchone()
        text = msg["text"] or ""
        amounts = [a.value for a in find_amounts(text)]
        role = role or ("amount_annotation" if amounts else "caption")
        data = {"amounts": amounts} if role == "amount_annotation" else {"text": text}
        insert_decision(conn, tenant_id, customer_id, item_ref, "link", CONFIDENT, role=role, targets=[group_id],
                        data=data, decided_by="user", user_id=user_id)
    renormalize(conn, tenant_id, customer_id)


def _reconfirm_anchors(conn, group_id, user_id):
    for d in _anchors(conn, group_id):
        if d["status"] != CONFIDENT:
            _supersede_decision(conn, d["id"])
            insert_decision(conn, d["tenant_id"], d["customer_id"], d["item_ref"], "anchor", CONFIDENT, role="anchor",
                            group_id=group_id, decided_by="user", user_id=user_id)


def accept_group(conn, group_id, user_id):
    """Nhóm mơ hồ (ví dụ 2 ảnh, không rõ 1 hay 2 hóa đơn): kế toán xác nhận là một giao dịch."""
    g = _active_group(conn, group_id)
    if g["status"] != AMBIGUOUS:
        raise ReviewError("Nhóm không ở trạng thái mơ hồ")
    conn.execute("UPDATE message_group SET status = 'CONFIDENT' WHERE id = %s", (group_id,))
    _reconfirm_anchors(conn, group_id, user_id)
    renormalize(conn, g["tenant_id"], g["customer_id"])


def split_group(conn, group_id, item_refs: list[str], user_id):
    """Tách các item đã chọn ra thành một giao dịch mới."""
    g = _active_group(conn, group_id)
    anchors = {d["item_ref"]: d for d in _anchors(conn, group_id)}
    if not item_refs or not set(item_refs) <= set(anchors) or set(item_refs) == set(anchors):
        raise ReviewError("Chọn một phần (không phải tất cả) các chứng từ của nhóm để tách")
    tenant, customer = g["tenant_id"], g["customer_id"]
    new_gid = insert_group(conn, tenant, customer, g["kind"], CONFIDENT, created_by="user")
    for ref in item_refs:
        _supersede_decision(conn, anchors[ref]["id"])
        insert_decision(conn, tenant, customer, ref, "anchor", CONFIDENT, role="anchor", group_id=new_gid,
                        decided_by="user", user_id=user_id)
    if g["status"] == AMBIGUOUS:
        conn.execute("UPDATE message_group SET status = 'CONFIDENT' WHERE id = %s", (group_id,))
    _reconfirm_anchors(conn, group_id, user_id)
    renormalize(conn, tenant, customer)
    return new_gid


def merge_groups(conn, group_ids: list, user_id):
    """Gộp nhiều nhóm vào nhóm đầu tiên. Liên kết trỏ tới nhóm bị gộp được trỏ lại."""
    if len(set(map(str, group_ids))) < 2:
        raise ReviewError("Chọn ít nhất hai nhóm để gộp")
    groups = [_active_group(conn, gid) for gid in group_ids]
    if len({str(g["customer_id"]) for g in groups}) != 1:
        raise ReviewError("Chỉ gộp được nhóm của cùng một hộ")
    target = groups[0]
    tenant, customer = target["tenant_id"], target["customer_id"]
    for g in groups[1:]:
        for d in _anchors(conn, g["id"]):
            _supersede_decision(conn, d["id"])
            insert_decision(conn, tenant, customer, d["item_ref"], "anchor", CONFIDENT, role="anchor",
                            group_id=target["id"], decided_by="user", user_id=user_id)
        links = conn.execute(
            "SELECT * FROM item_decision WHERE customer_id = %s AND superseded_at IS NULL AND decision = 'link'"
            " AND %s = ANY(target_group_ids)", (customer, g["id"])).fetchall()
        for l in links:
            _supersede_decision(conn, l["id"])
            new_targets = sorted({str(target["id"]) if t == g["id"] else str(t) for t in l["target_group_ids"]})
            insert_decision(conn, tenant, customer, l["item_ref"], "link", CONFIDENT, role=l["role"],
                            targets=new_targets, data=l["data"], decided_by="user", user_id=user_id)
        conn.execute("UPDATE message_group SET superseded_at = now() WHERE id = %s", (g["id"],))
    if target["status"] == AMBIGUOUS:
        conn.execute("UPDATE message_group SET status = 'CONFIDENT' WHERE id = %s", (target["id"],))
    _reconfirm_anchors(conn, target["id"], user_id)
    renormalize(conn, tenant, customer)


# --------------------------------------------------------------------------- bản ghi


def _validate(fields: dict) -> dict:
    out = {}
    for k, v in fields.items():
        if k not in EDITABLE_FIELDS:
            raise ReviewError(f"Không sửa được trường {k}")
        if k == "transaction_type" and v not in ("INCOME", "EXPENSE"):
            raise ReviewError("Loại phải là INCOME hoặc EXPENSE")
        if k == "amount" and (not isinstance(v, int) or isinstance(v, bool) or v <= 0):
            raise ReviewError("Số tiền phải là số nguyên dương (đồng)")
        if k in ("document_date", "posting_date") and v is not None:
            try:
                date.fromisoformat(v)
            except (TypeError, ValueError):
                raise ReviewError(f"{k} phải có dạng YYYY-MM-DD") from None
        if k == "description" and v is not None and not isinstance(v, str):
            raise ReviewError("Mô tả phải là chuỗi")
        out[k] = v
    return out


def _record(conn, record_id):
    r = conn.execute("SELECT * FROM record WHERE id = %s", (record_id,)).fetchone()
    if r is None:
        raise ReviewError("Bản ghi không tồn tại")
    if r["status"] != "ACTIVE":
        raise ReviewError("Bản ghi đã bị thay thế hoặc gộp")
    return r


def effective_fields(record) -> dict:
    ai = {k: (record["fields_ai"].get(k) or {}).get("value") for k in EDITABLE_FIELDS if k != "description"}
    ai["description"] = record["description"]
    return {**ai, **(record["fields_confirmed"] or {})}


def edit_record(conn, record_id, fields: dict, user_id):
    r = _record(conn, record_id)
    merged = {**(r["fields_confirmed"] or {}), **_validate(fields)}
    conn.execute("UPDATE record SET fields_confirmed = %s, updated_at = now() WHERE id = %s", (Jsonb(merged), record_id))


def confirm_record(conn, record_id, fields: dict | None, user_id):
    r = _record(conn, record_id)
    confirmed = {**(r["fields_confirmed"] or {}), **_validate(fields or {})}
    final = {**effective_fields(r), **confirmed}
    missing = [k for k in REQUIRED_TO_CONFIRM if final.get(k) is None]
    if missing:
        raise ReviewError("Cần nhập " + ", ".join(missing) + " trước khi xác nhận")
    conn.execute(
        "UPDATE record SET fields_confirmed = %s, review_required = false, review_reasons = '[]',"
        " confirmed_by = %s, confirmed_at = now(), updated_at = now() WHERE id = %s",
        (Jsonb(final), user_id, record_id))


