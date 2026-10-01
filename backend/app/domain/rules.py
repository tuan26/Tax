"""Rule chất lượng dữ liệu (V1). Hàm thuần, có mã và phiên bản.

Mỗi rule chỉ nhận bản ghi "dùng được" (đã xác nhận, hoặc mọi quyết định cốt lõi đạt HIGH), nên không
thể sinh phát hiện từ dữ liệu chưa chắc. Mỗi phát hiện bắt buộc có bằng chứng.

Rule V1 không kết luận về thuế: DQ-01 nói "chưa có chứng từ đi kèm", không nói "thiếu hóa đơn".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .money import find_amounts

PAYMENT_KINDS = {"bank_transfer_screenshot", "self_declared"}
DOCUMENT_KINDS = {"document"}


@dataclass
class RuleRecord:
    id: str
    kind: str                 # evidence_kind
    fields: dict              # giá trị cuối (đã xác nhận nếu có)
    evidence_items: list[str]
    texts: list[str] = field(default_factory=list)   # tin chữ của khách nằm trong bằng chứng
    created_order: int = 0


@dataclass
class Draft:
    rule_id: str
    rule_version: str
    fingerprint: str
    severity: str             # check | confirm
    record_id: str
    title: str
    detail: str
    amount: int | None
    evidence: list[str]

    def __post_init__(self):
        if not self.evidence:
            raise ValueError(f"[{self.rule_id}] phát hiện phải có bằng chứng")


def _money(v):
    return f"{v:,.0f}".replace(",", ".") + "đ" if v is not None else "—"


def _day(iso):
    if not iso:
        return "không rõ ngày"
    y, m, d = iso.split("-")
    return f"{d}/{m}/{y}"


def dq01_payment_without_document(records: list[RuleRecord], matched_payments: set[str]) -> list[Draft]:
    """Khoản chi (ảnh chuyển khoản hoặc chi tự khai) chưa được ghép với chứng từ nào."""
    out = []
    for r in records:
        f = r.fields
        if r.kind not in PAYMENT_KINDS or f.get("transaction_type") != "EXPENSE" or r.id in matched_payments:
            continue
        what = "Chuyển khoản" if r.kind == "bank_transfer_screenshot" else "Khoản chi khách tự báo"
        desc = f.get("description")
        out.append(Draft(
            "DQ-01", "1", f"DQ-01:{r.id}", "check" if r.kind == "bank_transfer_screenshot" else "confirm", r.id,
            "Khoản chi chưa có chứng từ đi kèm",
            f"{what} {_money(f.get('amount'))} ngày {_day(f.get('posting_date'))}"
            + (f', nội dung "{desc}"' if desc else ""),
            f.get("amount"), list(r.evidence_items)))
    return out


def dq02_possible_duplicate(records: list[RuleRecord]) -> list[Draft]:
    """Hai chứng từ cùng loại thu chi, cùng số tiền, cùng ngày."""
    out = []
    docs = [r for r in records if r.kind in DOCUMENT_KINDS | {"bank_transfer_screenshot"}]
    seen: dict = {}
    for r in sorted(docs, key=lambda r: r.created_order):
        f = r.fields
        when = f.get("document_date") or f.get("posting_date")
        if f.get("amount") is None or not when:
            continue
        key = (r.kind, f.get("transaction_type"), f["amount"], when)
        if key in seen:
            first = seen[key]
            out.append(Draft(
                "DQ-02", "1", f"DQ-02:{min(first.id, r.id)}:{max(first.id, r.id)}", "check", r.id,
                "Có thể trùng chứng từ",
                f"Hai chứng từ cùng {_money(f['amount'])}, cùng ngày {_day(when)}. Kiểm tra có phải gửi lại cùng "
                "một chứng từ không.", f["amount"], list(first.evidence_items) + list(r.evidence_items)))
        else:
            seen[key] = r
    return out


def dq03_document_fields(records: list[RuleRecord]) -> list[Draft]:
    """Chứng từ thiếu ngày, hoặc số khách nhắn khác số đã chốt."""
    out = []
    for r in records:
        if r.kind not in DOCUMENT_KINDS:
            continue
        f = r.fields
        if not f.get("document_date"):
            out.append(Draft(
                "DQ-03", "1", f"DQ-03:no_date:{r.id}", "confirm", r.id, "Chứng từ không có ngày",
                f"Chứng từ {_money(f.get('amount'))} không đọc được hoặc không ghi ngày lập. Hạch toán đang theo "
                f"ngày {_day(f.get('posting_date'))}.", f.get("amount"), list(r.evidence_items)))
        typed = {a.value for t in r.texts for a in find_amounts(t)}
        if typed and f.get("amount") is not None and f["amount"] not in typed:
            out.append(Draft(
                "DQ-03", "1", f"DQ-03:typed_mismatch:{r.id}", "check", r.id, "Số khách nhắn khác số đã chốt",
                f"Khách nhắn {', '.join(_money(v) for v in sorted(typed))}, sổ đang ghi {_money(f['amount'])}. "
                "Nên báo lại khách để thống nhất.", f["amount"], list(r.evidence_items)))
    return out


def evaluate(records: list[RuleRecord], matched_payments: set[str]) -> list[Draft]:
    return (dq01_payment_without_document(records, matched_payments) + dq02_possible_duplicate(records)
            + dq03_document_fields(records))


def match_evidence(payment: dict, document: dict) -> list[dict]:
    """Tiêu chí ghép, để giao diện nói được vì sao hai bản ghi có thể là một khoản."""
    out = []
    pa, da = payment.get("amount"), document.get("amount")
    out.append({"criterion": "amount", "ok": pa is not None and pa == da,
                "detail": f"{_money(pa)} và {_money(da)}"})
    pd, dd = payment.get("posting_date"), document.get("document_date") or document.get("posting_date")
    if pd and dd:
        gap = abs((date.fromisoformat(pd) - date.fromisoformat(dd)).days)
        out.append({"criterion": "date", "ok": gap <= 3, "detail": "cùng ngày" if gap == 0 else f"cách {gap} ngày"})
    else:
        out.append({"criterion": "date", "ok": None, "detail": "thiếu ngày để so"})
    out.append({"criterion": "type", "ok": document.get("transaction_type") == payment.get("transaction_type"),
                "detail": "cùng là khoản chi" if document.get("transaction_type") == "EXPENSE" else "khác loại thu chi"})
    return out
