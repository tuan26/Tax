"""Kết nối DB. Mọi truy vấn nghiệp vụ chạy trong transaction đã đặt tenant, để RLS có hiệu lực."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

MIGRATIONS = Path(__file__).parent / "migrations"


class Database:
    def __init__(self, url: str):
        self.pool = ConnectionPool(url, min_size=1, max_size=10, kwargs={"row_factory": dict_row}, open=True)

    def close(self):
        self.pool.close()

    @contextmanager
    def tx(self, tenant_id=None, user_id=None, actor_kind="user"):
        """Transaction gắn tenant và người thực hiện cho RLS và audit trigger."""
        with self.pool.connection() as conn:
            with conn.transaction():
                if tenant_id is not None:
                    conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),))
                conn.execute("SELECT set_config('app.user_id', %s, true)", (str(user_id) if user_id else "",))
                conn.execute("SELECT set_config('app.actor_kind', %s, true)", (actor_kind,))
                yield conn


def migrate(admin_url: str):
    """Chạy migration bằng role sở hữu schema (không phải role của app)."""
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migration (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
        done = {r[0] for r in conn.execute("SELECT version FROM schema_migration")}
        for path in sorted(MIGRATIONS.glob("*.sql")):
            if path.stem in done:
                continue
            sql = path.read_text().replace(
                "CREATE TABLE schema_migration (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());", "")
            with conn.transaction():
                conn.execute(sql)
