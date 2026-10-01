"""Chấm điểm một engine gom tin theo spec/grouping_cases.json và spec/records.expected.json.

Mỗi quyết định kỳ vọng (nhóm, liên kết, item không gom) cho ra một kết quả:
- auto_correct: kỳ vọng chắc chắn và hệ thống tự quyết đúng.
- review_flagged: hệ thống đưa vào hàng chờ duyệt.
- wrong_auto: hệ thống tự quyết sai, tự quyết khi bằng chứng chưa đủ, hoặc bỏ qua im lặng.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .grouping import AMBIGUOUS, CONFIDENT, NONE_CANDIDATE, UNMATCHED, GroupingResult
from .normalize import Record, description_matches
from .text import fold

BANDS = (("HIGH", 0.90), ("MEDIUM", 0.60), ("LOW", 0.0))


def band(value, confidence) -> str:
    if value is None:
        return "NONE"
    c = confidence or 0.0
    return next(name for name, low in BANDS if c >= low)


@dataclass
class CaseReport:
    case_id: str
    source_type: str
    outcomes: Counter = field(default_factory=Counter)
    by_expected: Counter = field(default_factory=Counter)
    violations: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    record_problems: list[str] = field(default_factory=list)

    @property
    def wrong_auto(self) -> int:
        return self.outcomes["wrong_auto"]

    @property
    def passed(self) -> bool:
        return not self.violations and not self.problems and not self.record_problems and self.wrong_auto == 0


def _map_groups(expected_groups, result: GroupingResult) -> dict[str, str]:
    """Nhãn nhóm trong spec → khóa nhóm hệ thống, so theo tập anchor (và đoạn cho tin nhiều giao dịch)."""
    mapping = {}
    used = set()
    for eg in expected_groups:
        anchors = set(eg["anchor_items"])
        options = [g for g in result.groups if set(g.anchor_items) == anchors and g.key not in used]
        if eg.get("segment") and len(options) > 1:
            needle = fold(eg["segment"])
            options = [g for g in options if g.segment and (needle in fold(g.segment) or fold(g.segment) in needle)]
        if options:
            mapping[eg["group_key"]] = options[0].key
            used.add(options[0].key)
    return mapping


def _resolve(label: str, mapping: dict[str, str]) -> str:
    if label == NONE_CANDIDATE:
        return label
    return "+".join(sorted(mapping.get(p, f"?{p}") for p in label.split("+")))


def _norm(label: str) -> str:
    return label if label == NONE_CANDIDATE else "+".join(sorted(label.split("+")))


def _system_view(result: GroupingResult):
    links = {}
    for l in result.links:
        links.setdefault(l.item, []).append(l)
    unmatched = {u.item: u for u in result.unmatched}
    anchors = {}
    for g in result.groups:
        for a in g.anchor_items:
            anchors.setdefault(a, []).append(g)
    return links, unmatched, anchors


def evaluate_grouping(case: dict, result: GroupingResult) -> tuple[CaseReport, dict[str, str]]:
    exp = case["expected"]
    msgs = case["input"]["messages"]
    report = CaseReport(case["case_id"], msgs[0]["source_type"] if msgs else "UNKNOWN")
    mapping = _map_groups(exp["groups"], result)
    links, unmatched, anchors = _system_view(result)

    def out(expected_status, outcome, note=None):
        report.by_expected[expected_status] += 1
        report.outcomes[outcome] += 1
        if outcome == "wrong_auto" and note:
            report.problems.append(note)

    # Nhóm
    for eg in exp["groups"]:
        sys_key = mapping.get(eg["group_key"])
        sys_group = result.group(sys_key) if sys_key else None
        if eg["status"] == CONFIDENT:
            if sys_group and sys_group.status == CONFIDENT:
                out(CONFIDENT, "auto_correct")
            elif sys_group:
                out(CONFIDENT, "review_flagged")
            else:
                touched = [g for a in eg["anchor_items"] for g in anchors.get(a, [])]
                if touched and all(g.status != CONFIDENT for g in touched):
                    out(CONFIDENT, "review_flagged")
                else:
                    out(CONFIDENT, "wrong_auto", f"nhóm {eg['group_key']} {eg['anchor_items']} bị chia/gộp sai")
        else:
            touched = {g.key: g for a in eg["anchor_items"] for g in anchors.get(a, [])}
            if touched and all(g.status != CONFIDENT for g in touched.values()):
                out(AMBIGUOUS, "review_flagged")
            else:
                out(AMBIGUOUS, "wrong_auto", f"nhóm mơ hồ {eg['anchor_items']} bị tự quyết")

    # Liên kết
    for el in exp["links"]:
        item = el["item"]
        sys_links = links.get(item, [])
        sys_link = next((l for l in sys_links if l.role == el["role"]), sys_links[0] if sys_links else None)
        um = unmatched.get(item)
        if el["status"] == CONFIDENT:
            want = sorted(mapping.get(t, f"?{t}") for t in el["targets"])
            if sys_link and sys_link.status == CONFIDENT:
                if sorted(sys_link.targets) == want:
                    out(CONFIDENT, "auto_correct")
                else:
                    out(CONFIDENT, "wrong_auto", f"{item} gán vào {sys_link.targets}, đúng là {want}")
            elif sys_link or (um and um.needs_review):
                out(CONFIDENT, "review_flagged")
            else:
                out(CONFIDENT, "wrong_auto", f"{item} bị bỏ qua hoặc xử lý sai vai trò")
        else:
            if sys_link and sys_link.status == AMBIGUOUS:
                out(AMBIGUOUS, "review_flagged")
                want = {_resolve(c, mapping) for c in el["candidates"]}
                have = {_norm(c) for c in sys_link.candidates or []}
                missing = want - have
                if missing:
                    report.problems.append(f"{item} thiếu ứng viên {sorted(missing)}")
            elif um and um.needs_review:
                out(AMBIGUOUS, "review_flagged")
            else:
                out(AMBIGUOUS, "wrong_auto", f"{item} mơ hồ nhưng bị tự quyết")

    # Item không thuộc nhóm nào
    for eu in exp["unmatched"]:
        item = eu["item"]
        um = unmatched.get(item)
        auto_linked = any(l.status == CONFIDENT for l in links.get(item, [])) or any(
            g.status == CONFIDENT for g in anchors.get(item, []))
        status = "UNMATCHED_REVIEW" if eu["needs_review"] else UNMATCHED
        if auto_linked:
            out(status, "wrong_auto", f"{item} lẽ ra không thuộc nhóm nào")
        elif um is None:
            out(status, "review_flagged")
        elif eu["needs_review"] and not um.needs_review:
            out(status, "wrong_auto", f"{item} cần kế toán xem nhưng bị ẩn")
        elif eu["needs_review"]:
            out(status, "review_flagged")
        else:
            out(status, "auto_correct")

    # Cặp cấm tự gom
    def side_groups(ref):
        if ref in mapping:
            return {mapping[ref]}
        gs = {g.key for g in anchors.get(ref, []) if g.status == CONFIDENT}
        for l in links.get(ref, []):
            if l.status == CONFIDENT:
                gs |= set(l.targets or [])
        return gs

    for pair in exp["must_not_auto_link"]:
        if side_groups(pair["a"]) & side_groups(pair["b"]):
            report.violations.append(f"{pair['a']} bị tự gom với {pair['b']}: {pair['reason']}")
            report.outcomes["wrong_auto"] += 1

    return report, mapping


def _check_decision(name, exp, got, problems, key):
    got_band = band(got.value, got.confidence)
    if got_band not in exp["confidence"]:
        problems.append(f"{key}.{name}: band {got_band}, cho phép {exp['confidence']}")
    if exp.get("value") is not None and got.value != exp["value"]:
        problems.append(f"{key}.{name}: {got.value!r} ≠ {exp['value']!r}")
    if exp.get("value") is None and got.value is not None and "NONE" in exp["confidence"] and len(exp["confidence"]) == 1:
        problems.append(f"{key}.{name}: phải để trống cho kế toán chọn, hệ thống lại chọn {got.value!r}")
    if exp.get("candidates"):
        missing = [c for c in exp["candidates"] if c not in (got.candidates or [])]
        if missing:
            problems.append(f"{key}.{name}: thiếu ứng viên {missing}")


def evaluate_records(rcase: dict, records: list[Record], mapping: dict[str, str], report: CaseReport):
    problems = report.record_problems
    count = rcase["record_count"]
    if isinstance(count, int) and len(records) != count:
        problems.append(f"số bản ghi {len(records)} ≠ {count}")
    if isinstance(count, dict) and not (count["min"] <= len(records) <= count["max"]):
        problems.append(f"số bản ghi {len(records)} ngoài khoảng {count}")

    by_group = {r.group_key: r for r in records}
    rec_key_map = {}
    for er in rcase["records"]:
        sys_key = mapping.get(er["from_groups"][0])
        rec = by_group.get(sys_key)
        k = er["record_key"]
        if rec is None:
            problems.append(f"{k}: không có bản ghi cho nhóm {er['from_groups']}")
            continue
        rec_key_map[k] = rec.key
        for name, exp_dec in er["decisions"].items():
            if name == "message_group":
                got_band = band(True, rec.decisions[name].confidence)
                if got_band not in exp_dec["confidence"]:
                    problems.append(f"{k}.message_group: band {got_band}")
                continue
            _check_decision(name, exp_dec, rec.decisions[name], problems, k)
        if set(rec.evidence_items) != set(er["evidence_items"]):
            problems.append(f"{k}: bằng chứng {sorted(rec.evidence_items)} ≠ {sorted(er['evidence_items'])}")
        if rec.evidence_kind != er["evidence_kind"]:
            problems.append(f"{k}: loại bằng chứng {rec.evidence_kind} ≠ {er['evidence_kind']}")
        if rec.sent_date != er["sent_date"]:
            problems.append(f"{k}: ngày gửi {rec.sent_date} ≠ {er['sent_date']}")
        if er["review_required"] is not None and rec.review_required != er["review_required"]:
            problems.append(f"{k}: cờ duyệt {rec.review_required} ≠ {er['review_required']}")
        missing = set(er.get("review_reasons", [])) - set(rec.review_reasons)
        if missing:
            problems.append(f"{k}: thiếu lý do duyệt {sorted(missing)}")
        if er.get("description_contains") and not description_matches(rec.description, er["description_contains"]):
            problems.append(f"{k}: mô tả {rec.description!r} không chứa {er['description_contains']!r}")
        if er.get("status") and rec.status != er["status"]:
            problems.append(f"{k}: trạng thái {rec.status} ≠ {er['status']}")
    for er in rcase["records"]:
        if er.get("supersedes"):
            got = next((r.supersedes for r in records if r.key == rec_key_map.get(er["record_key"])), None)
            if got != rec_key_map.get(er["supersedes"]):
                problems.append(f"{er['record_key']}: phải thay thế {er['supersedes']}")
    for c in rcase.get("constraints", []):
        items = set(c["items"])
        for r in records:
            if items & set(r.evidence_items) and r.review_required != c["review_required"]:
                problems.append(f"{r.key}: vi phạm ràng buộc {c['note']}")


def summarize(reports: list[CaseReport]) -> dict:
    """Chỉ số tổng, tách theo source_type như yêu cầu của pilot."""
    def metrics(rs):
        o, e = Counter(), Counter()
        for r in rs:
            o.update(r.outcomes)
            e.update(r.by_expected)
        total = sum(e.values())
        return {
            "cases": len(rs),
            "decisions": total,
            "auto_correct_rate": o["auto_correct"] / max(1, e[CONFIDENT] + e[UNMATCHED]),
            "wrong_auto_rate": o["wrong_auto"] / max(1, total),
            "human_review_rate": o["review_flagged"] / max(1, total),
            "unnecessary_review": o["review_flagged"] - e[AMBIGUOUS] - e["UNMATCHED_REVIEW"],
            "wrong_auto": o["wrong_auto"],
            "must_not_auto_link_violations": sum(len(r.violations) for r in rs),
            "cases_passed": sum(r.passed for r in rs),
        }

    out = {"ALL": metrics(reports)}
    for source in sorted({r.source_type for r in reports}):
        out[source] = metrics([r for r in reports if r.source_type == source])
    return out
