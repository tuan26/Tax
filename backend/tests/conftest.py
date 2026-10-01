"""Test tích hợp chạy trên PostgreSQL thật.

Cần biến TEST_PG_ADMIN_URL trỏ tới một server PostgreSQL với quyền superuser, ví dụ
postgresql://postgres@/postgres?host=/tmp&port=55432. Thiếu biến này thì bỏ qua test tích hợp.
"""

import os
import uuid
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings
from app.db import Database, migrate
from app.extraction import NoOcr
from app.security import hash_password
from app.storage import ImmutableStorage

ADMIN = os.environ.get("TEST_PG_ADMIN_URL")
PASSWORD = "mat-khau-thu-nghiem"


def _url(base: str, dbname: str, user: str | None = None) -> str:
    info = psycopg.conninfo.conninfo_to_dict(base)
    info["dbname"] = dbname
    if user:
        info["user"] = user
    return psycopg.conninfo.make_conninfo(**info)


@pytest.fixture(scope="session")
def pg():
    if not ADMIN:
        pytest.skip("Cần TEST_PG_ADMIN_URL để chạy test tích hợp")
    name = f"tax_test_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(ADMIN, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
        conn.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='tax_app_test') THEN "
                     "CREATE ROLE tax_app_test LOGIN; END IF; END $$")
    admin_url = _url(ADMIN, name)
    migrate(admin_url)
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute("GRANT tax_app TO tax_app_test")
    yield {"admin": admin_url, "app": _url(ADMIN, name, "tax_app_test"), "name": name}
    with psycopg.connect(ADMIN, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def make_tenant(admin_url, name, email):
    tid = uuid.uuid4()
    with psycopg.connect(admin_url) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tid),))
        conn.execute("INSERT INTO tenant (id, name) VALUES (%s, %s)", (tid, name))
        uid = conn.execute("INSERT INTO app_user (tenant_id, email, display_name, password_hash) VALUES (%s,%s,%s,%s)"
                           " RETURNING id", (tid, email, name, hash_password(PASSWORD))).fetchone()[0]
    return tid, uid


@pytest.fixture(scope="session")
def db(pg):
    d = Database(pg["app"])
    yield d
    d.close()


@pytest.fixture(scope="session")
def tenants(pg):
    a = make_tenant(pg["admin"], "Văn phòng A", f"a-{uuid.uuid4().hex[:6]}@example.com")
    b = make_tenant(pg["admin"], "Văn phòng B", f"b-{uuid.uuid4().hex[:6]}@example.com")
    return {"A": a, "B": b}


@pytest.fixture()
def storage(tmp_path):
    return ImmutableStorage(tmp_path / "storage")


@pytest.fixture()
def settings(tmp_path):
    return Settings(database_url="", storage_dir=tmp_path / "storage", session_hours=1, foreign_ai_enabled=False,
                    ocr_provider="none", max_upload_bytes=5 * 1024 * 1024)


@pytest.fixture()
def client(settings, db, storage):
    return TestClient(create_app(settings, db, storage, NoOcr()))


def login(client, pg, tenant_key, tenants):
    tid, uid = tenants[tenant_key]
    with psycopg.connect(pg["admin"]) as conn:
        email = conn.execute("SELECT email FROM app_user WHERE id = %s", (uid,)).fetchone()[0]
    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


FIXTURES = Path(__file__).resolve().parents[2] / "spec"
