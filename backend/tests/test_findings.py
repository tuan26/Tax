"""Vòng khép kín: phát hiện → yêu cầu khách → ghép chứng từ → đóng; bỏ ghép → mở lại."""

import hashlib
import io

import psycopg
from fastapi.testclient import TestClient

from app.api import create_app
from app.extraction import FixtureOcr
from tests.conftest import login
from tests.test_integration import new_customer, png


def _sv(v, c=0.97):
    return {"value": v, "confidence": c}


def _app(settings, db, storage, seeds):
    by_sha = {
        hashlib.sha256(png(seeds["transfer"])).hexdigest(): {
            "doc_type": _sv("bank_transfer"), "direction": _sv("outgoing"), "total_amount": _sv(5_000_000),
            "document_date": _sv("2026-10-01")},
        hashlib.sha256(png(seeds["invoice"])).hexdigest(): {
            "doc_type": _sv("invoice"), "total_amount": _sv(5_000_000), "document_date": _sv("2026-10-02"),
            "counterparty_name": _sv("Đại lý thực phẩm Hòa", 0.9)},
    }
    return TestClient(create_app(settings, db, storage, FixtureOcr(by_sha)))


def _import(client, h, cid, seeds):
    r = client.post(f"/customers/{cid}/imports", headers=h, data={
        "business_date": "2026-10-02", "chat_text": "chi 500k tiền ship"},
        files=[("files", ("ck.png", io.BytesIO(png(seeds["transfer"])), "image/png")),
               ("files", ("hd.png", io.BytesIO(png(seeds["invoice"])), "image/png"))])
    assert r.status_code == 201 and r.json()["processing"] == "done", r.text


def test_closed_loop(settings, db, storage, pg, tenants):
    seeds = {"transfer": 210, "invoice": 211}
    client = _app(settings, db, storage, seeds)
    h = login(client, pg, "A", tenants)
    cid = new_customer(client, h, "Hộ vòng khép kín")
    _import(client, h, cid, seeds)

    fs = client.get(f"/customers/{cid}/findings", headers=h).json()
    dq01 = {f["record"]["evidence_kind"]: f for f in fs if f["rule_id"] == "DQ-01"}
    assert set(dq01) == {"bank_transfer_screenshot", "self_declared"}
    transfer, ship = dq01["bank_transfer_screenshot"], dq01["self_declared"]
    assert transfer["status"] == "OPEN" and transfer["evidence"], "phát hiện phải có bằng chứng"

    # Yêu cầu khách bổ sung: tin nhắn liệt kê đúng các khoản, phát hiện chuyển sang REQUESTED.
    r = client.post(f"/customers/{cid}/request-text", headers=h,
                    json={"finding_ids": [transfer["id"], ship["id"]]}).json()
    assert "5.000.000đ" in r["text"] and "500.000đ" in r["text"] and r["text"].startswith("Anh/chị")
    assert {f["status"] for f in client.get(f"/customers/{cid}/findings", headers=h).json()
            if f["rule_id"] == "DQ-01"} == {"REQUESTED"}

    # Gợi ý chứng từ để ghép: hóa đơn cùng số tiền đứng đầu, có bằng chứng từng tiêu chí.
    cands = client.get(f"/findings/{transfer['id']}/candidates", headers=h).json()
    assert cands and cands[0]["fields"]["amount"] == 5_000_000
    assert {e["criterion"]: e["ok"] for e in cands[0]["evidence"]} == {"amount": True, "date": True, "type": True}
    invoice_id = cands[0]["record_id"]

    # Ghép và xác nhận: phát hiện đóng; sổ không cộng hai lần.
    m = client.post(f"/findings/{transfer['id']}/match", headers=h, json={"document_record_id": invoice_id}).json()
    f = next(x for x in client.get(f"/customers/{cid}/findings", headers=h).json() if x["id"] == transfer["id"])
    assert f["status"] == "RESOLVED" and f["resolution"] == "matched" and f["match"]["document"]["id"] == invoice_id
    recs = {r["evidence_kind"]: r for r in client.get(f"/customers/{cid}/records", headers=h).json()
            if r["fields"]["amount"] == 5_000_000}
    assert recs["bank_transfer_screenshot"]["counted"] is False and recs["document"]["counted"] is True

    # Bỏ ghép: phát hiện mở lại.
    assert client.post(f"/matches/{m['match_id']}/undo", headers=h).status_code == 200
    f = next(x for x in client.get(f"/customers/{cid}/findings", headers=h).json() if x["id"] == transfer["id"])
    assert f["status"] == "OPEN" and f["resolution"] is None

    # Không cần xử lý thì phải có lý do; mở lại được.
    assert client.post(f"/findings/{ship['id']}/decision", headers=h, json={"action": "not_needed"}).status_code == 409
    assert client.post(f"/findings/{ship['id']}/decision", headers=h,
                       json={"action": "not_needed", "note": "phí ship nhỏ, khách trả tiền mặt"}).status_code == 200
    assert client.post(f"/findings/{ship['id']}/reopen", headers=h).status_code == 200

    # Ghép lại rồi loại hóa đơn khỏi sổ: ghép bị bỏ, phát hiện của chuyển khoản mở lại.
    client.post(f"/findings/{transfer['id']}/match", headers=h, json={"document_record_id": invoice_id})
    group = next(r["group_id"] for r in client.get(f"/customers/{cid}/records", headers=h).json() if r["id"] == invoice_id)
    assert client.post(f"/groups/{group}/exclude", headers=h, json={"reason": "duplicate"}).status_code == 200
    f = next(x for x in client.get(f"/customers/{cid}/findings", headers=h).json() if x["id"] == transfer["id"])
    assert f["status"] == "OPEN"
    with psycopg.connect(pg["admin"]) as conn:
        statuses = [r[0] for r in conn.execute("SELECT status FROM match WHERE payment_record_id = %s ORDER BY created_at",
                                               (transfer["record_id"],))]
    assert statuses == ["UNDONE", "UNDONE"], "lịch sử ghép được giữ lại"

    # Tenant khác không thấy và không thao tác được.
    hb = login(client, pg, "B", tenants)
    assert client.get(f"/customers/{cid}/findings", headers=hb).status_code == 404
    assert client.post(f"/findings/{transfer['id']}/decision", headers=hb, json={"action": "request"}).status_code == 409


def test_findings_never_from_uncertain_records(client, pg, tenants):
    """Ảnh không OCR được: bản ghi chờ duyệt, không có phát hiện nào cho tới khi kế toán xác nhận."""
    h = login(client, pg, "A", tenants)
    cid = new_customer(client, h, "Hộ chưa chắc")
    client.post(f"/customers/{cid}/imports", headers=h, data={"business_date": "2026-10-02"},
                files=[("files", ("x.png", io.BytesIO(png(220)), "image/png"))])
    assert client.get(f"/customers/{cid}/findings", headers=h).json() == []
    rec = client.get(f"/customers/{cid}/records", headers=h).json()[0]
    client.post(f"/records/{rec['id']}/confirm", headers=h,
                json={"fields": {"amount": 300_000, "transaction_type": "EXPENSE"}})
    titles = [f["title"] for f in client.get(f"/customers/{cid}/findings", headers=h).json()]
    assert titles == ["Chứng từ không có ngày"]
