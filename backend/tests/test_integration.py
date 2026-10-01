"""Luồng chính qua API: nhập tay → gom → hàng chờ duyệt → kế toán xử lý → xác nhận bản ghi."""

import io

import psycopg

from tests.conftest import login


def png(seed: int) -> bytes:
    # PNG 1x1 hợp lệ; byte cuối thay đổi để mỗi ảnh có sha256 khác nhau.
    base = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                         "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")
    return base + bytes([seed])


def new_customer(client, h, name="Quán Minh Anh"):
    r = client.post("/customers", json={"name": name}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_manual_import_flow(client, pg, tenants):
    h = login(client, pg, "A", tenants)
    cid = new_customer(client, h)
    r = client.post(f"/customers/{cid}/imports", headers=h, data={
        "business_date": "2026-10-03", "source_type": "ZALO_MANUAL",
        "chat_text": "tiền gas\nDoanh thu 5tr\nok em nhé",
    }, files=[("files", ("hd1.png", io.BytesIO(png(1)), "image/png"))])
    assert r.status_code == 201, r.text
    assert r.json()["processing"] == "done"

    q = client.get(f"/customers/{cid}/review-queue", headers=h).json()
    # Ảnh không có OCR và chú thích không có bằng chứng ghép: cả hai phải chờ kế toán.
    caption = next(i for i in q["items"] if i["text"] == "tiền gas")
    assert caption["type"] == "ambiguous_link"
    assert {c["choice"] for c in caption["candidates"]} >= {"NONE"}
    image_record = next(r for r in q["records"] if r["evidence_kind"] == "document")
    assert image_record["fields"]["amount"] is None
    assert "amount_missing" in image_record["review_reasons"]

    # Doanh thu tự khai đã đủ chắc, không vào hàng chờ.
    recs = client.get(f"/customers/{cid}/records", headers=h).json()
    income = next(r for r in recs if r["evidence_kind"] == "self_declared")
    assert income["fields"]["amount"] == 5_000_000 and income["fields"]["posting_date"] == "2026-10-03"
    assert income["review_required"] is False

    # Kế toán gán chú thích vào ảnh, nhập số tiền và xác nhận.
    group_choice = next(c["choice"] for c in caption["candidates"] if c["choice"] != "NONE")
    assert client.post(f"/decisions/{caption['decision_id']}/resolve", json={"choice": group_choice},
                       headers=h).status_code == 200
    r = client.post(f"/records/{image_record['id']}/confirm", json={"fields": {}}, headers=h)
    assert r.status_code == 409 and "amount" in r.json()["detail"]
    r = client.post(f"/records/{image_record['id']}/confirm", json={"fields": {"amount": 950000, "transaction_type": "EXPENSE"}},
                    headers=h)
    assert r.status_code == 200, r.text

    recs = {r["id"]: r for r in client.get(f"/customers/{cid}/records", headers=h).json()}
    confirmed = recs[image_record["id"]]
    assert confirmed["confirmed"] and confirmed["fields"]["amount"] == 950000
    assert confirmed["fields"]["description"] == "tiền gas"
    assert confirmed["fields_ai"]["amount"]["value"] is None, "giá trị AI phải được giữ nguyên để đo % phải sửa"
    q = client.get(f"/customers/{cid}/review-queue", headers=h).json()
    assert not any(i["text"] == "tiền gas" for i in q["items"])


def test_amount_evidence_links_without_review(client, pg, tenants):
    """Nhập tay: số tiền khớp duy nhất một bản ghi tự khai không được gán; chỉ ảnh có OCR mới khớp."""
    h = login(client, pg, "A", tenants)
    cid = new_customer(client, h, "Tạp hóa Lan")
    r = client.post(f"/customers/{cid}/imports", headers=h, data={
        "business_date": "2026-10-04", "chat_text": "Hôm nay bán 8tr4, nhập hàng 3tr"})
    assert r.status_code == 201
    recs = client.get(f"/customers/{cid}/records", headers=h).json()
    assert sorted((r["fields"]["transaction_type"], r["fields"]["amount"]) for r in recs) == [
        ("EXPENSE", 3_000_000), ("INCOME", 8_400_000)]


def test_split_and_merge_keep_history(client, pg, tenants):
    h = login(client, pg, "A", tenants)
    cid = new_customer(client, h, "Quán Hòa")
    client.post(f"/customers/{cid}/imports", headers=h, data={"business_date": "2026-10-05"},
                files=[("files", ("a.png", io.BytesIO(png(10)), "image/png")),
                       ("files", ("b.png", io.BytesIO(png(11)), "image/png"))])
    recs = client.get(f"/customers/{cid}/records", headers=h).json()
    assert len(recs) == 2
    r = client.post("/groups/merge", json={"group_ids": [recs[0]["group_id"], recs[1]["group_id"]]}, headers=h)
    assert r.status_code == 200, r.text
    recs = client.get(f"/customers/{cid}/records", headers=h).json()
    assert len(recs) == 1 and len(recs[0]["evidence_items"]) == 2
    r = client.post(f"/groups/{recs[0]['group_id']}/split", json={"item_refs": [recs[0]["evidence_items"][1]]},
                    headers=h)
    assert r.status_code == 200, r.text
    assert len(client.get(f"/customers/{cid}/records", headers=h).json()) == 2
    # Lịch sử còn đủ: quyết định cũ chỉ bị đánh dấu hết hiệu lực.
    with psycopg.connect(pg["admin"]) as conn:
        decisions = conn.execute("SELECT count(*) FROM item_decision WHERE customer_id = %s AND superseded_at IS NOT"
                                 " NULL", (cid,)).fetchone()[0]
        groups = conn.execute("SELECT count(*) FROM message_group WHERE customer_id = %s AND superseded_at IS NOT NULL",
                              (cid,)).fetchone()[0]
        merged = conn.execute("SELECT count(*) FROM record WHERE customer_id = %s AND status = 'MERGED'",
                              (cid,)).fetchone()[0]
    # Gộp: 1 quyết định anchor hết hiệu lực, 1 nhóm hết hiệu lực, 1 bản ghi MERGED. Tách: thêm 1 quyết định.
    assert (decisions, groups, merged) == (2, 1, 1)


def test_rejects_unsupported_file(client, pg, tenants):
    h = login(client, pg, "A", tenants)
    cid = new_customer(client, h, "Hộ X")
    r = client.post(f"/customers/{cid}/imports", headers=h, data={"business_date": "2026-10-05"},
                    files=[("files", ("x.exe", io.BytesIO(b"MZ"), "application/octet-stream"))])
    assert r.status_code == 415
