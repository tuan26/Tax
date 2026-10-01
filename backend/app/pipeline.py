"""Nối DB với lõi nghiệp vụ.

- load_document: dữ liệu gốc trong DB → tài liệu theo spec/messages.schema.json.
- load_result: quyết định đang hiệu lực trong DB → GroupingResult.
- process_customer: OCR (nếu có) → gom tin → ghi quyết định mới → tính lại bản ghi.
- renormalize: tính lại toàn bộ bản ghi của một hộ từ trạng thái quyết định hiện tại.

Quyết định đã có (của engine hay của kế toán) không bao giờ bị engine ghi đè.
"""

from __future__ import annotations

from uuid import UUID

from psycopg.types.json import Jsonb

from .domain.grouping import (AMBIGUOUS, CONFIDENT, ENGINE_VERSION, NONE_CANDIDATE, UNMATCHED, Group,
                              GroupingResult, Link, Unmatched, group_messages)
from .domain.normalize import normalize
from .extraction import run_ocr


def _iso(v):
    return v.isoformat() if v is not None and hasattr(v, "isoformat") else v


# --------------------------------------------------------------------------- load


def load_document(conn, customer_id) -> dict:
    cust = conn.execute("SELECT * FROM customer WHERE id = %s", (customer_id,)).fetchone()
    if cust is None:
        raise LookupError("customer")
    msgs = conn.execute(
        "SELECT * FROM message WHERE customer_id = %s ORDER BY received_at, sequence NULLS LAST, id",
        (customer_id,)).fetchall()
    atts = conn.execute(
        "SELECT a.* FROM attachment a JOIN message m ON m.id = a.message_id WHERE m.customer_id = %s "
        "ORDER BY a.created_at, a.external_id", (customer_id,)).fetchall()
    exts = conn.execute(
        "SELECT DISTINCT ON (e.attachment_id) e.* FROM extraction e JOIN attachment a ON a.id = e.attachment_id "
        "JOIN message m ON m.id = a.message_id WHERE m.customer_id = %s ORDER BY e.attachment_id, e.created_at DESC",
        (customer_id,)).fetchall()
    by_msg: dict = {}
    for a in atts:
        by_msg.setdefault(a["message_id"], []).append({
            "attachment_id": str(a["id"]), "kind": a["kind"], "file_name": a["file_name"],
            "mime_type": a["mime_type"], "size_bytes": a["size_bytes"], "sha256": a["sha256"],
            "storage_uri": a["storage_key"], "width": None, "height": None,
        })
    messages = []
    for m in msgs:
        d = {
            "message_id": str(m["id"]), "customer_id": str(customer_id), "conversation_id": m["conversation_id"],
            "sender_id": m["sender_id"], "sent_at": _iso(m["sent_at"]), "kind": m["kind"],
            "source_type": m["source_type"], "batch_id": str(m["batch_id"]) if m["batch_id"] else None,
            "business_date": _iso(m["business_date"]), "sequence": m["sequence"], "text": m["text"],
            "provenance": m["provenance"],
        }
        if m["id"] in by_msg:
            d["attachments"] = by_msg[m["id"]]
        messages.append(d)
    extractions = [{"extraction_id": str(e["id"]), "attachment_id": str(e["attachment_id"]),
                    "engine": e["engine"], **e["fields"]} for e in exts]
    return {
        "schema_version": "1.1",
        "dataset_id": str(customer_id),
        "customer": {"customer_id": str(customer_id), "name": cust["name"], "timezone": cust["timezone"],
                     "business_day_cutoff": cust["business_day_cutoff"]},
        "senders": [],
        "messages": messages,
        "extractions": extractions,
    }


def _active_decisions(conn, customer_id):
    return conn.execute(
        "SELECT * FROM item_decision WHERE customer_id = %s AND superseded_at IS NULL ORDER BY created_at, id",
        (customer_id,)).fetchall()


def load_result(conn, customer_id) -> GroupingResult:
    groups = conn.execute(
        "SELECT * FROM message_group WHERE customer_id = %s AND superseded_at IS NULL ORDER BY created_at, id",
        (customer_id,)).fetchall()
    decisions = _active_decisions(conn, customer_id)
    anchors: dict = {}
    links, unmatched = [], []
    for d in decisions:
        if d["decision"] == "anchor":
            anchors.setdefault(d["group_id"], []).append(d["item_ref"])
        elif d["decision"] == "link":
            links.append(Link(d["item_ref"], d["role"], d["status"],
                              targets=[str(t) for t in d["target_group_ids"]] if d["status"] == CONFIDENT else None,
                              candidates=d["candidates"], note=d["note"], data=d["data"]))
        else:
            unmatched.append(Unmatched(d["item_ref"], d["reason"], d["needs_review"]))
    out = []
    for g in groups:
        if not anchors.get(g["id"]):
            continue
        out.append(Group(str(g["id"]), g["status"], anchors[g["id"]], g["kind"], None, (), segment=g["segment"],
                         partition_candidates=g["partition_candidates"], facts=g["facts"]))
    return GroupingResult(out, links, unmatched)


# --------------------------------------------------------------------------- write decisions


def _split_ref(ref: str):
    msg, _, att = ref.partition("#")
    return UUID(msg), UUID(att) if att else None


def insert_decision(conn, tenant_id, customer_id, ref, decision, status, *, role=None, group_id=None,
                    targets=(), candidates=None, reason=None, needs_review=False, note=None, data=None,
                    decided_by="engine", user_id=None, run_id=None):
    msg_id, att_id = _split_ref(ref)
    return conn.execute(
        "INSERT INTO item_decision (tenant_id, customer_id, run_id, item_ref, message_id, attachment_id, decision, role,"
        " status, group_id, target_group_ids, candidates, reason, needs_review, note, data, decided_by, user_id)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (tenant_id, customer_id, run_id, ref, msg_id, att_id, decision, role, status, group_id,
         [UUID(str(t)) for t in targets], Jsonb(candidates) if candidates is not None else None, reason,
         needs_review, note, Jsonb(data or {}), decided_by, user_id)).fetchone()["id"]


def insert_group(conn, tenant_id, customer_id, kind, status, *, segment=None, facts=None, partitions=None,
                 created_by="engine", run_id=None):
    return conn.execute(
        "INSERT INTO message_group (tenant_id, customer_id, run_id, kind, status, segment, facts, partition_candidates,"
        " created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (tenant_id, customer_id, run_id, kind, status, segment, Jsonb(facts or {}),
         Jsonb(partitions) if partitions is not None else None, created_by)).fetchone()["id"]


def _apply_engine(conn, tenant_id, customer_id, doc, run_id):
    result = group_messages(doc)
    active = _active_decisions(conn, customer_id)
    prior_anchor = {d["item_ref"] for d in active if d["decision"] == "anchor"}
    decided_anchor = set(prior_anchor)
    decided_other = {d["item_ref"] for d in active if d["decision"] != "anchor"}
    existing = {}
    for g in load_result(conn, customer_id).groups:
        existing[(frozenset(g.anchor_items), g.segment)] = g.key

    label: dict[str, str] = {}
    for g in result.groups:
        k = (frozenset(g.anchor_items), g.segment)
        if k in existing:
            label[g.key] = existing[k]
            continue
        # Chỉ coi là xung đột với quyết định có từ trước lần chạy này. Trong cùng lần chạy, một tin
        # có thể là anchor của nhiều nhóm (ví dụ "bán 8tr4, nhập hàng 3tr").
        if any(a in prior_anchor for a in g.anchor_items):
            for a in g.anchor_items:
                if a not in decided_anchor and a not in decided_other:
                    insert_decision(conn, tenant_id, customer_id, a, "unmatched", UNMATCHED,
                                    reason="conflicts_with_existing_group", needs_review=True, run_id=run_id)
                    decided_other.add(a)
            continue
        facts = dict(g.facts)
        if "supersedes" in facts:
            facts["supersedes"] = label.get(facts["supersedes"])
        gid = insert_group(conn, tenant_id, customer_id, g.kind, g.status, segment=g.segment, facts=facts,
                           partitions=g.partition_candidates, run_id=run_id)
        label[g.key] = str(gid)
        for a in g.anchor_items:
            insert_decision(conn, tenant_id, customer_id, a, "anchor", g.status, role="anchor", group_id=gid,
                            run_id=run_id)
            decided_anchor.add(a)
    for l in result.links:
        if l.item in decided_other:
            continue
        status, targets, candidates = l.status, [], None
        if l.status == CONFIDENT:
            targets = [label.get(t) for t in l.targets]
            if None in targets:
                status, targets = AMBIGUOUS, []
                candidates = [label[t] for t in l.targets if t in label] or None
        if status == AMBIGUOUS and candidates is None:
            candidates = []
            for c in l.candidates or []:
                if c == NONE_CANDIDATE:
                    candidates.append(c)
                    continue
                parts = [label.get(p) for p in c.split("+")]
                if None not in parts:
                    candidates.append("+".join(parts))
        if status == AMBIGUOUS and not [c for c in candidates if c != NONE_CANDIDATE]:
            insert_decision(conn, tenant_id, customer_id, l.item, "unmatched", UNMATCHED,
                            reason="candidates_unavailable", needs_review=True, run_id=run_id)
        else:
            insert_decision(conn, tenant_id, customer_id, l.item, "link", status, role=l.role, targets=targets,
                            candidates=candidates if status == AMBIGUOUS else None, note=l.note, data=l.data,
                            run_id=run_id)
        decided_other.add(l.item)
    for u in result.unmatched:
        if u.item in decided_other or u.item in decided_anchor:
            continue
        insert_decision(conn, tenant_id, customer_id, u.item, "unmatched", UNMATCHED, reason=u.reason,
                        needs_review=u.needs_review, run_id=run_id)
        decided_other.add(u.item)


# --------------------------------------------------------------------------- records


def renormalize(conn, tenant_id, customer_id):
    doc = load_document(conn, customer_id)
    result = load_result(conn, customer_id)
    records = normalize(doc, result)
    rows = {str(r["group_id"]): r for r in conn.execute("SELECT * FROM record WHERE customer_id = %s",
                                                        (customer_id,)).fetchall()}
    active_groups = {g.key for g in result.groups}
    ids: dict[str, UUID] = {}
    for rec in records:
        fields_ai = {k: {"value": d.value, "candidates": d.candidates} for k, d in rec.decisions.items()}
        confidence = {k: d.confidence for k, d in rec.decisions.items()}
        row = rows.get(rec.group_key)
        values = dict(fields_ai=Jsonb(fields_ai), decision_confidence=Jsonb(confidence),
                      evidence_items=Jsonb(rec.evidence_items), evidence_kind=rec.evidence_kind,
                      sent_date=rec.sent_date, description=rec.description, status=rec.status)
        if row is None:
            ids[rec.key] = conn.execute(
                "INSERT INTO record (tenant_id, customer_id, group_id, fields_ai, decision_confidence, evidence_items,"
                " evidence_kind, sent_date, review_required, review_reasons, description, status)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (tenant_id, customer_id, UUID(rec.group_key), values["fields_ai"], values["decision_confidence"],
                 values["evidence_items"], rec.evidence_kind, rec.sent_date, rec.review_required,
                 Jsonb(rec.review_reasons), rec.description, rec.status)).fetchone()["id"]
            continue
        ids[rec.key] = row["id"]
        review, reasons = rec.review_required, list(rec.review_reasons)
        if row["confirmed_at"] is not None:
            if row["fields_ai"] != fields_ai or row["evidence_items"] != rec.evidence_items:
                review, reasons = True, sorted(set(reasons) | {"new_evidence_after_confirm"})
            else:
                review, reasons = row["review_required"], row["review_reasons"]
        changed = (row["fields_ai"] != fields_ai or row["decision_confidence"] != confidence
                   or row["evidence_items"] != rec.evidence_items or row["review_required"] != review
                   or row["review_reasons"] != reasons or row["status"] != rec.status
                   or row["description"] != rec.description or row["evidence_kind"] != rec.evidence_kind)
        if changed:
            conn.execute(
                "UPDATE record SET fields_ai=%s, decision_confidence=%s, evidence_items=%s, evidence_kind=%s,"
                " sent_date=%s, review_required=%s, review_reasons=%s, description=%s, status=%s, updated_at=now()"
                " WHERE id=%s",
                (values["fields_ai"], values["decision_confidence"], values["evidence_items"], rec.evidence_kind,
                 rec.sent_date, review, Jsonb(reasons), rec.description, rec.status, row["id"]))
    for rec in records:
        if rec.supersedes:
            target = ids.get(rec.supersedes)
            conn.execute("UPDATE record SET supersedes_id=%s WHERE id=%s AND supersedes_id IS DISTINCT FROM %s",
                         (target, ids[rec.key], target))
    for gk, row in rows.items():
        if gk not in active_groups and row["status"] == "ACTIVE":
            conn.execute("UPDATE record SET status='MERGED', review_required=false, updated_at=now() WHERE id=%s",
                         (row["id"],))
    from .findings import run_rules  # tránh vòng import

    run_rules(conn, tenant_id, customer_id)


# --------------------------------------------------------------------------- entry


def process_customer(conn, tenant_id, customer_id, ocr=None, storage=None, ocr_timeout_seconds=20.0):
    """Chạy trong transaction có actor_kind = engine.

    OCR lỗi ở một ảnh chỉ ảnh hưởng ảnh đó: lần thử được ghi lại với status failed, ảnh vẫn được
    gom và bản ghi của nó vào hàng chờ duyệt. Lỗi OCR không bao giờ làm hỏng cả lượt xử lý.
    """
    if ocr is not None and storage is not None and ocr.name != "none":
        pending = conn.execute(
            "SELECT a.* FROM attachment a JOIN message m ON m.id = a.message_id LEFT JOIN extraction e"
            " ON e.attachment_id = a.id WHERE m.customer_id = %s AND e.id IS NULL", (customer_id,)).fetchall()
        for a in pending:
            outcome = run_ocr(ocr, storage.get(a["storage_key"]), a["mime_type"], ocr_timeout_seconds)
            conn.execute("INSERT INTO extraction (tenant_id, attachment_id, engine, fields) VALUES (%s,%s,%s,%s)",
                         (tenant_id, a["id"], ocr.name, Jsonb(outcome.to_row(ocr.name))))
    doc = load_document(conn, customer_id)
    run_id = conn.execute(
        "INSERT INTO grouping_run (tenant_id, customer_id, engine_version, message_count) VALUES (%s,%s,%s,%s)"
        " RETURNING id", (tenant_id, customer_id, ENGINE_VERSION, len(doc["messages"]))).fetchone()["id"]
    _apply_engine(conn, tenant_id, customer_id, doc, run_id)
    renormalize(conn, tenant_id, customer_id)
    return run_id
