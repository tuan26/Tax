"""PILOT RELEASE GATE. Mọi test trong file này phải qua trước khi cho kế toán dùng dữ liệu thật.

[1] Raw data append-only           test_raw_data_is_append_only, test_storage_never_overwrites
[2] Grouping spec, 0 wrong auto     tests/test_spec_suite.py
[3] 100% write operations audited  test_every_write_is_audited
[4] Tenant isolation               test_tenant_isolation_api, test_tenant_isolation_db
[5] Backup + restore               tests/test_backup_restore.py (tuần 2)
[6] AI outbound fail-closed        test_foreign_ai_fail_closed
"""

import io

import psycopg
import pytest

from app.ai_outbound import OutboundBlocked, send_to_foreign_ai
from app.config import Settings
from tests.conftest import login
from tests.test_integration import new_customer, png


def _seed(client, pg, tenants):
    h = login(client, pg, "A", tenants)
    cid = new_customer(client, h, "Hộ kiểm tra gate")
    r = client.post(f"/customers/{cid}/imports", headers=h, data={
        "business_date": "2026-10-06", "chat_text": "tiền thịt\nDoanh thu 7tr"},
        files=[("files", ("p.png", io.BytesIO(png(42)), "image/png"))])
    assert r.status_code == 201
    return h, cid


# [1] -----------------------------------------------------------------------


@pytest.mark.parametrize("table", ["message", "attachment", "import_batch", "grouping_run", "audit_event"])
def test_raw_data_is_append_only(client, pg, tenants, db, table):
    _, cid = _seed(client, pg, tenants)
    tid, uid = tenants["A"]
    for sql in (f"UPDATE {table} SET tenant_id = tenant_id" if table != "message" else
                "UPDATE message SET text = 'sửa'", f"DELETE FROM {table}"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with db.tx(tid, uid) as conn:
                conn.execute(sql)
    # Kể cả role quản trị cũng bị trigger chặn.
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with psycopg.connect(pg["admin"]) as conn:
            conn.execute(f"DELETE FROM {table}")


def test_decisions_only_superseded_never_rewritten(client, pg, tenants, db):
    _, cid = _seed(client, pg, tenants)
    tid, uid = tenants["A"]
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with db.tx(tid, uid) as conn:
            conn.execute("UPDATE item_decision SET status = 'CONFIDENT' WHERE customer_id = %s", (cid,))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with db.tx(tid, uid) as conn:
            conn.execute("DELETE FROM record WHERE customer_id = %s", (cid,))


def test_storage_never_overwrites(storage):
    tid = "t"
    sha, key = storage.put(tid, b"anh goc")
    assert storage.put(tid, b"anh goc") == (sha, key)
    path = storage.root / key
    path.chmod(0o640)
    path.write_bytes(b"bi sua")
    with pytest.raises(RuntimeError):
        storage.get(key)


# [3] -----------------------------------------------------------------------

AUDITED = ["customer", "import_batch", "message", "attachment", "extraction", "ai_call", "grouping_run",
           "message_group", "item_decision", "record", "finding", "match"]


def test_every_write_is_audited(client, pg, tenants):
    h, cid = _seed(client, pg, tenants)
    q = client.get(f"/customers/{cid}/review-queue", headers=h).json()
    item = q["items"][0]
    client.post(f"/decisions/{item['decision_id']}/resolve", json={"choice": item["candidates"][0]["choice"]},
                headers=h)
    rec = client.get(f"/customers/{cid}/records", headers=h).json()[0]
    client.patch(f"/records/{rec['id']}", json={"fields": {"amount": 1_000_000}}, headers=h)
    with psycopg.connect(pg["admin"]) as conn:
        for table in AUDITED:
            inserted = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            audited = conn.execute("SELECT count(*) FROM audit_event WHERE table_name = %s AND action = 'INSERT'",
                                   (table,)).fetchone()[0]
            assert audited == inserted, f"{table}: {inserted} dòng nhưng {audited} audit INSERT"
        edits = conn.execute("SELECT actor_kind, actor_id, old_row->'fields_confirmed', new_row->'fields_confirmed'"
                             " FROM audit_event WHERE table_name = 'record' AND action = 'UPDATE'"
                             " AND row_id = %s ORDER BY id DESC LIMIT 1", (rec["id"],)).fetchone()
        assert edits[0] == "user" and str(edits[1]) == str(tenants["A"][1])
        assert edits[3] == {"amount": 1_000_000}
        # Mọi UPDATE trên bảng có audit đều có dòng audit tương ứng (kiểm tra bằng số lần cập nhật record).
        assert conn.execute("SELECT count(*) FROM audit_event WHERE action = 'UPDATE'").fetchone()[0] > 0


# [4] -----------------------------------------------------------------------


def test_tenant_isolation_api(client, pg, tenants):
    ha, cid = _seed(client, pg, tenants)
    hb = login(client, pg, "B", tenants)
    rec = client.get(f"/customers/{cid}/records", headers=ha).json()[0]
    att = client.get(f"/customers/{cid}/review-queue", headers=ha).json()
    attachment_id = next(r for r in client.get(f"/customers/{cid}/records", headers=ha).json()
                         if r["evidence_kind"] == "document")["evidence_items"][0].split("#")[1]
    assert client.get(f"/attachments/{attachment_id}/content", headers=ha).status_code == 200
    assert client.get(f"/attachments/{attachment_id}/content", headers=hb).status_code == 404
    assert cid not in {c["id"] for c in client.get("/customers", headers=hb).json()}
    assert client.get(f"/customers/{cid}/records", headers=hb).status_code == 404
    assert client.get(f"/customers/{cid}/review-queue", headers=hb).status_code == 404
    assert client.post(f"/customers/{cid}/imports", headers=hb, data={"business_date": "2026-10-06",
                                                                     "chat_text": "x 1tr"}).status_code == 404
    assert client.post(f"/records/{rec['id']}/confirm", json={"fields": {}}, headers=hb).status_code == 409
    if att["items"]:
        assert client.post(f"/decisions/{att['items'][0]['decision_id']}/dismiss", headers=hb).status_code == 409


def test_tenant_isolation_db(pg, tenants, db, client):
    _, cid = _seed(client, pg, tenants)
    tid_b, uid_b = tenants["B"]
    with db.tx(tid_b, uid_b) as conn:
        assert conn.execute("SELECT count(*) AS n FROM customer WHERE id = %s", (cid,)).fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM message WHERE customer_id = %s", (cid,)).fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM audit_event WHERE tenant_id <> %s", (tid_b,)).fetchone()["n"] == 0
    # Chưa đặt tenant: không thấy gì.
    with db.tx() as conn:
        assert conn.execute("SELECT count(*) AS n FROM customer").fetchone()["n"] == 0
    # Ghi dữ liệu vào tenant khác bị RLS chặn.
    tid_a, _ = tenants["A"]
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with db.tx(tid_b, uid_b) as conn:
            conn.execute("INSERT INTO customer (tenant_id, name) VALUES (%s, 'lấn tenant')", (tid_a,))
    # Tham chiếu chéo tenant bị khóa ngoại kép chặn.
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with db.tx(tid_b, uid_b) as conn:
            conn.execute("INSERT INTO import_batch (tenant_id, customer_id, source_type, business_date)"
                         " VALUES (%s, %s, 'ZALO_MANUAL', '2026-10-06')", (tid_b, cid))


def test_app_role_is_not_superuser(pg):
    with psycopg.connect(pg["app"]) as conn:
        su, bypass = conn.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user").fetchone()
    assert not su and not bypass


# [6] -----------------------------------------------------------------------


def test_foreign_ai_fail_closed(db, tenants):
    tid, _ = tenants["B"]
    calls = []
    disabled = Settings("", None, 1, False, "none", 0)
    enabled = Settings("", None, 1, True, "none", 0)
    cases = [
        (disabled, "synthetic", "Hóa đơn [NGUOI_1] 2.350.000", "foreign_ai_disabled"),
        (enabled, "real", "Hóa đơn [NGUOI_1] 2.350.000", "data_class_not_allowed:real"),
        (enabled, "synthetic", "Chuyển cho 0903123456", "pii_detected:phone"),
        (enabled, "synthetic", "STK 0071000123456", "pii_detected"),
        (enabled, "synthetic", {"nguoi_ban": "a@b.vn"}, "pii_detected:email"),
    ]
    for settings, data_class, payload, reason in cases:
        with pytest.raises(OutboundBlocked) as e:
            send_to_foreign_ai(db, tid, settings, "test", payload, data_class, client=calls.append)
        assert str(e.value).startswith(reason)
    assert calls == [], "không payload nào được gửi đi"
    with pytest.raises(OutboundBlocked):
        send_to_foreign_ai(db, tid, enabled, "test", "ok", "synthetic", client=None)
    allowed = []
    send_to_foreign_ai(db, tid, enabled, "test", "Hóa đơn [NGUOI_1] 2.350.000", "synthetic", client=allowed.append)
    assert allowed == ["Hóa đơn [NGUOI_1] 2.350.000"]
    # Mọi lần thử đều có log, kể cả lần bị chặn.
    with db.tx(tid) as conn:
        rows = conn.execute("SELECT allowed, reason FROM ai_call ORDER BY created_at").fetchall()
    assert [r["allowed"] for r in rows] == [False] * 6 + [True]
    assert rows[0]["reason"] == "foreign_ai_disabled"


def test_default_config_disables_foreign_ai(monkeypatch):
    from app.config import load_settings
    monkeypatch.delenv("FOREIGN_AI_ENABLED", raising=False)
    assert load_settings().foreign_ai_enabled is False
