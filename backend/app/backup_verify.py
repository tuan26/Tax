"""Kiểm tra một bản khôi phục: python -m app.backup_verify <admin_url> <storage_dir>

Đạt khi: mọi file gốc có mặt và khớp sha256, trigger chỉ-thêm và audit còn đủ, RLS còn bật FORCE
trên mọi bảng có tenant, và số dòng audit INSERT khớp số dòng của từng bảng nghiệp vụ.
"""

import hashlib
import sys
from pathlib import Path

import psycopg

AUDITED = ["customer", "import_batch", "message", "attachment", "extraction", "ai_call", "grouping_run",
           "message_group", "item_decision", "record"]
APPEND_ONLY = ["import_batch", "message", "attachment", "extraction", "ai_call", "grouping_run", "audit_event"]
RLS_TABLES = ["tenant", "app_user", "user_session", "customer", "import_batch", "message", "attachment", "extraction",
              "ai_call", "grouping_run", "message_group", "item_decision", "record", "processing_job", "activity_log",
              "audit_event"]


def verify(admin_url: str, storage_dir: str) -> tuple[list[str], dict]:
    problems: list[str] = []
    stats: dict = {}
    root = Path(storage_dir)
    with psycopg.connect(admin_url) as conn:
        atts = conn.execute("SELECT id, sha256, storage_key FROM attachment").fetchall()
        stats["attachments"] = len(atts)
        for att_id, sha, key in atts:
            path = root / key
            if not path.exists():
                problems.append(f"thiếu file gốc của attachment {att_id}")
            elif hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                problems.append(f"file gốc của attachment {att_id} không khớp sha256")

        triggers = {r[0] for r in conn.execute("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal")}
        for t in APPEND_ONLY:
            if f"{t}_append_only" not in triggers:
                problems.append(f"mất trigger chỉ-thêm trên {t}")
        for t in AUDITED:
            if f"{t}_audit" not in triggers:
                problems.append(f"mất trigger audit trên {t}")

        rls = {r[0]: (r[1], r[2]) for r in conn.execute(
            "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = ANY(%s)",
            (RLS_TABLES,))}
        for t in RLS_TABLES:
            if rls.get(t) != (True, True):
                problems.append(f"RLS không bật FORCE trên {t}")

        for t in AUDITED:
            rows = conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            audited = conn.execute("SELECT count(*) FROM audit_event WHERE table_name = %s AND action = 'INSERT'",
                                   (t,)).fetchone()[0]
            stats[t] = rows
            if rows != audited:
                problems.append(f"{t}: {rows} dòng nhưng {audited} audit INSERT")
    return problems, stats


def main(argv):
    problems, stats = verify(argv[1], argv[2])
    for k, v in stats.items():
        print(f"{k}: {v}")
    if problems:
        print("RESTORE KHÔNG ĐẠT")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("RESTORE ĐẠT")


if __name__ == "__main__":
    main(sys.argv)
