from datetime import date

import pytest

from app.domain.dates import business_date, local_datetime, resolve_relative
from app.domain.money import find_amounts


@pytest.mark.parametrize("text,expected", [
    ("12tr5", [12_500_000]),
    ("8tr4", [8_400_000]),
    ("6tr", [6_000_000]),
    ("1tr25", [1_250_000]),
    ("1tr250", [1_250_000]),
    ("2,35tr", [2_350_000]),
    ("1.5tr", [1_500_000]),
    ("2 triệu 350", [2_350_000]),
    ("2 triệu", [2_000_000]),
    ("1t2", [1_200_000]),
    ("950k", [950_000]),
    ("1k5", [1_500]),
    ("2.350.000đ", [2_350_000]),
    ("2,350,000 vnd", [2_350_000]),
    ("2350000đ", [2_350_000]),
    ("Hôm nay bán 8tr4, nhập hàng 3tr", [8_400_000, 3_000_000]),
    ("Sửa lại: doanh thu hôm qua 9tr chứ không phải 8tr", [9_000_000, 8_000_000]),
    ("chi 500k tiền ship", [500_000]),
])
def test_amounts(text, expected):
    assert [a.value for a in find_amounts(text)] == expected


@pytest.mark.parametrize("text", [
    "Thịt heo 15kg", "5 thùng nước", "HĐ số 0451", "ngày 12/10", "Mai anh qua lấy hàng nhé", "2350000",
])
def test_not_amounts(text):
    assert find_amounts(text) == []


def test_business_date_cutoff():
    tz = "Asia/Ho_Chi_Minh"
    assert business_date(local_datetime("2026-10-02T00:45:00+07:00", tz), "04:00") == date(2026, 10, 1)
    assert business_date(local_datetime("2026-10-02T04:00:00+07:00", tz), "04:00") == date(2026, 10, 2)
    # Giờ UTC phải được quy đổi trước khi xét giờ chốt.
    assert business_date(local_datetime("2026-10-01T18:30:00Z", tz), "04:00") == date(2026, 10, 1)


def test_relative_last_night_after_midnight_is_ambiguous():
    local = local_datetime("2026-10-02T01:30:00+07:00", "Asia/Ho_Chi_Minh")
    r = resolve_relative("last_night", local, "04:00")
    assert r.value is None and r.candidates == [date(2026, 9, 30), date(2026, 10, 1)]


def test_relative_without_send_time_is_not_fabricated():
    r = resolve_relative("yesterday", None, "04:00", base=date(2026, 10, 3))
    assert r.value == date(2026, 10, 3) and r.confidence < 0.9
