"""Cô lập tenant theo spec AC-E1-017 và Constitution 3.14.

Mọi kiểm tra chạy bằng role đăng nhập của ứng dụng (không superuser, không BYPASSRLS), trên dữ liệu giả
lập. Tenant "C" là bên thử truy cập; tenant "D" là bên bị nhắm tới, có dữ liệu ở mọi bảng. Sau mỗi
thử nghiệm, dữ liệu của D được so với ảnh chụp ban đầu để chắc rằng không có gì bị đổi.
"""

import hashlib
import io
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.ai_outbound import OutboundBlocked, send_to_foreign_ai
from app.api import create_app
from app.config import Settings
from app.extraction import FixtureOcr, NoOcr
from app.storage import ImmutableStorage
from app.worker import run_once
from tests.conftest import PASSWORD, make_tenant
from tests.test_integration import png

# Bảng không chứa dữ liệu tenant. Bảng mới có tenant_id sẽ tự được đưa vào kiểm tra.
NON_TENANT_TABLES = {"schema_migration"}

# Hàm chạy với quyền của người tạo (SECURITY DEFINER) và role duy nhất được gọi mỗi hàm.
SECURITY_DEFINER_GRANTS = {
    "auth_lookup": {"tax_auth"},
    "session_lookup": {"tax_app"},
    "claim_job": {"tax_worker"},
}

SEEDS = {"transfer": 230, "invoice": 231}


def _sv(v, c=0.97):
    return {"value": v, "confidence": c}


def _admin(pg):
    return psycopg.connect(pg["admin"], row_factory=dict_row)


def tenant_tables(pg) -> list[str]:
    with _admin(pg) as conn:
        rows = conn.execute("""
            SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r' ORDER BY 1""").fetchall()
    return [r["relname"] for r in rows if r["relname"] not in NON_TENANT_TABLES]


def tenant_col(table: str) -> str:
    return "id" if table == "tenant" else "tenant_id"


def snapshot(pg, tid) -> dict:
    """Toàn bộ dữ liệu của một tenant, đọc bằng role sở hữu schema (không qua RLS)."""
    out = {}
    with _admin(pg) as conn:
        for t in tenant_tables(pg):
            q = sql.SQL("SELECT md5(coalesce(string_agg(x::text, '|' ORDER BY x::text), '')) AS h, count(*) AS n "
                        "FROM {} x WHERE {} = %s").format(sql.Identifier(t), sql.Identifier(tenant_col(t)))
            out[t] = tuple(conn.execute(q, (tid,)).fetchone().values())
    return out


# --------------------------------------------------------------------------- dữ liệu


@pytest.fixture(scope="module")
def world(pg, db, auth_db, tmp_path_factory):
    storage = ImmutableStorage(tmp_path_factory.mktemp("iso-storage"))
    settings = Settings(database_url="", storage_dir=storage.root, session_hours=1, foreign_ai_enabled=False,
                        ocr_provider="fixture", max_upload_bytes=5 * 1024 * 1024)
    ocr = FixtureOcr({
        hashlib.sha256(png(SEEDS["transfer"])).hexdigest(): {
            "doc_type": _sv("bank_transfer"), "direction": _sv("outgoing"), "total_amount": _sv(5_000_000),
            "document_date": _sv("2026-10-01")},
        hashlib.sha256(png(SEEDS["invoice"])).hexdigest(): {
            "doc_type": _sv("invoice"), "total_amount": _sv(5_000_000), "document_date": _sv("2026-10-02")},
    })
    client = TestClient(create_app(settings, db, storage, ocr, auth_db=auth_db))
    w = {"client": client, "storage": storage}
    for key in ("C", "D"):
        email = f"{key.lower()}-{uuid.uuid4().hex[:8]}@example.com"
        tid, uid = make_tenant(pg["admin"], f"Văn phòng {key}", email)
        r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        h = {"Authorization": f"Bearer {r.json()['token']}"}
        cid = client.post("/customers", json={"name": f"Hộ thử {key}"}, headers=h).json()["id"]
        r = client.post(f"/customers/{cid}/imports", headers=h, data={
            "business_date": "2026-10-02", "chat_text": "chi 500k tiền ship"},
            files=[("files", ("ck.png", io.BytesIO(png(SEEDS["transfer"])), "image/png")),
                   ("files", ("hd.png", io.BytesIO(png(SEEDS["invoice"])), "image/png"))])
        assert r.status_code == 201, r.text
        f = next(x for x in client.get(f"/customers/{cid}/findings", headers=h).json()
                 if x["record"]["evidence_kind"] == "bank_transfer_screenshot")
        doc = client.get(f"/findings/{f['id']}/candidates", headers=h).json()[0]["record_id"]
        assert client.post(f"/findings/{f['id']}/match", headers=h, json={"document_record_id": doc}).status_code == 200
        assert client.post("/activity", headers=h, json={"customer_id": cid, "screen": "ledger"}).status_code == 204
        with pytest.raises(OutboundBlocked):
            send_to_foreign_ai(db, tid, settings, "test", "dữ liệu giả lập", "synthetic")
        w[key] = {"tid": tid, "uid": uid, "cid": cid, "h": h, "email": email}
    # Một việc đang chờ của D, để thử nhận việc của tenant khác.
    with _admin(pg) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(w["D"]["tid"]),))
        w["D"]["job"] = conn.execute("INSERT INTO processing_job (tenant_id, customer_id) VALUES (%s, %s) RETURNING id",
                                     (w["D"]["tid"], w["D"]["cid"])).fetchone()["id"]
    return w


@pytest.fixture()
def d_unchanged(pg, world):
    before = snapshot(pg, world["D"]["tid"])
    yield
    assert snapshot(pg, world["D"]["tid"]) == before, "dữ liệu của tenant D bị thay đổi"


def as_c(db, world):
    return db.tx(world["C"]["tid"], world["C"]["uid"])


# --------------------------------------------------------------------------- cấu hình DB


def test_login_roles_cannot_bypass_rls(pg):
    for key in ("app", "auth", "worker"):
        with psycopg.connect(pg[key]) as conn:
            su, bypass = conn.execute(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user").fetchone()
        assert not su and not bypass, key


def test_every_tenant_table_has_forced_rls(pg):
    with _admin(pg) as conn:
        rows = {r["relname"]: r for r in conn.execute("""
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
              EXISTS (SELECT 1 FROM information_schema.columns k
                      WHERE k.table_name = c.relname AND k.column_name = 'tenant_id') AS has_tenant,
              (SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid
                 AND pg_get_expr(p.polqual, p.polrelid) LIKE '%current_tenant()%') AS policies
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r'""").fetchall()}
    for t in tenant_tables(pg):
        r = rows[t]
        assert t == "tenant" or r["has_tenant"], f"{t}: bảng dữ liệu không có tenant_id"
        assert r["relrowsecurity"] and r["relforcerowsecurity"], f"{t}: chưa bật FORCE RLS"
        assert r["policies"] >= 1, f"{t}: không có policy theo current_tenant()"


def test_every_reference_column_is_tenant_scoped(pg):
    """Mọi khóa ngoại tới bảng tenant phải gồm tenant_id; mọi cột *_id kiểu uuid phải có khóa ngoại như vậy."""
    with _admin(pg) as conn:
        fks = conn.execute("""
            SELECT r.relname AS tbl, f.relname AS ref,
              ARRAY(SELECT a.attname FROM unnest(k.conkey) AS u(n)
                    JOIN pg_attribute a ON a.attrelid = k.conrelid AND a.attnum = u.n) AS cols
            FROM pg_constraint k JOIN pg_class r ON r.oid = k.conrelid JOIN pg_class f ON f.oid = k.confrelid
            WHERE k.contype = 'f' AND r.relnamespace = 'public'::regnamespace""").fetchall()
        uuid_cols = conn.execute("""
            SELECT table_name, column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND data_type = 'uuid' AND column_name LIKE '%\\_id'
              AND column_name <> 'tenant_id'""").fetchall()
    tables = set(tenant_tables(pg)) - {"tenant"}
    for fk in fks:
        if fk["tbl"] in tables and fk["ref"] != "tenant":
            assert "tenant_id" in fk["cols"], f"{fk['tbl']}{fk['cols']} → {fk['ref']} không kèm tenant_id"
    scoped = {(fk["tbl"], c) for fk in fks if "tenant_id" in fk["cols"] for c in fk["cols"]}
    for c in uuid_cols:
        if c["table_name"] in tables:
            assert (c["table_name"], c["column_name"]) in scoped, f"{c['table_name']}.{c['column_name']} không có khóa ngoại kèm tenant_id"


def test_security_definer_functions_are_granted_to_one_role_only(pg):
    with _admin(pg) as conn:
        funcs = conn.execute("""
            SELECT p.oid, p.proname FROM pg_proc p
            WHERE p.pronamespace = 'public'::regnamespace AND p.prosecdef""").fetchall()
        assert {f["proname"] for f in funcs} == set(SECURITY_DEFINER_GRANTS), "có hàm SECURITY DEFINER chưa được rà soát"
        for f in funcs:
            for role in ("tax_app", "tax_auth", "tax_worker", "public"):
                allowed = conn.execute("SELECT has_function_privilege(%s, %s::oid, 'EXECUTE') AS ok",
                                       (role, f["oid"])).fetchone()["ok"]
                # tax_worker là thành viên tax_app nên cũng gọi được hàm của tax_app.
                expected = role in SECURITY_DEFINER_GRANTS[f["proname"]] or (
                    role == "tax_worker" and "tax_app" in SECURITY_DEFINER_GRANTS[f["proname"]])
                assert allowed == expected, f"{f['proname']}: quyền của {role} là {allowed}"


def test_world_has_rows_in_every_table(pg, world):
    """Điều kiện để các kiểm tra phía dưới có ý nghĩa: D có dữ liệu ở mọi bảng."""
    empty = [t for t, (_, n) in snapshot(pg, world["D"]["tid"]).items() if n == 0]
    assert empty == []


# --------------------------------------------------------------------------- đọc, sửa, xóa, chèn


def test_other_tenant_rows_invisible_and_immutable(pg, db, world, d_unchanged):
    d = world["D"]["tid"]
    for t in tenant_tables(pg):
        col = sql.Identifier(tenant_col(t))
        with as_c(db, world) as conn:
            n = conn.execute(sql.SQL("SELECT count(*) AS n FROM {} WHERE {} = %s").format(sql.Identifier(t), col),
                             (d,)).fetchone()["n"]
        assert n == 0, f"{t}: C đọc được {n} dòng của D"
        for stmt in (sql.SQL("UPDATE {} SET {} = {} WHERE {} = %s").format(sql.Identifier(t), col, col, col),
                     sql.SQL("DELETE FROM {} WHERE {} = %s").format(sql.Identifier(t), col)):
            try:
                with as_c(db, world) as conn:
                    assert conn.execute(stmt, (d,)).rowcount == 0, f"{t}: C sửa/xóa được dòng của D"
            except psycopg.errors.InsufficientPrivilege:
                pass  # role ứng dụng không có quyền UPDATE/DELETE trên bảng này


def test_no_tenant_context_sees_and_writes_nothing(pg, db, world, d_unchanged):
    for t in tenant_tables(pg):
        with db.tx() as conn:
            n = conn.execute(sql.SQL("SELECT count(*) AS n FROM {}").format(sql.Identifier(t))).fetchone()["n"]
        assert n == 0, f"{t}: chưa đặt tenant mà thấy {n} dòng"
    with pytest.raises(psycopg.Error):
        with db.tx() as conn:
            conn.execute("INSERT INTO customer (tenant_id, name) VALUES (%s, 'không có tenant')", (world["D"]["tid"],))


def _clone_row(pg, table, tid, overrides):
    """Một dòng có thật của tenant tid, đổi các cột duy nhất để không vướng lỗi trùng khóa, rồi áp overrides.

    Cột uuid thuộc một khóa ngoại thì giữ nguyên, để lỗi khóa ngoại (nếu có) chỉ đến từ cột đang thử.
    """
    with _admin(pg) as conn:
        row = conn.execute(sql.SQL("SELECT * FROM {} WHERE {} = %s LIMIT 1").format(
            sql.Identifier(table), sql.Identifier(tenant_col(table))), (tid,)).fetchone()
        cols = {r["attname"]: r for r in conn.execute("""
            SELECT a.attname, format_type(a.atttypid, a.atttypmod) AS typ,
              coalesce(pg_get_expr(d.adbin, d.adrelid), '') LIKE 'nextval%%' AS serial,
              EXISTS (SELECT 1 FROM pg_index i WHERE i.indrelid = a.attrelid AND i.indisunique
                      AND a.attnum = ANY(i.indkey)) AS uniq,
              EXISTS (SELECT 1 FROM pg_constraint k WHERE k.conrelid = a.attrelid AND k.contype = 'f'
                      AND a.attnum = ANY(k.conkey)) AS fk
            FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
            WHERE a.attrelid = %s::regclass AND a.attnum > 0 AND NOT a.attisdropped""", (table,)).fetchall()}
    assert row is not None, f"{table}: không có dòng mẫu"
    row = dict(row)
    for name, c in cols.items():
        if c["serial"]:
            row.pop(name)
        elif not c["uniq"] or name == "tenant_id" or name in overrides or row[name] is None:
            continue
        elif c["typ"] == "uuid" and not c["fk"]:
            row[name] = uuid.uuid4()
        elif c["typ"] == "text":
            row[name] = f"{row[name]}-{uuid.uuid4().hex[:6]}"
        elif c["typ"] in ("integer", "bigint", "smallint"):
            row[name] = row[name] + 1_000_000
    row.update(overrides)
    json_cols = {n for n, c in cols.items() if c["typ"] in ("json", "jsonb")}
    return {k: (Jsonb(v) if k in json_cols and v is not None else v) for k, v in row.items()}


def _insert(conn, table, row):
    cols = list(row)
    conn.execute(sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, cols)),
        sql.SQL(", ").join(sql.Placeholder() * len(cols))), list(row.values()))


def test_insert_with_other_tenant_id_is_rejected(pg, db, world, d_unchanged):
    for t in tenant_tables(pg):
        row = _clone_row(pg, t, world["D"]["tid"], {})
        with pytest.raises(psycopg.Error) as e:
            with as_c(db, world) as conn:
                _insert(conn, t, row)
        assert isinstance(e.value, (psycopg.errors.InsufficientPrivilege, psycopg.errors.ForeignKeyViolation)), \
            f"{t}: bị chặn vì lý do khác: {e.value!r}"


def test_reference_to_other_tenant_row_is_rejected(pg, db, world):
    """Dòng mang tenant_id của C nhưng trỏ tới dòng có thật của D, qua từng khóa ngoại."""
    with _admin(pg) as conn:
        fks = conn.execute("""
            SELECT k.conname, r.relname AS tbl, f.relname AS ref,
              ARRAY(SELECT a.attname FROM unnest(k.conkey) WITH ORDINALITY u(n, i)
                    JOIN pg_attribute a ON a.attrelid = k.conrelid AND a.attnum = u.n ORDER BY i) AS cols,
              ARRAY(SELECT a.attname FROM unnest(k.confkey) WITH ORDINALITY u(n, i)
                    JOIN pg_attribute a ON a.attrelid = k.confrelid AND a.attnum = u.n ORDER BY i) AS refcols
            FROM pg_constraint k JOIN pg_class r ON r.oid = k.conrelid JOIN pg_class f ON f.oid = k.confrelid
            WHERE k.contype = 'f' AND r.relnamespace = 'public'::regnamespace AND f.relname <> 'tenant'
            ORDER BY 1, 2""").fetchall()
    assert fks
    # Dòng đích của D. Nếu cột tham chiếu là duy nhất (vd. record.group_id) thì dòng đích có sẵn đã được
    # dùng, nên tạo thêm một dòng đích mới cho D trước khi chụp dữ liệu của D.
    targets = {}
    for fk in fks:
        own = [c for c in fk["cols"] if c != "tenant_id"]
        with _admin(pg) as conn:
            if _is_unique(pg, fk["tbl"], own):
                fresh = _clone_row(pg, fk["ref"], world["D"]["tid"], {})
                conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(world["D"]["tid"]),))
                _insert(conn, fk["ref"], fresh)
                targets[fk["conname"]] = fresh
            else:
                targets[fk["conname"]] = conn.execute(sql.SQL("SELECT {} FROM {} WHERE tenant_id = %s LIMIT 1").format(
                    sql.SQL(", ").join(map(sql.Identifier, fk["refcols"])), sql.Identifier(fk["ref"])),
                    (world["D"]["tid"],)).fetchone()
    before = snapshot(pg, world["D"]["tid"])
    for fk in fks:
        target = targets[fk["conname"]]
        overrides = {c: target[rc] for c, rc in zip(fk["cols"], fk["refcols"]) if c != "tenant_id"}
        with pytest.raises(psycopg.errors.ForeignKeyViolation) as e:
            with as_c(db, world) as conn:
                # Cột vừa duy nhất vừa là khóa ngoại khác (vd. record.group_id) được trỏ tới một dòng mới của C,
                # để lỗi trùng khóa không che mất lỗi khóa ngoại đang thử.
                for other in fks:
                    if other["tbl"] == fk["tbl"] and other["conname"] != fk["conname"]:
                        own = [c for c in other["cols"] if c != "tenant_id" and c not in overrides]
                        if own and _is_unique(pg, fk["tbl"], own):
                            fresh = _clone_row(pg, other["ref"], world["C"]["tid"], {})
                            _insert(conn, other["ref"], fresh)
                            overrides.update({c: fresh[rc] for c, rc in zip(other["cols"], other["refcols"])
                                              if c != "tenant_id"})
                _insert(conn, fk["tbl"], _clone_row(pg, fk["tbl"], world["C"]["tid"], overrides))
        assert e.value.diag.constraint_name == fk["conname"], f"{fk['conname']}: bị chặn bởi {e.value.diag.constraint_name}"
    assert snapshot(pg, world["D"]["tid"]) == before, "dữ liệu của tenant D bị thay đổi"


def _is_unique(pg, table, cols):
    with _admin(pg) as conn:
        return conn.execute("""
            SELECT EXISTS (SELECT 1 FROM pg_index i WHERE i.indrelid = %s::regclass AND i.indisunique AND i.indkey::int2[] @>
              ARRAY(SELECT attnum FROM pg_attribute WHERE attrelid = %s::regclass AND attname = ANY(%s))) AS u""",
            (table, table, cols)).fetchone()["u"]


def test_regression_activity_log_cannot_point_to_other_tenant(db, world, d_unchanged):
    """Lỗi gốc 1: A ghi được nhật ký hoạt động trỏ tới hộ (hoặc user) của B."""
    c, d = world["C"], world["D"]
    for customer_id, user_id in ((d["cid"], c["uid"]), (c["cid"], d["uid"])):
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            with as_c(db, world) as conn:
                conn.execute("INSERT INTO activity_log (tenant_id, user_id, customer_id, screen) VALUES (%s,%s,%s,'x')",
                             (c["tid"], user_id, customer_id))


def test_regression_target_group_ids_cannot_point_to_other_tenant(pg, db, world, d_unchanged):
    """Mảng target_group_ids không có khóa ngoại; trigger phải chặn id nhóm của tenant khác."""
    with _admin(pg) as conn:
        d_group = conn.execute("SELECT id FROM message_group WHERE tenant_id = %s LIMIT 1",
                               (world["D"]["tid"],)).fetchone()["id"]
    row = _clone_row(pg, "item_decision", world["C"]["tid"], {"target_group_ids": [d_group]})
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with as_c(db, world) as conn:
            _insert(conn, "item_decision", row)


# --------------------------------------------------------------------------- hàm quyền nâng cao


def test_app_role_cannot_call_auth_lookup_or_claim_job(db, world, d_unchanged):
    for stmt, args in (("SELECT * FROM auth_lookup(%s)", (world["D"]["email"],)), ("SELECT * FROM claim_job()", ())):
        for tenant in (world["C"]["tid"], None):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with db.tx(tenant) as conn:
                    conn.execute(stmt, args)


def test_auth_role_reads_no_table(pg, auth_db, world):
    for t in tenant_tables(pg):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with auth_db.tx() as conn:
                conn.execute(sql.SQL("SELECT 1 FROM {} LIMIT 1").format(sql.Identifier(t)))
    with auth_db.tx() as conn:
        row = conn.execute("SELECT user_id, tenant_id FROM auth_lookup(%s)", (world["D"]["email"],)).fetchone()
    assert row["tenant_id"] == world["D"]["tid"]


def test_session_lookup_needs_the_token(db, world):
    with db.tx(world["C"]["tid"]) as conn:
        assert conn.execute("SELECT * FROM session_lookup(%s)", ("0" * 64,)).fetchone() is None


def test_worker_processes_job_only_inside_its_tenant(pg, worker_db, world, tmp_path):
    before_c = snapshot(pg, world["C"]["tid"])
    for _ in range(50):  # có thể còn việc của tenant khác từ các test trước
        with _admin(pg) as conn:
            job = conn.execute("SELECT tenant_id, status FROM processing_job WHERE id = %s",
                               (world["D"]["job"],)).fetchone()
        if job["status"] not in ("pending", "running") or not run_once(worker_db, ImmutableStorage(tmp_path), NoOcr()):
            break
    assert job["tenant_id"] == world["D"]["tid"] and job["status"] in ("done", "failed")
    assert snapshot(pg, world["C"]["tid"]) == before_c, "worker xử lý việc của D làm đổi dữ liệu của C"


# --------------------------------------------------------------------------- API


def _ids_of(pg, tid):
    with _admin(pg) as conn:
        one = lambda q: conn.execute(q, (tid,)).fetchone()  # noqa: E731
        return {
            "customer": one("SELECT id FROM customer WHERE tenant_id = %s LIMIT 1")["id"],
            "attachment": one("SELECT id FROM attachment WHERE tenant_id = %s LIMIT 1")["id"],
            "decision": one("SELECT id FROM item_decision WHERE tenant_id = %s LIMIT 1")["id"],
            "item_ref": one("SELECT item_ref FROM item_decision WHERE tenant_id = %s LIMIT 1")["item_ref"],
            "group": one("SELECT id FROM message_group WHERE tenant_id = %s AND superseded_at IS NULL LIMIT 1")["id"],
            "record": one("SELECT id FROM record WHERE tenant_id = %s LIMIT 1")["id"],
            "finding": one("SELECT id FROM finding WHERE tenant_id = %s LIMIT 1")["id"],
            "match": one("SELECT id FROM match WHERE tenant_id = %s LIMIT 1")["id"],
        }


def test_api_rejects_every_id_of_other_tenant(pg, world, d_unchanged):
    client, h, i = world["client"], world["C"]["h"], _ids_of(pg, world["D"]["tid"])
    calls = [
        ("get", f"/customers/{i['customer']}", None),
        ("get", f"/customers/{i['customer']}/records", None),
        ("get", f"/customers/{i['customer']}/review-queue", None),
        ("get", f"/customers/{i['customer']}/findings", None),
        ("get", f"/attachments/{i['attachment']}/content", None),
        ("post", f"/customers/{i['customer']}/assign", {"item_ref": i["item_ref"], "group_id": str(i["group"])}),
        ("post", f"/decisions/{i['decision']}/resolve", {"choice": "x"}),
        ("post", f"/decisions/{i['decision']}/dismiss", None),
        ("post", f"/groups/{i['group']}/accept", None),
        ("post", f"/groups/{i['group']}/split", {"item_refs": [i["item_ref"]]}),
        ("post", f"/groups/{i['group']}/exclude", {"reason": "duplicate"}),
        ("post", "/groups/merge", {"group_ids": [str(i["group"]), str(i["group"])]}),
        ("patch", f"/records/{i['record']}", {"fields": {"amount": 1}}),
        ("post", f"/records/{i['record']}/confirm", {"fields": {}}),
        ("get", f"/findings/{i['finding']}/candidates", None),
        ("post", f"/findings/{i['finding']}/match", {"document_record_id": str(i["record"])}),
        ("post", f"/matches/{i['match']}/undo", None),
        ("post", f"/findings/{i['finding']}/decision", {"action": "not_needed", "note": "x"}),
        ("post", f"/findings/{i['finding']}/reopen", None),
        ("post", f"/customers/{i['customer']}/request-text", {"finding_ids": [str(i["finding"])]}),
        ("post", "/activity", {"customer_id": str(i["customer"]), "screen": "x"}),
    ]
    for method, path, body in calls:
        r = getattr(client, method)(path, headers=h, **({"json": body} if body is not None else {}))
        assert r.status_code in (400, 403, 404, 409, 422), f"{method.upper()} {path}: HTTP {r.status_code} {r.text[:120]}"
    r = client.post(f"/customers/{i['customer']}/imports", headers=h, data={"business_date": "2026-10-02",
                                                                            "chat_text": "lấn tenant"})
    assert r.status_code in (403, 404), r.text
    customers = client.get("/customers", headers=h).json()
    assert str(i["customer"]) not in {str(c["id"]) for c in customers}
