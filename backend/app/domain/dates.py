"""Ngày kinh doanh và ngày tương đối."""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .text import contains_any


def parse_cutoff(cutoff: str) -> time:
    h, m = cutoff.split(":")
    return time(int(h), int(m))


def local_datetime(sent_at: str | None, tz: str) -> datetime | None:
    if not sent_at:
        return None
    return datetime.fromisoformat(sent_at).astimezone(ZoneInfo(tz))


def business_date(local: datetime, cutoff: str) -> date:
    """Tin gửi trước giờ chốt được tính vào ngày hôm trước."""
    d = local.date()
    return d - timedelta(days=1) if local.time() < parse_cutoff(cutoff) else d


def before_cutoff(local: datetime, cutoff: str) -> bool:
    return local.time() < parse_cutoff(cutoff)


TODAY = ("hom nay", "toi nay", "sang nay", "trua nay", "chieu nay")
YESTERDAY = ("hom qua",)
LAST_NIGHT = ("toi qua", "dem qua")
DAY_BEFORE = ("hom kia",)


def relative_kind(folded: str) -> str | None:
    if contains_any(folded, LAST_NIGHT):
        return "last_night"
    if contains_any(folded, YESTERDAY):
        return "yesterday"
    if contains_any(folded, DAY_BEFORE):
        return "day_before"
    if contains_any(folded, TODAY):
        return "today"
    return None


@dataclass
class Resolved:
    value: date | None
    confidence: float
    candidates: list[date] = field(default_factory=list)


def resolve_relative(kind: str, local: datetime | None, cutoff: str, base: date | None = None) -> Resolved:
    """Quy đổi ngày tương đối theo thời điểm gửi.

    Không có thời điểm gửi (nhập tay) thì không suy ra được ngày tuyệt đối: trả về
    ngày nền do kế toán chọn với độ tin cậy trung bình, để bản ghi vào hàng chờ duyệt.
    """
    if local is None:
        return Resolved(base, 0.6 if base else 0.0)
    bd = business_date(local, cutoff)
    late = before_cutoff(local, cutoff)
    if kind == "today":
        return Resolved(bd, 0.95)
    if kind == "day_before":
        return Resolved(bd - timedelta(days=2), 0.9)
    if kind in ("yesterday", "last_night"):
        if late:
            # 1 giờ sáng nói "tối qua": có thể là tối vừa hết hoặc tối hôm trước nữa.
            return Resolved(None, 0.0, [bd - timedelta(days=1), bd])
        return Resolved(bd - timedelta(days=1), 0.92)
    return Resolved(None, 0.0)
