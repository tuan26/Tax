"""Rút trường từ văn bản OCR thô (dùng cho engine chỉ trả về chữ, ví dụ Tesseract).

Mỗi trường có độ tin cậy theo mức bằng chứng: có nhãn rõ ("Tổng cộng", "MST") thì cao,
chỉ đoán theo vị trí thì thấp. Giá trị dưới 0,6 chỉ là gợi ý (xem normalize.OCR_SUGGESTION_ONLY_BELOW).
"""

from __future__ import annotations

import re
from datetime import date

from ..domain.money import find_formal_amounts
from ..domain.text import contains_any, fold

TOTAL_KEYS = [  # theo thứ tự ưu tiên
    ("tong cong thanh toan", 0.9), ("tong thanh toan", 0.9), ("tong tien thanh toan", 0.9),
    ("tong cong", 0.85), ("tong tien", 0.85), ("so tien", 0.85), ("thanh tien", 0.75), ("cong tien hang", 0.7),
    ("total", 0.8), ("phai tra", 0.8),
]
BANK_KEYS = ("chuyen tien thanh cong", "giao dich thanh cong", "chuyen khoan thanh cong", "so tai khoan",
             "ma giao dich", "tai khoan nguon", "tai khoan nhan")
INVOICE_KEYS = ("hoa don", "invoice")
RECEIPT_KEYS = ("phieu", "bien lai", "bill")
SELLER_KEYS = ("don vi ban hang", "don vi ban", "nguoi ban", "ten don vi", "ben ban")
SELLER_HINTS = ("cong ty", "cua hang", "ho kinh doanh", "dai ly", "doanh nghiep", "tnhh")

DATE_NUMERIC = re.compile(r"(?<!\d)(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?!\d)")
DATE_WORDS = re.compile(r"ngay\s*(\d{1,2})\s*thang\s*(\d{1,2})\s*nam\s*(\d{4})")
TAX_ID = re.compile(r"(?:mst|ma so thue)\s*[:.]?\s*((?:\d\s*){10}(?:-\s*(?:\d\s*){3})?)")


def _sv(value, confidence):
    return {"value": value, "confidence": round(confidence, 2)}


def mst_checksum_ok(digits: str) -> bool:
    """Số kiểm tra của mã số thuế 10 số. Dùng để tăng độ tin cậy, không dùng để loại."""
    d = re.sub(r"\D", "", digits)[:10]
    if len(d) != 10:
        return False
    weights = (31, 29, 23, 19, 17, 13, 7, 5, 3)
    check = 10 - sum(int(a) * w for a, w in zip(d[:9], weights)) % 11
    return check == int(d[9])


def _valid_date(d, m, y):
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def _solo_amount(lines: list[str]) -> int | None:
    """Số tiền duy nhất chiếm gần trọn một dòng, ví dụ "-5,000,000 VND"."""
    hits = []
    for line in lines:
        amounts = find_formal_amounts(line)
        rest = re.sub(r"[\s+\-]|vnd|đ|d\b", "", fold(line).replace(amounts[0].raw, "")) if len(amounts) == 1 else "x"
        if len(amounts) == 1 and not rest:
            hits.append(amounts[0].value)
    return hits[0] if len(set(hits)) == 1 else None


def extract_fields(text: str) -> dict:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    folded_lines = [fold(l) for l in lines]
    whole = "\n".join(folded_lines)
    out: dict = {}

    # loại chứng từ
    if contains_any(whole, BANK_KEYS):
        out["doc_type"] = _sv("bank_transfer", 0.85)
    elif contains_any(whole, INVOICE_KEYS):
        out["doc_type"] = _sv("invoice", 0.85)
    elif contains_any(whole, RECEIPT_KEYS):
        out["doc_type"] = _sv("receipt", 0.7)
    else:
        out["doc_type"] = _sv("unknown", 0.3)

    # tổng tiền: dòng có nhãn, ưu tiên nhãn mạnh, rồi dòng ở dưới cùng
    best = None
    for rank, (key, conf) in enumerate(TOTAL_KEYS):
        for i, fl in enumerate(folded_lines):
            if not contains_any(fl, (key,)):
                continue
            amounts = find_formal_amounts(lines[i])
            if not amounts and i + 1 < len(lines):
                amounts = find_formal_amounts(lines[i + 1])
            if amounts:
                cand = (rank, -i, max(a.value for a in amounts), conf)
                if best is None or cand[:2] < best[:2]:
                    best = cand
    if best:
        out["total_amount"] = _sv(best[2], best[3])
    elif out["doc_type"]["value"] == "bank_transfer" and (solo := _solo_amount(lines)):
        # Ảnh chuyển khoản in số tiền to trên một dòng riêng, thường không có nhãn.
        out["total_amount"] = _sv(solo, 0.8)
    else:
        everything = find_formal_amounts(text)
        if everything:
            out["total_amount"] = _sv(max(a.value for a in everything), 0.4)

    # chiều tiền với ảnh chuyển khoản
    if out["doc_type"]["value"] == "bank_transfer":
        if re.search(r"(^|\s)-\s?\d", text) or contains_any(whole, ("chuyen di", "ghi no", "tai khoan nguon")):
            out["direction"] = _sv("outgoing", 0.8)
        elif re.search(r"(^|\s)\+\s?\d", text) or contains_any(whole, ("nhan tien", "ghi co")):
            out["direction"] = _sv("incoming", 0.8)

    # ngày
    m = DATE_WORDS.search(whole)
    if m and _valid_date(*m.groups()):
        out["document_date"] = _sv(_valid_date(*m.groups()), 0.85)
    else:
        for fl in folded_lines:
            dm = DATE_NUMERIC.search(fl)
            if dm and _valid_date(*dm.groups()):
                conf = 0.8 if contains_any(fl, ("ngay", "date", "thoi gian")) else 0.6
                out["document_date"] = _sv(_valid_date(*dm.groups()), conf)
                break

    # mã số thuế người bán: cái đầu tiên (người bán thường in phía trên người mua)
    tm = TAX_ID.search(whole)
    if tm:
        digits = re.sub(r"\s", "", tm.group(1))
        out["seller_tax_id"] = _sv(digits, 0.9 if mst_checksum_ok(digits) else 0.6)

    # tên người bán
    name = None
    for i, fl in enumerate(folded_lines):
        if contains_any(fl, SELLER_KEYS) and ":" in lines[i]:
            name = (lines[i].split(":", 1)[1].strip(), 0.8)
            break
    if name is None:
        for i, fl in enumerate(folded_lines[:6]):
            if contains_any(fl, SELLER_HINTS):
                name = (lines[i], 0.6)
                break
    if name and name[0]:
        out["counterparty_name"] = _sv(name[0], name[1])

    out["raw_text"] = text
    return out
