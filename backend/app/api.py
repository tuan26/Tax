"""HTTP API cho pilot. Mọi truy vấn chạy trong transaction gắn tenant (RLS)."""


import logging
from datetime import date, datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Response, UploadFile
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from . import review
from .pipeline import process_customer
from .security import new_token, token_hash, verify_password

log = logging.getLogger("tax")

ALLOWED_MIME = {"image/jpeg": "image", "image/png": "image", "image/webp": "image", "image/heic": "image",
                "application/pdf": "pdf"}
MANUAL_SOURCES = {"ZALO_MANUAL", "FILE_UPLOAD", "MANUAL_ENTRY"}
SOURCE_LABEL = {"ZALO_MANUAL": "zalo_pc_manual", "FILE_UPLOAD": "upload", "MANUAL_ENTRY": "upload"}


class Ctx(BaseModel):
    tenant_id: UUID
    user_id: UUID


class LoginIn(BaseModel):
    email: str
    password: str


class CustomerIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    business_day_cutoff: str = Field(default="04:00", pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")


class ResolveIn(BaseModel):
    choice: str


class AssignIn(BaseModel):
    item_ref: str
    group_id: UUID | None = None
    role: str | None = None


class SplitIn(BaseModel):
    item_refs: list[str]


class MergeIn(BaseModel):
    group_ids: list[UUID]


class ExcludeIn(BaseModel):
    reason: str


class RecordFieldsIn(BaseModel):
    fields: dict = Field(default_factory=dict)


class ActivityIn(BaseModel):
    customer_id: UUID | None = None
    screen: str = Field(max_length=50)


def create_app(settings, db, storage, ocr) -> FastAPI:
    app = FastAPI(title="Tax check pilot", version="0.1")

    # ------------------------------------------------------------------ auth

    def ctx(authorization: Annotated[str | None, Header()] = None) -> Ctx:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Cần đăng nhập")
        with db.tx() as conn:
            row = conn.execute("SELECT * FROM session_lookup(%s)", (token_hash(authorization[7:]),)).fetchone()
        if row is None:
            raise HTTPException(401, "Phiên đăng nhập hết hạn")
        return Ctx(tenant_id=row["tenant_id"], user_id=row["user_id"])

    Auth = Annotated[Ctx, Depends(ctx)]

    def tx(c: Ctx, actor_kind="user"):
        return db.tx(c.tenant_id, c.user_id, actor_kind)

    def review_call(c: Ctx, fn, *args):
        try:
            with tx(c) as conn:
                return fn(conn, *args)
        except review.ReviewError as e:
            raise HTTPException(409, str(e)) from None

    @app.post("/auth/login")
    def login(body: LoginIn):
        with db.tx() as conn:
            row = conn.execute("SELECT * FROM auth_lookup(%s)", (body.email,)).fetchone()
        if row is None or not verify_password(body.password, row["password_hash"]):
            raise HTTPException(401, "Sai email hoặc mật khẩu")
        token, digest = new_token()
        expires = datetime.now(timezone.utc) + timedelta(hours=settings.session_hours)
        with db.tx(row["tenant_id"], row["user_id"]) as conn:
            conn.execute("INSERT INTO user_session (token_hash, tenant_id, user_id, expires_at) VALUES (%s,%s,%s,%s)",
                         (digest, row["tenant_id"], row["user_id"], expires))
        return {"token": token, "expires_at": expires, "display_name": row["display_name"]}

    @app.post("/auth/logout")
    def logout(c: Auth, authorization: Annotated[str, Header()]):
        with tx(c) as conn:
            conn.execute("UPDATE user_session SET revoked_at = now() WHERE token_hash = %s",
                         (token_hash(authorization[7:]),))
        return {"ok": True}

    @app.get("/me")
    def me(c: Auth):
        with tx(c) as conn:
            return conn.execute("SELECT id, email, display_name FROM app_user WHERE id = %s", (c.user_id,)).fetchone()

    # ------------------------------------------------------------------ hộ

    def _customer(conn, customer_id):
        row = conn.execute("SELECT * FROM customer WHERE id = %s", (customer_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Không tìm thấy hộ")
        return row

    @app.get("/customers")
    def customers(c: Auth):
        with tx(c) as conn:
            return conn.execute("""
                SELECT c.id, c.name, c.business_day_cutoff,
                  (SELECT count(*) FROM item_decision d WHERE d.customer_id = c.id AND d.superseded_at IS NULL
                     AND (d.status = 'AMBIGUOUS' OR (d.decision = 'unmatched' AND d.needs_review))) AS pending_items,
                  (SELECT count(*) FROM record r WHERE r.customer_id = c.id AND r.status = 'ACTIVE'
                     AND r.review_required) AS pending_records
                FROM customer c ORDER BY c.name""").fetchall()

    @app.get("/customers/{customer_id}")
    def get_customer(customer_id: UUID, c: Auth):
        with tx(c) as conn:
            return _customer(conn, customer_id)

    @app.post("/customers", status_code=201)
    def create_customer(body: CustomerIn, c: Auth):
        with tx(c) as conn:
            return conn.execute(
                "INSERT INTO customer (tenant_id, name, business_day_cutoff) VALUES (%s,%s,%s) RETURNING *",
                (c.tenant_id, body.name, body.business_day_cutoff)).fetchone()

    # ------------------------------------------------------------------ nhập dữ liệu

    def _run_processing(c: Ctx, customer_id, job_id):
        try:
            with tx(c, actor_kind="engine") as conn:
                conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (str(customer_id),))
                process_customer(conn, c.tenant_id, customer_id, ocr, storage, settings.ocr_timeout_seconds)
                conn.execute("UPDATE processing_job SET status='done', finished_at=now() WHERE id=%s", (job_id,))
            return "done"
        except Exception as e:  # dữ liệu gốc đã lưu; worker sẽ thử lại
            log.exception("processing failed")
            with tx(c, actor_kind="system") as conn:
                conn.execute("UPDATE processing_job SET status='failed', error=%s, finished_at=now() WHERE id=%s",
                             (repr(e)[:2000], job_id))
            return "failed"

    @app.post("/customers/{customer_id}/imports", status_code=201)
    async def create_import(
        customer_id: UUID,
        c: Auth,
        business_date: Annotated[date, Form()],
        source_type: Annotated[str, Form()] = "ZALO_MANUAL",
        chat_text: Annotated[str | None, Form()] = None,
        split_lines: Annotated[bool, Form()] = True,
        files: Annotated[list[UploadFile] | None, File()] = None,
    ):
        if source_type not in MANUAL_SOURCES:
            raise HTTPException(422, "Nguồn nhập tay không hợp lệ")
        uploads = []
        for f in files or []:
            mime = (f.content_type or "").split(";")[0]
            if mime not in ALLOWED_MIME:
                raise HTTPException(415, f"{f.filename}: chỉ nhận ảnh JPEG, PNG, WEBP, HEIC hoặc PDF")
            data = await f.read()
            if len(data) > settings.max_upload_bytes:
                raise HTTPException(413, f"{f.filename}: file quá lớn")
            uploads.append((f.filename, mime, data))
        lines = []
        if chat_text and chat_text.strip():
            lines = [l.strip() for l in chat_text.splitlines() if l.strip()] if split_lines else [chat_text.strip()]
        if not uploads and not lines:
            raise HTTPException(422, "Đợt nhập không có ảnh hay nội dung nào")

        received = datetime.now(timezone.utc).isoformat()
        with tx(c) as conn:
            _customer(conn, customer_id)
            batch_id = conn.execute(
                "INSERT INTO import_batch (tenant_id, customer_id, source_type, business_date, created_by)"
                " VALUES (%s,%s,%s,%s,%s) RETURNING id",
                (c.tenant_id, customer_id, source_type, business_date, c.user_id)).fetchone()["id"]
            seq = 0
            for filename, mime, data in uploads:
                sha, key = storage.put(c.tenant_id, data)
                kind = ALLOWED_MIME[mime]
                msg_id = conn.execute(
                    "INSERT INTO message (tenant_id, customer_id, batch_id, external_id, conversation_id, sender_id,"
                    " sent_at, business_date, sequence, kind, text, source_type, provenance)"
                    " VALUES (%s,%s,%s,%s,%s,NULL,NULL,%s,%s,%s,NULL,%s,%s) RETURNING id",
                    (c.tenant_id, customer_id, batch_id, f"{batch_id}:{seq}", f"batch:{batch_id}", business_date, seq,
                     "image" if kind == "image" else "file", source_type,
                     Jsonb({"source": SOURCE_LABEL[source_type], "source_message_id": None, "received_at": received,
                            "collected_by": str(c.user_id), "raw_payload": None, "raw_payload_sha256": None,
                            "original_filename": filename}))).fetchone()["id"]
                conn.execute(
                    "INSERT INTO attachment (tenant_id, message_id, external_id, kind, mime_type, file_name,"
                    " size_bytes, sha256, storage_key) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (c.tenant_id, msg_id, str(uuid4()), kind, mime, filename, len(data), sha, key))
                seq += 1
            for line in lines:
                conn.execute(
                    "INSERT INTO message (tenant_id, customer_id, batch_id, external_id, conversation_id, sender_id,"
                    " sent_at, business_date, sequence, kind, text, source_type, provenance)"
                    " VALUES (%s,%s,%s,%s,%s,NULL,NULL,%s,%s,'text',%s,%s,%s)",
                    (c.tenant_id, customer_id, batch_id, f"{batch_id}:{seq}", f"batch:{batch_id}", business_date, seq,
                     line, source_type,
                     Jsonb({"source": SOURCE_LABEL[source_type], "source_message_id": None, "received_at": received,
                            "collected_by": str(c.user_id), "raw_payload": None, "raw_payload_sha256": None})))
                seq += 1
            job_id = conn.execute("INSERT INTO processing_job (tenant_id, customer_id) VALUES (%s,%s) RETURNING id",
                                  (c.tenant_id, customer_id)).fetchone()["id"]
        status = _run_processing(c, customer_id, job_id)
        return {"batch_id": batch_id, "messages": seq, "processing": status}

    @app.get("/attachments/{attachment_id}/content")
    def attachment_content(attachment_id: UUID, c: Auth):
        with tx(c) as conn:
            a = conn.execute("SELECT * FROM attachment WHERE id = %s", (attachment_id,)).fetchone()
        if a is None:
            raise HTTPException(404, "Không tìm thấy file")
        return Response(storage.get(a["storage_key"]), media_type=a["mime_type"],
                        headers={"Cache-Control": "private, max-age=3600"})

    # ------------------------------------------------------------------ hàng chờ duyệt

    @app.get("/customers/{customer_id}/review-queue")
    def review_queue(customer_id: UUID, c: Auth):
        with tx(c) as conn:
            _customer(conn, customer_id)
            return build_review_queue(conn, customer_id)

    @app.post("/decisions/{decision_id}/resolve")
    def resolve(decision_id: UUID, body: ResolveIn, c: Auth):
        review_call(c, review.resolve_ambiguous, decision_id, body.choice, c.user_id)
        return {"ok": True}

    @app.post("/decisions/{decision_id}/dismiss")
    def dismiss(decision_id: UUID, c: Auth):
        review_call(c, review.dismiss, decision_id, c.user_id)
        return {"ok": True}

    @app.post("/customers/{customer_id}/assign")
    def assign(customer_id: UUID, body: AssignIn, c: Auth):
        def run(conn):
            _customer(conn, customer_id)
            review.assign_item(conn, c.tenant_id, customer_id, body.item_ref, body.group_id, c.user_id, body.role)
        review_call(c, run)
        return {"ok": True}

    @app.post("/groups/{group_id}/accept")
    def accept(group_id: UUID, c: Auth):
        review_call(c, review.accept_group, group_id, c.user_id)
        return {"ok": True}

    @app.post("/groups/{group_id}/split")
    def split(group_id: UUID, body: SplitIn, c: Auth):
        return {"group_id": review_call(c, review.split_group, group_id, body.item_refs, c.user_id)}

    @app.post("/groups/{group_id}/exclude")
    def exclude(group_id: UUID, body: ExcludeIn, c: Auth):
        review_call(c, review.exclude_group, group_id, body.reason, c.user_id)
        return {"ok": True}

    @app.post("/groups/merge")
    def merge(body: MergeIn, c: Auth):
        review_call(c, review.merge_groups, body.group_ids, c.user_id)
        return {"ok": True}

    # ------------------------------------------------------------------ bản ghi

    @app.get("/customers/{customer_id}/records")
    def records(customer_id: UUID, c: Auth, date_from: date | None = None, date_to: date | None = None):
        with tx(c) as conn:
            _customer(conn, customer_id)
            rows = conn.execute("SELECT * FROM record WHERE customer_id = %s AND status = 'ACTIVE' ORDER BY created_at",
                                (customer_id,)).fetchall()
            ev = evidence_index(conn, customer_id)
        out = []
        for r in rows:
            eff = review.effective_fields(r)
            posting = eff.get("posting_date")
            if posting and ((date_from and posting < date_from.isoformat()) or (date_to and posting > date_to.isoformat())):
                continue
            out.append(record_view(r, ev))
        return out

    @app.patch("/records/{record_id}")
    def edit(record_id: UUID, body: RecordFieldsIn, c: Auth):
        review_call(c, review.edit_record, record_id, body.fields, c.user_id)
        return {"ok": True}

    @app.post("/records/{record_id}/confirm")
    def confirm(record_id: UUID, body: RecordFieldsIn, c: Auth):
        review_call(c, review.confirm_record, record_id, body.fields, c.user_id)
        return {"ok": True}

    @app.post("/activity", status_code=204)
    def activity(body: ActivityIn, c: Auth):
        with tx(c) as conn:
            conn.execute("INSERT INTO activity_log (tenant_id, user_id, customer_id, screen) VALUES (%s,%s,%s,%s)",
                         (c.tenant_id, c.user_id, body.customer_id, body.screen))

    return app


def evidence_index(conn, customer_id) -> dict:
    """item_ref → mô tả bằng chứng gốc để giao diện hiển thị ảnh và tin nhắn."""
    out = {}
    for m in conn.execute("SELECT id, kind, text, sent_at, business_date, source_type FROM message"
                          " WHERE customer_id = %s", (customer_id,)).fetchall():
        out[str(m["id"])] = {"ref": str(m["id"]), "kind": "text", "text": m["text"], "sent_at": m["sent_at"],
                             "business_date": m["business_date"], "source_type": m["source_type"]}
    for a in conn.execute("SELECT a.id, a.message_id, a.mime_type, a.file_name, m.text, m.sent_at, m.business_date,"
                          " m.source_type FROM attachment a JOIN message m ON m.id = a.message_id"
                          " WHERE m.customer_id = %s", (customer_id,)).fetchall():
        ref = f"{a['message_id']}#{a['id']}"
        out[ref] = {"ref": ref, "kind": "attachment", "attachment_id": a["id"], "mime_type": a["mime_type"],
                    "file_name": a["file_name"], "text": a["text"], "sent_at": a["sent_at"],
                    "business_date": a["business_date"], "source_type": a["source_type"]}
    return out


def record_view(r, evidence: dict | None = None) -> dict:
    return {
        "id": r["id"], "group_id": r["group_id"], "fields": review.effective_fields(r), "fields_ai": r["fields_ai"],
        "decision_confidence": r["decision_confidence"], "confirmed": r["confirmed_at"] is not None,
        "review_required": r["review_required"], "review_reasons": r["review_reasons"],
        "evidence_items": r["evidence_items"], "evidence_kind": r["evidence_kind"], "sent_date": r["sent_date"],
        "status": r["status"], "supersedes_id": r["supersedes_id"],
        "evidence": [evidence[e] for e in r["evidence_items"] if e in evidence] if evidence is not None else None,
    }


def build_review_queue(conn, customer_id) -> dict:
    decisions = conn.execute(
        "SELECT d.*, m.text, m.kind AS message_kind, m.sent_at, m.business_date, m.source_type,"
        " (SELECT mime_type FROM attachment a WHERE a.id = d.attachment_id) AS mime_type FROM item_decision d"
        " JOIN message m ON m.id = d.message_id WHERE d.customer_id = %s AND d.superseded_at IS NULL"
        " AND (d.status = 'AMBIGUOUS' OR (d.decision = 'unmatched' AND d.needs_review))"
        " ORDER BY m.sent_at NULLS LAST, m.business_date, m.sequence", (customer_id,)).fetchall()
    groups = conn.execute(
        "SELECT * FROM message_group WHERE customer_id = %s AND superseded_at IS NULL AND status = 'AMBIGUOUS'",
        (customer_id,)).fetchall()
    records = conn.execute(
        "SELECT * FROM record WHERE customer_id = %s AND status = 'ACTIVE' AND review_required ORDER BY created_at",
        (customer_id,)).fetchall()
    ev = evidence_index(conn, customer_id)
    group_records = {str(r["group_id"]): record_view(r, ev) for r in conn.execute(
        "SELECT * FROM record WHERE customer_id = %s AND status = 'ACTIVE'", (customer_id,)).fetchall()}
    items = []
    for d in decisions:
        items.append({
            "type": "ambiguous_link" if d["decision"] == "link" else (
                "ambiguous_anchor" if d["decision"] == "anchor" else "unmatched"),
            "decision_id": d["id"], "item_ref": d["item_ref"], "role": d["role"], "reason": d["reason"],
            "text": d["text"], "attachment_id": d["attachment_id"], "mime_type": d["mime_type"],
            "sent_at": d["sent_at"],
            "business_date": d["business_date"], "source_type": d["source_type"],
            "candidates": [{"choice": cand, "records": [group_records.get(p) for p in cand.split("+")]
                            if cand != "NONE" else []} for cand in (d["candidates"] or [])],
        })
    return {
        "items": [i for i in items if i["type"] != "ambiguous_anchor"],
        "groups": [{"group_id": g["id"], "partition_candidates": g["partition_candidates"],
                    "record": group_records.get(str(g["id"]))} for g in groups],
        "records": [record_view(r, ev) for r in records],
    }


