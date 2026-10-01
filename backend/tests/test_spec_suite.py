"""Release gate: bộ ca gom tin trong spec/ phải qua toàn bộ, không có lần tự ghép sai nào."""

import json
from pathlib import Path

import pytest

from app.domain.evaluator import evaluate_grouping, evaluate_records, summarize
from app.domain.grouping import group_messages
from app.domain.normalize import normalize

SPEC = Path(__file__).resolve().parents[2] / "spec"
GROUPING = json.loads((SPEC / "grouping_cases.json").read_text())
RECORDS = {c["case_id"]: c for c in json.loads((SPEC / "records.expected.json").read_text())["cases"]}


def run_case(case):
    result = group_messages(case["input"])
    report, mapping = evaluate_grouping(case, result)
    evaluate_records(RECORDS[case["case_id"]], normalize(case["input"], result), mapping, report)
    return report


@pytest.mark.parametrize("case", GROUPING["cases"], ids=lambda c: c["case_id"])
def test_case(case):
    report = run_case(case)
    assert not report.violations, report.violations
    assert report.wrong_auto == 0, report.problems
    assert not report.problems, report.problems
    assert not report.record_problems, report.record_problems


def test_release_gate_thresholds():
    summary = summarize([run_case(c) for c in GROUPING["cases"]])
    gate = GROUPING["scoring"]["thresholds"]
    assert summary["ALL"]["wrong_auto_rate"] <= gate["wrong_auto_rate_max"]
    assert summary["ALL"]["must_not_auto_link_violations"] <= gate["must_not_auto_link_violations_max"]
    assert summary["ALL"]["cases_passed"] == len(GROUPING["cases"])
