import pytest

from app.domain.rules import Draft, RuleRecord, evaluate, match_evidence


def rec(id, kind, ttype, amount, posting, doc_date=None, texts=(), order=0):
    return RuleRecord(id, kind, {"transaction_type": ttype, "amount": amount, "posting_date": posting,
                                 "document_date": doc_date, "description": None}, [f"{id}-ev"], list(texts), order)


def ids(drafts, rule):
    return sorted(d.record_id for d in drafts if d.rule_id == rule)


def test_dq01_payment_without_document():
    rs = [rec("t", "bank_transfer_screenshot", "EXPENSE", 5_000_000, "2026-10-01"),
          rec("s", "self_declared", "EXPENSE", 500_000, "2026-10-01"),
          rec("i", "self_declared", "INCOME", 9_000_000, "2026-10-01"),
          rec("d", "document", "EXPENSE", 5_000_000, "2026-10-01", "2026-10-01")]
    assert ids(evaluate(rs, set()), "DQ-01") == ["s", "t"], "doanh thu và chứng từ không thuộc DQ-01"
    assert ids(evaluate(rs, {"t"}), "DQ-01") == ["s"], "đã ghép thì không còn phát hiện"


def test_dq02_duplicates():
    rs = [rec("a", "document", "EXPENSE", 950_000, "2026-10-02", "2026-10-02", order=1),
          rec("b", "document", "EXPENSE", 950_000, "2026-10-05", "2026-10-02", order=2),
          rec("c", "document", "EXPENSE", 950_000, "2026-10-05", "2026-10-03", order=3)]
    d = [x for x in evaluate(rs, set()) if x.rule_id == "DQ-02"]
    assert [x.record_id for x in d] == ["b"] and set(d[0].evidence) == {"a-ev", "b-ev"}


def test_dq03_document_fields():
    rs = [rec("n", "document", "EXPENSE", 1_000_000, "2026-10-01", None),
          rec("m", "document", "EXPENSE", 2_350_000, "2026-10-01", "2026-10-01", texts=["2tr5"]),
          rec("ok", "document", "EXPENSE", 2_500_000, "2026-10-01", "2026-10-01", texts=["2tr5", "tiền thịt"])]
    d = {x.fingerprint for x in evaluate(rs, set()) if x.rule_id == "DQ-03"}
    assert d == {"DQ-03:no_date:n", "DQ-03:typed_mismatch:m"}


def test_finding_requires_evidence():
    with pytest.raises(ValueError):
        Draft("DQ-01", "1", "x", "check", "r", "t", "d", 1, [])


def test_match_evidence():
    ev = match_evidence({"amount": 5_000_000, "posting_date": "2026-10-01", "transaction_type": "EXPENSE"},
                        {"amount": 5_000_000, "document_date": "2026-10-02", "transaction_type": "EXPENSE"})
    assert [(e["criterion"], e["ok"]) for e in ev] == [("amount", True), ("date", True), ("type", True)]
