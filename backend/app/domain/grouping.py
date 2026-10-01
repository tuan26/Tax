"""Gom tin nhắn thành giao dịch: MESSAGE → MESSAGE_GROUP.

Nguyên tắc: không chắc thì không đoán. Một quyết định chỉ CONFIDENT khi có bằng chứng
(số tiền khớp duy nhất, nội dung khớp duy nhất, hoặc chỉ có đúng một ứng viên gửi liền
trước bởi cùng người). Tin nhập tay không có giờ gửi thì "đứng gần nhau" không phải
bằng chứng.

Đầu vào là một tài liệu theo spec/messages.schema.json. Hàm thuần, không đụng DB.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from .dates import business_date, local_datetime, relative_kind
from .money import Amount, find_amounts
from .text import contains_any, content_tokens, fold

ENGINE_VERSION = "grouping-0.1"

BURST_GAP_SECONDS = 180
NEAR_DUPLICATE_LOOKBACK_DAYS = 7
CORRECTION_LOOKBACK_DAYS = 3

CONFIDENT = "CONFIDENT"
AMBIGUOUS = "AMBIGUOUS"
UNMATCHED = "UNMATCHED"
NONE_CANDIDATE = "NONE"

DOCUMENT_TYPES = {"invoice", "receipt", "handwritten_receipt", "bank_transfer"}
# Chỉ ảnh được xác định rõ là không phải chứng từ mới bị loại. Loại "unknown" vẫn là chứng từ chờ duyệt.
NON_DOCUMENT_TYPES = {"other"}
NOISE_KINDS = {"sticker", "system", "deleted", "link"}
UNSUPPORTED_KINDS = {"voice", "unsupported"}

CAPTION_CUES = ("tien", "hd", "hoa don", "phieu", "bill", "mua", "phi")
REFERENCE_PHRASES = ("cai tren", "anh tren", "o tren", "cai nay", "hd tren", "cai truoc", "anh truoc")
CORRECTION_PHRASES = ("sua lai", "chu khong phai", "nham", "ghi nham")
SMALL_TALK = ("nhe", "nha", "ok", "oke", "cam on", "vang", "mai", "lay hang", "alo", "da", "em oi", "chi oi")

# Động từ trên chữ thường còn dấu, để "chi" (khoản chi) không nhầm với "chị".
INCOME_RE = re.compile(r"doanh thu|\bdt\b|\bbán\b|\bban duoc\b")
EXPENSE_RE = re.compile(r"\bchi\b|\bnhập\b|\bnhap hang\b|\bmua\b|\btrả\b")
SEGMENT_SPLIT_RE = re.compile(r"[,;\n]+|\s+và\s+")
CORRECTION_SPLIT_RE = re.compile(r"chứ không phải|chu khong phai")


# --------------------------------------------------------------------------- kết quả


@dataclass
class Group:
    key: str
    status: str
    anchor_items: list[str]
    kind: str  # "document" | "self_declared"
    sender_id: str | None
    burst: tuple
    segment: str | None = None
    partition_candidates: list | None = None
    facts: dict = field(default_factory=dict)


@dataclass
class Link:
    item: str
    role: str
    status: str
    targets: list[str] | None = None
    candidates: list[str] | None = None
    note: str | None = None
    data: dict = field(default_factory=dict)


@dataclass
class Unmatched:
    item: str
    reason: str
    needs_review: bool


@dataclass
class GroupingResult:
    groups: list[Group]
    links: list[Link]
    unmatched: list[Unmatched]
    engine_version: str = ENGINE_VERSION

    def group(self, key: str) -> Group:
        return next(g for g in self.groups if g.key == key)


# --------------------------------------------------------------------------- item


@dataclass
class Item:
    ref: str
    message: dict
    attachment: dict | None
    extraction: dict | None
    local: datetime | None
    order: int

    @property
    def sender(self):
        return self.message.get("sender_id")

    @property
    def timeless(self) -> bool:
        return self.local is None

    @property
    def message_id(self) -> str:
        return self.message["message_id"]

    def ext(self, name, min_conf=0.0):
        e = (self.extraction or {}).get(name)
        if not e or e.get("value") is None or e.get("confidence", 0) < min_conf:
            return None
        return e["value"]


def _items(doc: dict) -> list[Item]:
    tz = doc["customer"]["timezone"]
    extractions = {e["attachment_id"]: e for e in doc.get("extractions", [])}
    indexed = list(enumerate(doc["messages"]))

    def sort_key(pair):
        i, m = pair
        local = local_datetime(m.get("sent_at"), tz)
        seq = m.get("sequence")
        return (local is None, local or datetime.min, seq if seq is not None else i, i)

    items = []
    for order, (_, m) in enumerate(sorted(indexed, key=sort_key)):
        local = local_datetime(m.get("sent_at"), tz)
        atts = m.get("attachments") or []
        if atts:
            for a in atts:
                items.append(Item(f'{m["message_id"]}#{a["attachment_id"]}', m, a,
                                  extractions.get(a["attachment_id"]), local, order))
        else:
            items.append(Item(m["message_id"], m, None, None, local, order))
    return items


def _bursts(items: list[Item]) -> dict[str, tuple]:
    """Chuỗi tin liên tiếp của cùng người gửi, cách nhau không quá BURST_GAP_SECONDS.

    Tin không có giờ gửi thuộc một "burst" theo đợt nhập, đánh dấu timeless.
    """
    out: dict[str, tuple] = {}
    last: dict = {}
    counter = 0
    for it in items:
        if it.timeless:
            out[it.ref] = ("batch", it.message.get("batch_id") or it.message.get("business_date"))
            continue
        prev = last.get(it.sender)
        if prev is not None and it.message_id == prev[1]:
            out[it.ref] = prev[0]
            continue
        if prev is None or (it.local - prev[2]).total_seconds() > BURST_GAP_SECONDS:
            counter += 1
            burst = ("time", it.sender, counter)
        else:
            burst = prev[0]
        last[it.sender] = (burst, it.message_id, it.local)
        out[it.ref] = burst
    return out


# --------------------------------------------------------------------------- engine


class _Engine:
    def __init__(self, doc: dict):
        self.doc = doc
        self.cutoff = doc["customer"]["business_day_cutoff"]
        self.items = _items(doc)
        self.burst = _bursts(self.items)
        self.groups: list[Group] = []
        self.links: list[Link] = []
        self.unmatched: list[Unmatched] = []
        self.item_group: dict[str, str] = {}
        self.sha_owner: dict[str, str] = {}
        self.item_by_ref = {it.ref: it for it in self.items}

    # ---- helpers

    def _new_group(self, anchors, kind, it: Item, **kw) -> Group:
        g = Group(f"G{len(self.groups) + 1}", kw.pop("status", CONFIDENT), list(anchors), kind,
                  it.sender, self.burst[it.ref], **kw)
        self.groups.append(g)
        for a in anchors:
            self.item_group[a] = g.key
        return g

    def _doc_items(self, g: Group) -> list[Item]:
        return [self.item_by_ref[a] for a in g.anchor_items if a in self.item_by_ref]

    def _group_total(self, g: Group, min_conf=0.9):
        totals = {it.ext("total_amount", min_conf) for it in self._doc_items(g)} - {None}
        return totals.pop() if len(totals) == 1 else None

    def _group_tokens(self, g: Group) -> set[str]:
        toks = set()
        for it in self._doc_items(g):
            toks |= content_tokens(it.ext("description"))
            toks |= content_tokens(it.ext("counterparty_name"))
        return toks

    def _candidates(self, it: Item) -> list[Group]:
        """Nhóm chứng từ cùng burst, đứng trước item (với tin có giờ gửi)."""
        b = self.burst[it.ref]
        out = []
        for g in self.groups:
            if g.kind != "document" or g.burst != b:
                continue
            if not it.timeless and min(self.item_by_ref[a].order for a in g.anchor_items) > it.order:
                continue
            out.append(g)
        return out

    def _business_date(self, it: Item) -> date | None:
        if it.local is None:
            bd = it.message.get("business_date")
            return date.fromisoformat(bd) if bd else None
        return business_date(it.local, self.cutoff)

    # ---- documents

    def _document(self, it: Item):
        sha = it.attachment["sha256"]
        if sha in self.sha_owner:
            owner = self.sha_owner[sha]
            if owner in self.item_group:
                self.links.append(Link(it.ref, "duplicate_of", CONFIDENT, targets=[self.item_group[owner]],
                                       note="cùng sha256"))
            else:
                self.unmatched.append(Unmatched(it.ref, "duplicate_of_unmatched", False))
            return
        self.sha_owner[sha] = it.ref

        doc_type = it.ext("doc_type")
        if doc_type in NON_DOCUMENT_TYPES:
            conf = (it.extraction or {}).get("doc_type", {}).get("confidence", 0)
            self.unmatched.append(Unmatched(it.ref, "non_document", conf < 0.8))
            return

        if self._merge_pages(it):
            return
        if self._near_duplicate(it):
            return
        self._new_group([it.ref], "document", it)

    def _same_party(self, a: Item, b: Item) -> bool:
        pa, pb = a.ext("counterparty_name", 0.6), b.ext("counterparty_name", 0.6)
        return bool(pa and pb and fold(pa) == fold(pb))

    def _family(self, it: Item) -> str:
        return "transfer" if it.ext("doc_type") == "bank_transfer" else "paper"

    def _merge_pages(self, it: Item) -> bool:
        b = self.burst[it.ref]
        prev_groups = [g for g in self.groups if g.kind == "document" and g.burst == b]
        if not prev_groups:
            return False
        inv = it.ext("invoice_number", 0.8)
        for g in reversed(prev_groups):
            for other in self._doc_items(g):
                if self._family(other) != self._family(it) or not self._same_party(other, it):
                    continue
                other_inv = other.ext("invoice_number", 0.8)
                if inv and other_inv:
                    if inv == other_inv:
                        g.anchor_items.append(it.ref)
                        self.item_group[it.ref] = g.key
                        g.facts["merged_pages"] = True
                        return True
                    continue
        # Ảnh liền trước cùng người bán, không có số hóa đơn: một hóa đơn nhiều trang hay hai lần mua?
        last = prev_groups[-1]
        last_items = self._doc_items(last)
        other = last_items[-1]
        if (self._family(other) == self._family(it) and self._same_party(other, it)
                and not inv and not other.ext("invoice_number", 0.8)):
            ta, tb = other.ext("total_amount", 0.6), it.ext("total_amount", 0.6)
            if ta is not None and tb is not None and ta != tb:
                return False
            last.anchor_items.append(it.ref)
            self.item_group[it.ref] = last.key
            last.status = AMBIGUOUS
            last.partition_candidates = [[list(last.anchor_items)], [[a] for a in last.anchor_items]]
            return True
        return False

    def _near_duplicate(self, it: Item) -> bool:
        total = it.ext("total_amount", 0.6)
        ddate = it.ext("document_date", 0.6)
        if total is None or ddate is None:
            return False
        inv = it.ext("invoice_number", 0.8)
        for g in self.groups:
            if g.kind != "document" or g.burst == self.burst[it.ref]:
                continue
            for other in self._doc_items(g):
                if (self._family(other) != self._family(it) or not self._same_party(other, it)
                        or other.ext("total_amount", 0.6) != total or other.ext("document_date", 0.6) != ddate):
                    continue
                other_inv = other.ext("invoice_number", 0.8)
                if inv and other_inv and inv == other_inv:
                    self.links.append(Link(it.ref, "duplicate_of", CONFIDENT, targets=[g.key],
                                           note="cùng người bán, số hóa đơn, số tiền, ngày"))
                    return True
                if inv and other_inv:
                    continue
                self.links.append(Link(it.ref, "duplicate_of", AMBIGUOUS, candidates=[g.key, NONE_CANDIDATE],
                                       note="có thể chụp lại cùng một phiếu"))
                return True
        return False

    # ---- text

    def _text(self, it: Item):
        raw = it.message.get("text") or ""
        folded = fold(raw)
        amounts = find_amounts(raw)

        if amounts and contains_any(folded, CORRECTION_PHRASES):
            return self._correction(it, raw, amounts)

        segments = self._self_declared_segments(raw)
        if segments:
            for seg_text, ttype, amount in segments:
                self._new_group([it.ref], "self_declared", it, segment=seg_text,
                                facts={"type": ttype, "amount": amount, "relative": relative_kind(fold(seg_text))})
            return

        if amounts:
            return self._annotation(it, "amount_annotation", folded,
                                    data={"amounts": [a.value for a in amounts]})

        rel = relative_kind(folded)
        if rel and contains_any(folded, REFERENCE_PHRASES):
            return self._annotation(it, "date_correction", folded, data={"relative": rel})
        if rel:
            return self._annotation(it, "date_annotation", folded, data={"relative": rel})

        cands = self._candidates(it)
        caption_tokens = content_tokens(raw)
        content_hit = any(caption_tokens & self._group_tokens(g) for g in cands)
        if contains_any(folded, CAPTION_CUES) or content_hit:
            return self._annotation(it, "caption", folded, data={"text": raw})

        self.unmatched.append(Unmatched(it.ref, "noise", not contains_any(folded, SMALL_TALK)))

    def _self_declared_segments(self, raw: str):
        out = []
        for seg in SEGMENT_SPLIT_RE.split(raw):
            seg = seg.strip()
            if not seg:
                continue
            amounts = find_amounts(seg)
            if len(amounts) != 1:
                continue
            lower = seg.lower()
            is_income = bool(INCOME_RE.search(lower) or INCOME_RE.search(fold(seg)))
            is_expense = bool(EXPENSE_RE.search(lower))
            if is_income == is_expense:
                continue
            out.append((seg, "INCOME" if is_income else "EXPENSE", amounts[0].value))
        return out

    def _correction(self, it: Item, raw: str, amounts: list[Amount]):
        parts = CORRECTION_SPLIT_RE.split(raw, maxsplit=1)
        new_amounts = find_amounts(parts[0])
        old_amounts = find_amounts(parts[1]) if len(parts) > 1 else []
        lower = raw.lower()
        ttype = "INCOME" if INCOME_RE.search(lower) or INCOME_RE.search(fold(raw)) else (
            "EXPENSE" if EXPENSE_RE.search(lower) else None)
        new_value = new_amounts[0].value if new_amounts else amounts[0].value
        g = self._new_group([it.ref], "self_declared", it, segment=parts[0].strip(),
                            facts={"type": ttype, "amount": new_value, "relative": relative_kind(fold(raw)),
                                   "correction": True})
        old_value = old_amounts[0].value if old_amounts else None
        cands = []
        for prev in self.groups:
            if prev is g or prev.kind != "self_declared" or prev.facts.get("type") != ttype:
                continue
            prev_item = self.item_by_ref[prev.anchor_items[0]]
            if prev_item.order >= it.order:
                continue
            if old_value is not None and prev.facts.get("amount") != old_value:
                continue
            bd_prev, bd_now = self._business_date(prev_item), self._business_date(it)
            if bd_prev and bd_now and (bd_now - bd_prev).days > CORRECTION_LOOKBACK_DAYS:
                continue
            cands.append(prev.key)
        if len(cands) == 1:
            self.links.append(Link(it.ref, "correction", CONFIDENT, targets=cands, note=f"{g.key} thay thế {cands[0]}"))
            g.facts["supersedes"] = cands[0]
        elif cands:
            self.links.append(Link(it.ref, "correction", AMBIGUOUS, candidates=cands))

    def _annotation(self, it: Item, role: str, folded: str, data: dict):
        cands = self._candidates(it)
        if not cands:
            needs = role != "caption" or contains_any(folded, CAPTION_CUES)
            self.unmatched.append(Unmatched(it.ref, "no_anchor_in_window", needs))
            return

        matched: list[Group] = []
        if role == "amount_annotation":
            # Số kế toán/khách gõ và số OCR đọc là hai nguồn độc lập: khớp đúng một ứng viên đã là bằng
            # chứng mạnh, nên chỉ cần OCR đạt mức gợi ý (0,6) thay vì mức chắc chắn.
            values = set(data["amounts"])
            matched = [g for g in cands if self._group_total(g, min_conf=0.6) in values]
        elif role == "caption":
            toks = content_tokens(data["text"])
            matched = [g for g in cands if toks & self._group_tokens(g)]

        if len(matched) == 1:
            self.links.append(Link(it.ref, role, CONFIDENT, targets=[matched[0].key], data=data,
                                   note="bằng chứng khớp duy nhất"))
            return
        if not it.timeless:
            if len(cands) == 1:
                self.links.append(Link(it.ref, role, CONFIDENT, targets=[cands[0].key], data=data,
                                       note="ứng viên duy nhất gửi liền trước"))
                return
            if role == "date_annotation":
                anchor_msgs = {self.item_by_ref[a].message_id for g in cands for a in g.anchor_items}
                if len(anchor_msgs) == 1:
                    self.links.append(Link(it.ref, role, CONFIDENT, targets=[g.key for g in cands], data=data,
                                           note="chú thích cho cả album"))
                    return

        keys = [g.key for g in cands]
        if role in ("date_annotation", "date_correction") and len(keys) > 1:
            keys = keys + ["+".join(keys)]
        if it.timeless and len(cands) == 1:
            keys = keys + [NONE_CANDIDATE]
        self.links.append(Link(it.ref, role, AMBIGUOUS, candidates=keys, data=data))

    # ---- run

    def run(self) -> GroupingResult:
        for it in self.items:
            kind = it.message["kind"]
            if kind in NOISE_KINDS:
                self.unmatched.append(Unmatched(it.ref, "noise", False))
            elif kind in UNSUPPORTED_KINDS:
                self.unmatched.append(Unmatched(it.ref, "unsupported_content", True))
            elif it.attachment is not None:
                self._document(it)
            elif kind == "text":
                self._text(it)
            else:
                self.unmatched.append(Unmatched(it.ref, "unsupported_content", True))
        return GroupingResult(self.groups, self.links, self.unmatched)


def group_messages(doc: dict) -> GroupingResult:
    return _Engine(doc).run()
