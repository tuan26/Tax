"""Gate 5: backup tồn tại chưa đủ, phải khôi phục được và bản khôi phục phải còn nguyên các đảm bảo."""

import io
import os
import subprocess
import uuid
from pathlib import Path

import psycopg
import pytest

from tests.conftest import ADMIN, _url, login
from tests.test_integration import new_customer, png

OPS = Path(__file__).resolve().parents[2] / "ops"


def _run(script, env):
    return subprocess.run([str(OPS / script)], env={**os.environ, **env}, capture_output=True, text=True)


@pytest.fixture()
def seeded(client, pg, tenants, storage):
    h = login(client, pg, "A", tenants)
    cid = new_customer(client, h, "Hộ sao lưu")
    client.post(f"/customers/{cid}/imports", headers=h, data={
        "business_date": "2026-10-07", "chat_text": "tiền thịt\nDoanh thu 9tr"},
        files=[("files", ("a.png", io.BytesIO(png(150)), "image/png")),
               ("files", ("b.png", io.BytesIO(png(151)), "image/png"))])
    rec = next(r for r in client.get(f"/customers/{cid}/records", headers=h).json() if r["evidence_kind"] == "document")
    assert client.post(f"/records/{rec['id']}/confirm", headers=h,
                       json={"fields": {"amount": 1_234_000, "transaction_type": "EXPENSE"}}).status_code == 200
    return cid, rec["id"]


@pytest.fixture()
def target_db():
    name = f"tax_restore_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(ADMIN, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    yield _url(ADMIN, name), _url(ADMIN, name, "tax_app_test")
    with psycopg.connect(ADMIN, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def _backup(pg, storage, tmp_path):
    r = _run("backup.sh", {"ADMIN_DATABASE_URL": pg["admin"], "STORAGE_DIR": str(storage.root),
                           "BACKUP_DIR": str(tmp_path / "backups")})
    assert r.returncode == 0, r.stderr
    return Path(r.stdout.strip().splitlines()[-1])


def test_backup_and_restore(seeded, pg, tenants, storage, tmp_path, target_db):
    cid, record_id = seeded
    backup = _backup(pg, storage, tmp_path)
    target_admin, target_app = target_db
    restored_storage = tmp_path / "restored-storage"
    r = _run("restore.sh", {"BACKUP": str(backup), "TARGET_ADMIN_URL": target_admin,
                            "TARGET_STORAGE_DIR": str(restored_storage)})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "RESTORE ĐẠT" in r.stdout

    tid, uid = tenants["A"]
    with psycopg.connect(target_app) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tid),))
        fields = conn.execute("SELECT fields_confirmed FROM record WHERE id = %s", (record_id,)).fetchone()[0]
        assert fields["amount"] == 1_234_000, "quyết định của kế toán phải còn sau khi khôi phục"
        n = conn.execute("SELECT count(*) FROM message WHERE customer_id = %s", (cid,)).fetchone()[0]
        assert n == 4
    # Đảm bảo vẫn còn hiệu lực trên bản khôi phục.
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with psycopg.connect(target_admin) as conn:
            conn.execute("DELETE FROM message")
    with psycopg.connect(target_app) as conn:
        assert conn.execute("SELECT count(*) FROM customer").fetchone()[0] == 0, "chưa đặt tenant thì không thấy gì"


def test_restore_rejects_tampered_backup(seeded, pg, storage, tmp_path, target_db):
    backup = _backup(pg, storage, tmp_path)
    with open(backup / "storage.tar.gz", "ab") as f:
        f.write(b"x")
    r = _run("restore.sh", {"BACKUP": str(backup), "TARGET_ADMIN_URL": target_db[0],
                            "TARGET_STORAGE_DIR": str(tmp_path / "s2")})
    assert r.returncode != 0


def test_verify_detects_missing_file(seeded, pg, storage, tmp_path, target_db):
    from app.backup_verify import verify

    backup = _backup(pg, storage, tmp_path)
    restored = tmp_path / "s3"
    assert _run("restore.sh", {"BACKUP": str(backup), "TARGET_ADMIN_URL": target_db[0],
                               "TARGET_STORAGE_DIR": str(restored)}).returncode == 0
    victim = next(p for p in restored.rglob("*") if p.is_file())
    victim.chmod(0o640)
    victim.unlink()
    problems, _ = verify(target_db[0], str(restored))
    assert any("thiếu file gốc" in p for p in problems)
