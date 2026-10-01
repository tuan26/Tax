"""Gate 7: OCR lỗi phải giảm cấp an toàn.

Ảnh nhận được → OCR lỗi / quá thời gian / rác / độ tin cậy thấp
→ file gốc vẫn còn → bản ghi chờ duyệt, không có giá trị đoán → không dùng được để sinh phát hiện.
"""

import io
import time
from dataclasses import replace

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.review import finding_inputs
from tests.conftest import login
from tests.test_integration import new_customer, png


class Raising:
    name, domestic = "raising", True

    def extract(self, data, mime):
        raise ConnectionError("OCR server không phản hồi")


class Slow:
    name, domestic = "slow", True

    def extract(self, data, mime):
        time.sleep(1.0)
        return {"doc_type": {"value": "invoice", "confidence": 0.99},
                "total_amount": {"value": 1_000_000, "confidence": 0.99}}


class Garbage:
    name, domestic = "garbage", True

    def extract(self, data, mime):
        return {"text": "@@@"}


class LowConfidence:
    name, domestic = "lowconf", True

    def extract(self, data, mime):
        return {"doc_type": {"value": "invoice", "confidence": 0.95},
                "total_amount": {"value": 2_350_000, "confidence": 0.41},
                "document_date": {"value": "2026-10-01", "confidence": 0.35}}


class Good:
    name, domestic = "good", True

    def extract(self, data, mime):
        return {"doc_type": {"value": "invoice", "confidence": 0.97},
                "total_amount": {"value": 2_350_000, "confidence": 0.97},
                "document_date": {"value": "2026-10-01", "confidence": 0.95}}


def _run(provider, settings, db, storage, pg, tenants, seed):
    client = TestClient(create_app(replace(settings, ocr_timeout_seconds=0.2), db, storage, provider))
    h = login(client, pg, "A", tenants)
    cid = new_customer(client, h, f"Hộ OCR {provider.name}")
    r = client.post(f"/customers/{cid}/imports", headers=h, data={"business_date": "2026-10-01"},
                    files=[("files", ("hd.png", io.BytesIO(png(seed)), "image/png"))])
    assert r.status_code == 201, r.text
    assert r.json()["processing"] == "done", "lỗi OCR không được làm hỏng cả lượt xử lý"
    recs = client.get(f"/customers/{cid}/records", headers=h).json()
    assert len(recs) == 1, "ảnh vẫn phải thành một giao dịch chờ duyệt"
    att = recs[0]["evidence_items"][0].split("#")[1]
    assert client.get(f"/attachments/{att}/content", headers=h).content == png(seed), "file gốc phải còn nguyên"
    with psycopg.connect(pg["admin"]) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenants["A"][0]),))
        conn.row_factory = psycopg.rows.dict_row
        row = conn.execute("SELECT * FROM record WHERE id = %s", (recs[0]["id"],)).fetchone()
        ext = conn.execute("SELECT fields FROM extraction WHERE attachment_id = %s", (att,)).fetchone()["fields"]
    return recs[0], row, ext


@pytest.mark.parametrize("provider,reason,status,seed", [
    (Raising(), "ocr_failed", "failed", 101),
    (Slow(), "ocr_failed", "failed", 102),
    (Garbage(), "ocr_failed", "failed", 103),
    (LowConfidence(), "amount_low_confidence", "ok", 104),
])
def test_ocr_failure_degrades_safely(provider, reason, status, seed, settings, db, storage, pg, tenants):
    rec, row, ext = _run(provider, settings, db, storage, pg, tenants, seed=seed)
    assert ext["status"] == status
    assert rec["review_required"] is True
    assert reason in rec["review_reasons"]
    assert rec["fields"]["amount"] is None, "không được điền số tiền đoán"
    assert finding_inputs(row) is None, "không sinh phát hiện từ dữ liệu chưa chắc"
    if isinstance(provider, LowConfidence):
        assert rec["fields_ai"]["amount"]["candidates"] == [2_350_000], "giá trị đọc kém chỉ là gợi ý"
        assert rec["fields"]["document_date"] is None


def test_good_ocr_is_usable(settings, db, storage, pg, tenants):
    rec, row, ext = _run(Good(), settings, db, storage, pg, tenants, seed=201)
    assert ext["status"] == "ok"
    assert rec["fields"]["amount"] == 2_350_000
    # Ảnh hóa đơn đọc tốt vẫn chưa đủ để sinh phát hiện nếu chưa có gì khác đáng ngờ: bản ghi đạt HIGH thì được dùng.
    assert rec["review_required"] is False
    assert finding_inputs(row)["amount"] == 2_350_000
