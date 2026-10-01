"""Chuẩn hóa nhóm thành bản ghi thu chi: MESSAGE_GROUP → RECORD.

Mỗi quyết định suy luận có độ tin cậy riêng: gom nhóm, loại thu chi, số tiền, ngày
chứng từ, ngày hạch toán. Số tiền đọc rất chắc không làm cả bản ghi trông chắc theo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .dates import business_date, resolve_relative
from .grouping import AMBIGUOUS, CONFIDENT, Group, GroupingResult, Item, _items
from .text import fold

HIGH = 0.90
GROUP_CONFIDENCE = {CONFIDENT: 0.95, AMBIGUOUS: 0.5}
DOCUMENT_DEFAULT_DATE_CONFIDENCE = 0.7
SELF_DECLARED_CONFIDENCE = 0.95
DATE_ANNOTATION_CONFIDENCE = 0.92
# OCR dưới ngưỡng này chỉ là gợi ý cho kế toán, không được thành giá trị của bản ghi.
OCR_SUGGESTION_ONLY_BELOW = 0.60


@dataclass
class Decision:
    value: object
    confidence: float | None
    candidates: list = field(default_factory=list)

    def to_dict(self):
        d = {"value": self.value, "confidence": self.confidence}
        if self.candidates:
            d["candidates"] = self.candidates
        return d


@dataclass
class Record:
    key: str
    group_key: str
    evidence_items: list[str]
    evidence_kind: str
    decisions: dict[str, Decision]
    sent_date: str | None
    review_required: bool
    review_reasons: list[str]
    description: str | None
    status: str = "ACTIVE"
    supersedes: str | None = None

    def to_dict(self):
        return {
            "record_key": self.key,
            "from_groups": [self.group_key],
            "evidence_items": self.evidence_items,
            "evidence_kind": self.evidence_kind,
            "decisions": {k: v.to_dict() for k, v in self.decisions.items()},
            "sent_date": self.sent_date,
            "review_required": self.review_required,
            "review_reasons": self.review_reasons,
            "description": self.description,
            "status": self.status,
            "supersedes": self.supersedes,
        }


def _iso(d):
    return d.isoformat() if isinstance(d, date) else d


class _Normalizer:
    def __init__(self, doc: dict, result: GroupingResult):
        self.doc = doc
        self.result = result
        self.cutoff = doc["customer"]["business_day_cutoff"]
        self.items = {it.ref: it for it in _items(doc)}

    def _bd(self, it: Item) -> date | None:
        if it.local is None:
            bd = it.message.get("business_date")
            return date.fromisoformat(bd) if bd else None
        return business_date(it.local, self.cutoff)

    def _links_to(self, g: Group, role=None, status=CONFIDENT):
        out = []
        for l in self.result.links:
            if role and l.role != role:
                continue
            if l.status != status:
                continue
            keys = l.targets if status == CONFIDENT else [k for c in (l.candidates or []) for k in c.split("+")]
            if g.key in (keys or []):
                out.append(l)
        return out

    def _first_anchor(self, g: Group) -> Item:
        return min((self.items[a] for a in g.anchor_items), key=lambda it: it.order)

    def _sent_date(self, it: Item):
        return it.local.date().isoformat() if it.local else None

    # ---- documents

    def _document(self, g: Group, key: str) -> Record:
        docs = [self.items[a] for a in g.anchor_items]
        first = self._first_anchor(g)
        reasons: list[str] = []
        types = {it.ext("doc_type") for it in docs} - {None}

        # loại thu chi
        if types == {"bank_transfer"}:
            direction = docs[0].extraction.get("direction") if docs[0].extraction else None
            if direction and direction.get("value") in ("outgoing", "incoming"):
                ttype = Decision("EXPENSE" if direction["value"] == "outgoing" else "INCOME",
                                 direction.get("confidence"))
            else:
                ttype = Decision(None, None)
        elif types and types <= {"invoice", "receipt", "handwritten_receipt"}:
            conf = min(it.extraction["doc_type"]["confidence"] for it in docs
                       if it.extraction and it.extraction.get("doc_type"))
            ttype = Decision("EXPENSE", min(conf, 0.95))
        else:
            ttype = Decision(None, None)

        failed = [it for it in docs if (it.extraction or {}).get("status") in ("failed", "empty")]
        if failed:
            reasons.append("ocr_failed" if any(it.extraction["status"] == "failed" for it in failed) else "ocr_empty")

        # số tiền
        ocr_all = [(it.ext("total_amount"), it.extraction["total_amount"]["confidence"])
                   for it in docs if it.ext("total_amount") is not None]
        ocr = [(v, c) for v, c in ocr_all if c >= OCR_SUGGESTION_ONLY_BELOW]
        ocr_guesses = sorted({v for v, c in ocr_all if c < OCR_SUGGESTION_ONLY_BELOW})
        ocr_values = {v for v, _ in ocr}
        typed = [v for l in self._links_to(g, "amount_annotation") for v in l.data.get("amounts", [])]
        typed_ambiguous = [v for l in self._links_to(g, "amount_annotation", AMBIGUOUS)
                           for v in l.data.get("amounts", [])]
        if len(ocr_values) > 1:
            amount = Decision(None, None, sorted(ocr_values | set(typed)))
            reasons.append("amount_conflict")
        elif ocr_values and typed:
            ocr_value, ocr_conf = ocr[0]
            if set(typed) == {ocr_value}:
                amount = Decision(ocr_value, max(ocr_conf, 0.97))
            else:
                amount = Decision(None, None, sorted({ocr_value} | set(typed)))
                reasons.append("amount_conflict")
        elif ocr_values:
            amount = Decision(ocr[0][0], ocr[0][1])
        elif typed:
            amount = Decision(typed[0], SELF_DECLARED_CONFIDENCE) if len(set(typed)) == 1 else Decision(
                None, None, sorted(set(typed)))
        elif typed_ambiguous:
            amount = Decision(None, None, sorted(set(typed_ambiguous) | set(ocr_guesses)))
            reasons.append("amount_unresolved")
        elif ocr_guesses:
            amount = Decision(None, None, ocr_guesses)
            reasons.append("amount_low_confidence")
        else:
            amount = Decision(None, None)
            reasons.append("amount_missing")

        # ngày chứng từ
        dated = [(it.ext("document_date"), it.extraction["document_date"]["confidence"])
                 for it in docs if it.ext("document_date") is not None]
        sure_dates = [(v, c) for v, c in dated if c >= OCR_SUGGESTION_ONLY_BELOW]
        if sure_dates:
            doc_date = Decision(sure_dates[0][0], sure_dates[0][1])
        else:
            doc_date = Decision(None, None, sorted({v for v, _ in dated}))

        # ngày hạch toán
        default = Decision(_iso(self._bd(first)), DOCUMENT_DEFAULT_DATE_CONFIDENCE)
        if doc_date.value is not None:
            default = Decision(doc_date.value, doc_date.confidence)
        posting = default
        for l in self._links_to(g, "date_annotation") + self._links_to(g, "date_correction"):
            r = resolve_relative(l.data["relative"], self.items[l.item].local, self.cutoff,
                                 self._bd(self.items[l.item]))
            posting = Decision(_iso(r.value), DATE_ANNOTATION_CONFIDENCE if r.value else None,
                               [_iso(c) for c in r.candidates])
        ambiguous_dates = self._links_to(g, "date_correction", AMBIGUOUS) + self._links_to(
            g, "date_annotation", AMBIGUOUS)
        if ambiguous_dates:
            options = {default.value}
            for l in ambiguous_dates:
                r = resolve_relative(l.data["relative"], self.items[l.item].local, self.cutoff,
                                     self._bd(self.items[l.item]))
                options |= {_iso(r.value)} if r.value else {_iso(c) for c in r.candidates}
            posting = Decision(None, None, sorted(o for o in options if o))
            reasons.append("posting_date_ambiguous")
        elif posting.value is None and posting.candidates:
            reasons.append("posting_date_ambiguous")

        captions = self._links_to(g, "caption")
        if self._links_to(g, "caption", AMBIGUOUS):
            reasons.append("caption_ambiguous")
        description = captions[0].data.get("text") if captions else next(
            (it.ext("description") for it in docs if it.ext("description")),
            next((it.ext("counterparty_name", 0.6) for it in docs if it.ext("counterparty_name", 0.6)), None))

        evidence = list(g.anchor_items)
        for l in sorted((l for l in self.result.links if l.status == CONFIDENT and l.role != "correction"
                         and g.key in (l.targets or [])), key=lambda l: self.items[l.item].order):
            evidence.append(l.item)

        kind = "bank_transfer_screenshot" if types == {"bank_transfer"} else "document"
        decisions = {
            "message_group": Decision(None, GROUP_CONFIDENCE[g.status]),
            "transaction_type": ttype,
            "amount": amount,
            "document_date": doc_date,
            "posting_date": posting,
        }
        return self._finish(key, g, evidence, kind, decisions, self._sent_date(first), reasons, description)

    # ---- self-declared

    def _self_declared(self, g: Group, key: str) -> Record:
        it = self._first_anchor(g)
        reasons = []
        rel = g.facts.get("relative")
        if rel:
            r = resolve_relative(rel, it.local, self.cutoff, self._bd(it))
            posting = Decision(_iso(r.value), r.confidence if r.value else None, [_iso(c) for c in r.candidates])
            if r.value is None:
                reasons.append("posting_date_ambiguous")
        else:
            posting = Decision(_iso(self._bd(it)), 0.9)
        ttype = Decision(g.facts.get("type"), SELF_DECLARED_CONFIDENCE if g.facts.get("type") else None)
        decisions = {
            "message_group": Decision(None, GROUP_CONFIDENCE[g.status]),
            "transaction_type": ttype,
            "amount": Decision(g.facts.get("amount"), SELF_DECLARED_CONFIDENCE),
            "document_date": Decision(None, None),
            "posting_date": posting,
        }
        if g.facts.get("correction"):
            reasons.append("correction")
        return self._finish(key, g, [it.ref], "self_declared", decisions, self._sent_date(it), reasons, g.segment)

    def _finish(self, key, g, evidence, kind, decisions, sent_date, reasons, description) -> Record:
        weak = any(
            decisions[k].value is None and k != "message_group" or (decisions[k].confidence or 0) < HIGH
            for k in ("message_group", "transaction_type", "amount", "posting_date")
        )
        review = weak or "correction" in reasons or "caption_ambiguous" in reasons
        return Record(key, g.key, evidence, kind, decisions, sent_date, review, sorted(set(reasons)), description)

    def run(self) -> list[Record]:
        records = []
        by_group = {}
        for g in self.result.groups:
            key = f"R{len(records) + 1}"
            rec = self._document(g, key) if g.kind == "document" else self._self_declared(g, key)
            records.append(rec)
            by_group[g.key] = rec
        for g in self.result.groups:
            old = g.facts.get("supersedes")
            if old and old in by_group:
                by_group[g.key].supersedes = by_group[old].key
                by_group[old].status = "SUPERSEDED"
        return records


def normalize(doc: dict, result: GroupingResult) -> list[Record]:
    return _Normalizer(doc, result).run()


def description_matches(description: str | None, needle: str) -> bool:
    return bool(description) and fold(needle) in fold(description)


