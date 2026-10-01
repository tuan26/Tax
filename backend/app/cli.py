"""Quản trị pilot, chạy bằng kết nối quản trị (ADMIN_DATABASE_URL):

python -m app.cli migrate
python -m app.cli create-tenant "Văn phòng kế toán A"
python -m app.cli create-user <tenant_id> email@example.com "Tên hiển thị"   (mật khẩu từ biến PASSWORD hoặc nhập)
"""

import getpass
import os
import sys
from uuid import uuid4

import psycopg

from .db import migrate
from .security import hash_password


def _admin():
    return os.environ["ADMIN_DATABASE_URL"]


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "migrate":
        migrate(_admin())
        print("migrated")
    elif cmd == "create-tenant":
        tid = uuid4()
        with psycopg.connect(_admin()) as conn:
            conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tid),))
            conn.execute("INSERT INTO tenant (id, name) VALUES (%s, %s)", (tid, argv[2]))
        print(tid)
    elif cmd == "create-user":
        tenant_id, email, name = argv[2], argv[3].lower(), argv[4]
        password = os.environ.get("PASSWORD") or getpass.getpass("Mật khẩu: ")
        if len(password) < 10:
            sys.exit("Mật khẩu cần ít nhất 10 ký tự")
        with psycopg.connect(_admin()) as conn:
            conn.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_id,))
            row = conn.execute("INSERT INTO app_user (tenant_id, email, display_name, password_hash)"
                               " VALUES (%s,%s,%s,%s) RETURNING id", (tenant_id, email, name, hash_password(password)))
            print(row.fetchone()[0])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
