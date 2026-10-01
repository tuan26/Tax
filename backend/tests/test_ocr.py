"""Rút trường từ văn bản OCR và bộ chấm spike OCR. Không cần Tesseract, trừ test cuối."""

import csv
import shutil

import pytest

from app.ocr.bench import render_markdown, run_bench, score_one
from app.ocr.text_fields import extract_fields, mst_checksum_ok

INVOICE = """CÔNG TY TNHH VẬT TƯ BÌNH AN
HÓA ĐƠN GIÁ TRỊ GIA TĂNG
Ngày 01 tháng 10 năm 2026
Đơn vị bán hàng: Công ty TNHH Vật tư Bình An
Mã số thuế: 0100109106
Người mua: Quán ăn Minh Anh   MST: 8012345678
Thịt heo  15kg  150.000  2.250.000
Cộng tiền hàng: 2.250.000
Tổng cộng thanh toán: 2.350.000
"""

TRANSFER = """Chuyển tiền thành công
-5,000,000 VND
Tài khoản nguồn: 0071000123456
Tài khoản nhận: TRAN THI B
Thời gian: 01/10/2026 14:20
Nội dung: tien mua nguyen lieu
"""


def v(fields, key):
    return fields[key]["value"], fields[key]["confidence"]


def test_invoice_fields():
    f = extract_fields(INVOICE)
    assert v(f, "doc_type") == ("invoice", 0.85)
    assert v(f, "total_amount") == (2_350_000, 0.9), "phải ưu tiên 'Tổng cộng thanh toán' hơn 'Cộng tiền hàng'"
    assert v(f, "document_date") == ("2026-10-01", 0.85)
    assert f["seller_tax_id"]["value"] == "0100109106", "MST người bán in trước MST người mua"
    assert f["counterparty_name"]["value"] == "Công ty TNHH Vật tư Bình An"


def test_transfer_fields():
    f = extract_fields(TRANSFER)
    assert v(f, "doc_type")[0] == "bank_transfer"
    assert v(f, "total_amount")[0] == 5_000_000
    assert v(f, "direction")[0] == "outgoing"
    assert v(f, "document_date")[0] == "2026-10-01"


def test_unlabelled_amount_is_only_a_suggestion():
    f = extract_fields("abc\n1.200.000\nxyz 350.000")
    assert v(f, "total_amount") == (1_200_000, 0.4)
    assert v(f, "doc_type") == ("unknown", 0.3)


def test_shorthand_on_documents_is_ignored():
    assert "total_amount" not in extract_fields("Trang 5 tr. 2\nGhi chú 950k")


def test_mst_checksum():
    assert mst_checksum_ok("0100109106")
    assert not mst_checksum_ok("0100109107")


def test_score_one_buckets():
    truth = {"total_amount": "2.350.000", "document_date": "2026-10-01", "seller_tax_id": "0100109106",
             "seller_name": "Công ty TNHH Vật tư Bình An"}
    fields = {"total_amount": {"value": 2_350_000, "confidence": 0.9},
              "document_date": {"value": "2026-10-02", "confidence": 0.85},
              "seller_tax_id": {"value": "0100109106", "confidence": 0.5}}
    assert score_one(fields, truth) == {"total_amount": "correct", "document_date": "wrong_confident",
                                        "seller_tax_id": "suggestion", "seller_name": "missed"}


class FakeText:
    name = "fake"

    def __init__(self, texts):
        self.texts = texts

    def extract(self, data, mime):
        return extract_fields(self.texts[data])


def test_bench_report(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"A")
    (tmp_path / "b.jpg").write_bytes(b"B")
    with open(tmp_path / "truth.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "category", "doc_type", "total_amount", "document_date", "seller_tax_id", "seller_name"])
        w.writerow(["a.jpg", "in_thang", "invoice", "2.350.000", "2026-10-01", "0100109106", "Vật tư Bình An"])
        w.writerow(["b.jpg", "chuyen_khoan", "bank_transfer", "5.000.000", "2026-10-01", "", ""])
    report = run_bench(FakeText({b"A": INVOICE, b"B": TRANSFER}), tmp_path, tmp_path / "truth.csv")
    assert report.fields["total_amount"].correct == 2
    md = render_markdown(report)
    assert "| total_amount | 100% | 0% |" in md and "chuyen_khoan" in md


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="cần tesseract")
def test_tesseract_end_to_end_on_rendered_invoice():
    """Ảnh tổng hợp, chỉ để kiểm tra đường ống chạy được, không đại diện cho ảnh thật."""
    from io import BytesIO

    PIL = pytest.importorskip("PIL")
    from PIL import Image, ImageDraw, ImageFont

    from app.ocr.tesseract import TesseractOcr

    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    img = Image.new("RGB", (1100, 520), "white")
    d = ImageDraw.Draw(img)
    for i, line in enumerate(INVOICE.strip().splitlines()):
        d.text((30, 20 + i * 52), line, fill="black", font=font)
    buf = BytesIO()
    img.save(buf, format="PNG")
    f = TesseractOcr().extract(buf.getvalue(), "image/png")
    assert f["total_amount"]["value"] == 2_350_000
    assert f["document_date"]["value"] == "2026-10-01"
    _ = PIL
