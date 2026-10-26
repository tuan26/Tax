"""Chuyển bản chép chat Zalo thành messages.json (spec v1.1), che thông tin cá nhân, xem trước cách
engine gom tin, và xuất file đánh dấu để đo STOR trước pilot.

    python tools/pilot/zalo_transcript.py chat.txt --images anh/ --out ra/ [--ocr tesseract] [--collector "Tên"]
    python tools/pilot/zalo_transcript.py --score ra/danh-dau.csv      # sau khi đánh dấu đúng/sai

Định dạng chat.txt (xem docs/pilot/chep-chat-zalo.md):

    # hộ: Quán Minh Anh
    # giờ chốt: 04:00
    # người gửi: Chị Lan = owner; Tuấn = staff; Hà = accountant
    == 02/10/2026 ==
    10:00 Chị Lan: [ảnh hd_001.jpg]
    10:00 Chị Lan: [ảnh hd_002.jpg, hd_003.jpg]
    10:01 Chị Lan: 2tr5
    10:02 Chị Lan: tiền thịt
              dòng không có giờ là phần tiếp theo của tin trước
    10:05 Hà: [sticker]

Nội dung đặc biệt: [ảnh a.jpg, b.jpg] · [file x.pdf] · [sticker] · [thu hồi] · [ghi âm] · [link]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

ROLES = {"owner", "family", "staff", "accountant", "unknown"}
DATE_RE = re.compile(r"^==\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*==\s*$")
LINE_RE = re.compile(r"^(\d{1,2}):(\d{2})\s+([^:]{1,60}):\s?(.*)$")
SPECIAL_RE = re.compile(r"^\[(ảnh|anh|file|sticker|thu hồi|thu hoi|ghi âm|ghi am|link)\s*(.*?)\]$", re.I)
HEADER_RE = re.compile(r"^#\s*([^:]+):\s*(.*)$")

# Che thông tin cá nhân trong nội dung chữ. Số tiền (kể cả 8 chữ số như 12500000) không bị che:
# số tài khoản chỉ bị che khi có từ khóa đứng trước.
REDACTIONS = [
    ("SDT", re.compile(r"(?<!\d)(?:\+?84|0)[35789]\d{8}(?!\d)")),
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")),
    ("CCCD", re.compile(r"(?i)(?:cccd|cmnd|căn cước)\D{0,5}(\d{9,12})")),
    ("STK", re.compile(r"(?i)(?:stk|số tk|so tk|số tài khoản|so tai khoan|tài khoản|tai khoan|tk)\W{0,3}(\d[\d\s.-]{6,20}\d)")),
]


class TranscriptError(Exception):
    pass


@dataclass
class Message:
    message_id: str
    sender: str
    sent_at: str
    kind: str
    text: str | None
    files: list[str] = field(default_factory=list)
    line_no: int = 0


@dataclass
class Transcript:
    customer: str = "Hộ chưa đặt tên"
    cutoff: str = "04:00"
    roles: dict = field(default_factory=dict)
    messages: list[Message] = field(default_factory=list)


def parse(text: str) -> Transcript:
    t = Transcript()
    day = None
    for no, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        if not line.strip():
            continue
        if m := HEADER_RE.match(line.strip()):
            key, val = m.group(1).strip().lower(), m.group(2).strip()
            if key in ("hộ", "ho"):
                t.customer = val
            elif key in ("giờ chốt", "gio chot"):
                if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", val):
                    raise TranscriptError(f"dòng {no}: giờ chốt phải dạng HH:MM")
                t.cutoff = val
            elif key in ("người gửi", "nguoi gui"):
                for part in filter(None, (p.strip() for p in val.split(";"))):
                    name, _, role = part.partition("=")
                    role = role.strip().lower()
                    if role not in ROLES:
                        raise TranscriptError(f"dòng {no}: vai trò '{role}' phải là một trong {sorted(ROLES)}")
                    t.roles[name.strip()] = role
            continue
        if m := DATE_RE.match(line.strip()):
            d, mo, y = (int(x) for x in m.groups())
            day = f"{y:04d}-{mo:02d}-{d:02d}"
            continue
        if m := LINE_RE.match(line.strip()):
            if day is None:
                raise TranscriptError(f"dòng {no}: thiếu dòng ngày '== dd/mm/yyyy ==' phía trên")
            h, mi, sender, body = int(m.group(1)), int(m.group(2)), m.group(3).strip(), m.group(4).strip()
            if h > 23 or mi > 59:
                raise TranscriptError(f"dòng {no}: giờ không hợp lệ")
            sent_at = f"{day}T{h:02d}:{mi:02d}:00+07:00"
            msg = Message(f"m{len(t.messages) + 1}", sender, sent_at, "text", body or None, line_no=no)
            if sp := SPECIAL_RE.match(body):
                kind, rest = sp.group(1).lower(), sp.group(2)
                if kind in ("ảnh", "anh", "file"):
                    msg.kind = "image" if kind in ("ảnh", "anh") else "file"
                    msg.files = [f.strip() for f in rest.split(",") if f.strip()]
                    msg.text = None
                    if not msg.files:
                        raise TranscriptError(f"dòng {no}: [{kind}] cần tên file")
                else:
                    msg.kind = {"sticker": "sticker", "thu hồi": "deleted", "thu hoi": "deleted", "ghi âm": "voice",
                                "ghi am": "voice", "link": "link"}[kind]
                    msg.text = None
            elif not body:
                raise TranscriptError(f"dòng {no}: tin nhắn trống")
            t.messages.append(msg)
            continue
        # Dòng không có giờ: phần tiếp theo của tin chữ ngay trước.
        if t.messages and t.messages[-1].kind == "text":
            t.messages[-1].text += "\n" + line.strip()
            continue
        raise TranscriptError(f"dòng {no}: không hiểu '{line.strip()[:40]}'")
    if not t.messages:
        raise TranscriptError("không có tin nhắn nào")
    return t


def redact(text: str, counters: dict) -> str:
    for label, pattern in REDACTIONS:
        def sub(m, label=label):
            counters[label] = counters.get(label, 0) + 1
            token = f"[{label}_{counters[label]}]"
            if m.groups():
                return m.group(0).replace(m.group(1), token)
            return token
        text = pattern.sub(sub, text)
    return text


MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
        ".heic": "image/heic", ".pdf": "application/pdf"}


def build(t: Transcript, images_dir: Path | None, out_dir: Path, collector: str) -> tuple[dict, dict]:
    sender_ids, counters = {}, {}
    senders = []
    for m in t.messages:
        if m.sender not in sender_ids:
            sid = f"S{len(sender_ids) + 1}"
            sender_ids[m.sender] = sid
            senders.append({"sender_id": sid, "display_name": None, "role": t.roles.get(m.sender, "unknown"),
                            "linked_customer_id": "CUS-PILOT"})
    (out_dir / "images").mkdir(parents=True, exist_ok=True)
    messages = []
    for m in t.messages:
        d = {
            "message_id": m.message_id, "customer_id": "CUS-PILOT", "conversation_id": "CONV-TRANSCRIPT",
            "sender_id": sender_ids[m.sender], "sent_at": m.sent_at, "kind": m.kind,
            # Giờ gửi chép từ giao diện Zalo là bằng chứng thật, nên giữ sent_at; nguồn vẫn là chép tay.
            "source_type": "ZALO_MANUAL", "batch_id": None, "business_date": None, "sequence": None,
            "text": redact(m.text, counters) if m.text else None,
            "provenance": {"source": "zalo_pc_manual", "source_message_id": None,
                           "received_at": m.sent_at, "collected_by": collector, "raw_payload": None,
                           "raw_payload_sha256": None},
        }
        if m.files:
            atts = []
            for i, name in enumerate(m.files):
                ext = Path(name).suffix.lower()
                if ext not in MIME:
                    raise TranscriptError(f"dòng {m.line_no}: chỉ nhận {sorted(MIME)}: {name}")
                data = b""
                if images_dir is not None:
                    src = images_dir / name
                    if not src.is_file():
                        raise TranscriptError(f"dòng {m.line_no}: không thấy file {src}")
                    data = src.read_bytes()
                    shutil.copyfile(src, out_dir / "images" / name)
                atts.append({"attachment_id": f"{m.message_id}a{i + 1}",
                             "kind": "pdf" if ext == ".pdf" else "image", "file_name": name,
                             "mime_type": MIME[ext], "size_bytes": len(data) if data else None,
                             "sha256": hashlib.sha256(data or name.encode()).hexdigest(),
                             "storage_uri": f"images/{name}", "width": None, "height": None})
            d["attachments"] = atts
        messages.append(d)
    doc = {
        "schema_version": "1.1", "dataset_id": f"transcript-{t.customer}",
        "customer": {"customer_id": "CUS-PILOT", "name": t.customer, "timezone": "Asia/Ho_Chi_Minh",
                     "business_day_cutoff": t.cutoff},
        "senders": senders, "messages": messages,
    }
    report = {"messages": len(messages), "images": sum(len(m.files) for m in t.messages),
              "senders": {sid: t.roles.get(name, "unknown") for name, sid in sender_ids.items()},
              "redacted": counters}
    return doc, report


def add_ocr(doc: dict, out_dir: Path, provider_name: str):
    """Đọc ảnh bằng OCR tự host để xem trước sát với lúc chạy thật. Kết quả nằm riêng ở extractions."""
    from app.extraction import provider_for, run_ocr

    provider = provider_for(provider_name)
    extractions = []
    for m in doc["messages"]:
        for a in m.get("attachments", []):
            path = out_dir / a["storage_uri"]
            if not path.is_file():
                continue
            outcome = run_ocr(provider, path.read_bytes(), a["mime_type"], 60)
            row = outcome.to_row(provider.name)
            row.pop("raw_text", None)
            extractions.append({"extraction_id": f"X-{a['attachment_id']}", "attachment_id": a["attachment_id"],
                                "engine": provider.name, **{k: v for k, v in row.items() if v is not None}})
    doc["extractions"] = extractions


def score(csv_path: Path) -> dict:
    """Tính chỉ số từ file đánh dấu. Cột dung_khong: Y (đúng) hoặc N (sai); để trống thì chưa chấm."""
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    marked = [r for r in rows if r["dung_khong"].strip().upper() in ("Y", "N")]
    auto = [r for r in marked if r["engine"] == "CONFIDENT"]
    review = [r for r in marked if r["engine"] != "CONFIDENT" and ("AMBIGUOUS" in r["engine"] or "cần xem" in r["engine"])]
    tx = [r for r in marked if r["loai"] == "giao dịch"]
    # Giao dịch tổ chức thẳng: đúng, tự động, và không có liên kết mơ hồ nào trỏ tới nó.
    pending = {g.strip() for r in rows if r["engine"] == "AMBIGUOUS" for g in r["gan_vao"].replace("+", ",").split(",")}
    straight = [r for r in tx if r["dung_khong"].strip().upper() == "Y" and r["engine"] == "CONFIDENT"
                and r["ma"] not in pending]
    wrong_auto = [r for r in auto if r["dung_khong"].strip().upper() == "N"]
    return {
        "da_cham": len(marked), "chua_cham": len(rows) - len(marked),
        "tu_dong": len(auto), "tu_dong_sai": len(wrong_auto),
        "wrong_auto_rate": round(len(wrong_auto) / len(auto), 4) if auto else None,
        "vao_hang_cho": len(review),
        "giao_dich": len(tx), "to_chuc_thang": len(straight),
        "STOR_uoc_tinh": round(len(straight) / len(tx), 4) if tx else None,
        "tu_dong_sai_chi_tiet": [f'{r["ma"]}: {r["noi_dung"][:60]} → {r["sua_thanh"]}' for r in wrong_auto],
    }


def validate(doc: dict):
    from jsonschema import Draft202012Validator, FormatChecker

    schema = json.loads((ROOT / "spec" / "messages.schema.json").read_text())
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(doc))
    if errors:
        raise TranscriptError("không đúng schema: " + "; ".join(e.message for e in errors[:5]))


def preview_rows(doc: dict) -> list[dict]:
    """Một dòng cho mỗi quyết định của engine, để người chép đánh dấu đúng/sai."""
    from app.domain.grouping import group_messages

    result = group_messages(doc)
    text_of = {}
    for m in doc["messages"]:
        for a in m.get("attachments", []):
            text_of[f'{m["message_id"]}#{a["attachment_id"]}'] = f'[ảnh {a["file_name"]}]'
        text_of[m["message_id"]] = m.get("text") or f'[{m["kind"]}]'
    time_of = {m["message_id"]: m["sent_at"][5:16].replace("T", " ") for m in doc["messages"]}

    def show(ref):
        return f'{time_of[ref.split("#")[0]]} {text_of.get(ref, ref)}'

    rows = []
    for g in result.groups:
        rows.append({"loai": "giao dịch", "ma": g.key, "noi_dung": " + ".join(show(a) for a in g.anchor_items)
                     + (f' (đoạn: {g.segment})' if g.segment else ""), "engine": g.status, "gan_vao": "",
                     "dung_khong": "", "sua_thanh": "", "ghi_chu": ""})
    for l in result.links:
        rows.append({"loai": f"liên kết: {l.role}", "ma": l.item, "noi_dung": show(l.item), "engine": l.status,
                     "gan_vao": ", ".join(l.targets or l.candidates or []), "dung_khong": "", "sua_thanh": "",
                     "ghi_chu": ""})
    for u in result.unmatched:
        rows.append({"loai": "không thuộc giao dịch", "ma": u.item, "noi_dung": show(u.item),
                     "engine": f"UNMATCHED ({u.reason}{', cần xem' if u.needs_review else ''})", "gan_vao": "",
                     "dung_khong": "", "sua_thanh": "", "ghi_chu": ""})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("transcript", type=Path, nargs="?")
    ap.add_argument("--images", type=Path, help="thư mục chứa ảnh nhắc tới trong [ảnh ...]")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--ocr", choices=["tesseract"], help="đọc ảnh bằng OCR tự host trước khi xem trước")
    ap.add_argument("--collector", default="pilot")
    ap.add_argument("--score", type=Path, help="tính chỉ số từ file danh-dau.csv đã đánh dấu")
    args = ap.parse_args(argv)
    if args.score:
        print(json.dumps(score(args.score), ensure_ascii=False, indent=2))
        return 0
    if not args.transcript or not args.out:
        ap.error("cần file chat và --out")
    try:
        t = parse(args.transcript.read_text(encoding="utf-8-sig"))
        args.out.mkdir(parents=True, exist_ok=True)
        doc, report = build(t, args.images, args.out, args.collector)
        if args.ocr:
            add_ocr(doc, args.out, args.ocr)
        validate(doc)
    except TranscriptError as e:
        print(f"LỖI: {e}", file=sys.stderr)
        return 2
    (args.out / "messages.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = preview_rows(doc)
    with open(args.out / "danh-dau.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"Đã ghi {args.out / 'messages.json'} ({report['messages']} tin, {report['images']} ảnh)")
    print(f"Người gửi: {report['senders']}")
    print(f"Đã che: {report['redacted'] or 'không có'}. Tên riêng trong nội dung KHÔNG tự che được, hãy đọc lại.")
    print(f"File đánh dấu: {args.out / 'danh-dau.csv'} ({len(rows)} quyết định của engine)")
    if args.images is None:
        print("Chưa có --images: sha256 tính theo tên file, không phát hiện được ảnh gửi lại.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
