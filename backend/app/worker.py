"""Worker xử lý lại các đợt nhập bị lỗi hoặc đang chờ: python -m app.worker"""

import logging
import time

from .config import load_settings
from .db import Database
from .extraction import provider_for
from .pipeline import process_customer
from .storage import ImmutableStorage

log = logging.getLogger("tax.worker")


def run_once(db, storage, ocr) -> bool:
    with db.tx(actor_kind="system") as conn:
        job = conn.execute("SELECT * FROM claim_job()").fetchone()
    if job is None:
        return False
    try:
        with db.tx(job["tenant_id"], None, "engine") as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (str(job["customer_id"]),))
            process_customer(conn, job["tenant_id"], job["customer_id"], ocr, storage)
            conn.execute("UPDATE processing_job SET status='done', finished_at=now() WHERE id=%s", (job["job_id"],))
    except Exception as e:
        log.exception("job %s failed", job["job_id"])
        with db.tx(job["tenant_id"], None, "system") as conn:
            conn.execute("UPDATE processing_job SET status='failed', error=%s, finished_at=now() WHERE id=%s",
                         (repr(e)[:2000], job["job_id"]))
    return True


def main():
    logging.basicConfig(level=logging.INFO)
    s = load_settings()
    db, storage, ocr = Database(s.database_url), ImmutableStorage(s.storage_dir), provider_for(s.ocr_provider)
    while True:
        if not run_once(db, storage, ocr):
            time.sleep(5)


if __name__ == "__main__":
    main()
