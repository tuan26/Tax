"""Chỉ số pilot: STOR, tự quyết sai bị sửa, loại khỏi sổ, sai trường của AI."""

import io

import psycopg
from psycopg.rows import dict_row

from app.metrics import pilot_metrics
from tests.conftest import login
from tests.test_integration import new_customer, png


def test_pilot_metrics(client, pg, tenants):
    h = login(client, pg, "A", tenants)
    cid = new_customer(client, h, "Hộ đo chỉ số")
    client.post(f"/customers/{cid}/imports", headers=h, data={"business_date": "2026-10-08",
                "chat_text": "Doanh thu 5tr\nchi 200k tiền ship"},
                files=[("files", (f"{i}.png", io.BytesIO(png(170 + i)), "image/png")) for i in range(3)])
    recs = client.get(f"/customers/{cid}/records", headers=h).json()
    docs = [r for r in recs if r["evidence_kind"] == "document"]
    assert len(recs) == 5 and len(docs) == 3
    # Kế toán gộp 2 ảnh (chỉnh cấu trúc), loại 1 ảnh, xác nhận doanh thu với số tiền khác AI.
    assert client.post("/groups/merge", headers=h, json={"group_ids": [docs[0]["group_id"], docs[1]["group_id"]]}
                       ).status_code == 200
    assert client.post(f"/groups/{docs[2]['group_id']}/exclude", headers=h,
                       json={"reason": "client_retraction"}).status_code == 200
    income = next(r for r in recs if r["fields"]["transaction_type"] == "INCOME")
    client.post(f"/records/{income['id']}/confirm", headers=h, json={"fields": {"amount": 5_500_000}})
    assert client.post(f"/groups/{docs[2]['group_id']}/exclude", headers=h,
                       json={"reason": "client_retraction"}).status_code == 409, "không loại hai lần"

    with psycopg.connect(pg["admin"], row_factory=dict_row) as conn:
        m = pilot_metrics(conn, cid)
        excluded = conn.execute("SELECT status, excluded_reason FROM record WHERE group_id = %s",
                                (docs[2]["group_id"],)).fetchone()
    manual = m["ZALO_MANUAL"]
    # Còn 3 giao dịch: nhóm gộp (bị chỉnh), doanh thu và tiền ship (engine tự làm đúng).
    assert manual["transactions"] == 3 and manual["straight_through"] == 2
    assert manual["STOR"] == round(2 / 3, 4)
    assert manual["excluded:client_retraction"] == 1
    # Ảnh đứng một mình là quyết định CONFIDENT của engine; bị gộp nghĩa là engine tổ chức sai mà không biết.
    assert manual["silent_restructure"] == 1
    assert manual["records_ai_wrong_field"] == 1 and manual["ai_wrong_field_rate"] == 1.0
    assert excluded == {"status": "EXCLUDED", "excluded_reason": "client_retraction"}
    assert len(client.get(f"/customers/{cid}/records", headers=h).json()) == 3
