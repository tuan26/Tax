"""Đọc số tiền gõ tắt kiểu Việt Nam: 12tr5, 950k, 1t2, 2.350.000đ, 2,35tr, 2 triệu 350."""

import re
from dataclasses import dataclass

from .text import fold


@dataclass(frozen=True)
class Amount:
    value: int
    start: int
    end: int
    raw: str


# Vị trí trả về là vị trí trên chuỗi đã fold. fold() giữ nguyên độ dài với chữ Việt
# dựng sẵn (NFC) sau khi bỏ dấu, nhưng không cam kết điều đó; chỉ dùng vị trí để
# so thứ tự và cắt đoạn trên chính chuỗi đã fold.
_PATTERNS = [
    # 2 triệu 350
    ("million_words", re.compile(r"(?<![\d.,])(\d+)\s*trieu\s+(\d{1,3})(?![\d])")),
    # 12tr5, 2,35tr, 6tr, 1t2, 2 trieu
    ("million", re.compile(r"(?<![\d.,])(\d+(?:[.,]\d+)?)\s*(trieu|tr|t)(\d{1,3})?(?![a-z0-9])")),
    # 950k, 1k5
    ("thousand", re.compile(r"(?<![\d.,])(\d+(?:[.,]\d+)?)\s*k(\d{1,2})?(?![a-z0-9])")),
    # 2.350.000 hoặc 2,350,000, có thể kèm đ/dong/vnd
    ("grouped", re.compile(r"(?<![\d.,])(\d{1,3}(?:([.,])\d{3})(?:\2\d{3})*)(?![\d])\s*(?:d|dong|vnd)?(?![a-z0-9])")),
    # 2350000đ: số liền phải có đơn vị tiền
    ("plain", re.compile(r"(?<![\d.,])([1-9]\d{3,})\s*(?:d|dong|vnd)(?![a-z0-9])")),
]


def _to_float(num: str) -> float:
    return float(num.replace(",", "."))


def _value(kind: str, m: re.Match) -> int | None:
    if kind == "million_words":
        frac = m.group(2)
        return int(m.group(1)) * 1_000_000 + int(frac) * 10 ** (6 - len(frac))
    if kind == "million":
        base, frac = m.group(1), m.group(3)
        if frac and ("." in base or "," in base):
            return None
        value = round(_to_float(base) * 1_000_000)
        if frac:
            value += int(frac) * 10 ** (6 - len(frac))
        return value
    if kind == "thousand":
        base, frac = m.group(1), m.group(2)
        if frac and ("." in base or "," in base):
            return None
        value = round(_to_float(base) * 1_000)
        if frac:
            value += int(frac) * 10 ** (3 - len(frac))
        return value
    if kind == "grouped":
        return int(re.sub(r"[.,]", "", m.group(1)))
    if kind == "plain":
        return int(m.group(1))
    return None


def find_amounts(text: str) -> list[Amount]:
    """Mọi số tiền trong câu, theo thứ tự xuất hiện, không chồng lấn."""
    folded = fold(text)
    taken: list[tuple[int, int]] = []
    found: list[Amount] = []
    for kind, pattern in _PATTERNS:
        for m in pattern.finditer(folded):
            start, end = m.span()
            if any(start < e and s < end for s, e in taken):
                continue
            value = _value(kind, m)
            if value is None or value <= 0:
                continue
            taken.append((start, end))
            found.append(Amount(value, start, end, m.group(0).strip()))
    return sorted(found, key=lambda a: a.start)


_FORMAL = {"grouped", "plain", "million_words"}


def find_formal_amounts(text: str) -> list[Amount]:
    """Số tiền trên chứng từ in (OCR): chỉ dạng có dấu phân cách hoặc có đơn vị tiền.

    Bỏ dạng gõ tắt (12tr5, 950k) vì trên chứng từ chúng thường là lỗi đọc, ví dụ "5 tr." trong "Trang".
    """
    folded = fold(text)
    taken, found = [], []
    for kind, pattern in _PATTERNS:
        if kind not in _FORMAL:
            continue
        for m in pattern.finditer(folded):
            start, end = m.span()
            if any(start < e and s < end for s, e in taken):
                continue
            value = _value(kind, m)
            if value is None or value <= 0:
                continue
            taken.append((start, end))
            found.append(Amount(value, start, end, m.group(0).strip()))
    return sorted(found, key=lambda a: a.start)
