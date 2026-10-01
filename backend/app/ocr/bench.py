"""Spike OCR: chấm một provider trên ảnh thật có đáp án.

python -m app.ocr.bench --images <thư mục> --truth truth.csv --provider tesseract \
    --cost-per-page 0 --out report.md

truth.csv (UTF-8): file, category, doc_type, total_amount, document_date, seller_tax_id, seller_name
- category: nhãn tự do để chia nhóm báo cáo, ví dụ: in_thang, chup_nghieng, mo, viet_tay, chuyen_khoan.
- Ô để trống nghĩa là chứng từ không có trường đó; trường đó không được chấm cho ảnh này.

Với mỗi trường, mỗi ảnh rơi vào một trong bốn ô:
- correct: đọc đúng và đủ tự tin (≥ 0,6) → kế toán không phải gõ.
- wrong_confident: đọc sai nhưng tự tin → NGUY HIỂM, kế toán có thể không để ý.
- suggestion: có giá trị nhưng độ tin cậy thấp → vào hàng chờ, chỉ là gợi ý.
- missed: không đọc được → vào hàng chờ.
"""

from __future__ import annotations

import argparse
import csv
import mimetypes
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from ..domain.text import content_tokens
from ..extraction import run_ocr

FIELDS = ("total_amount", "document_date", "seller_tax_id", "seller_name")
CONFIDENT = 0.60
SAFE_WRONG_RATE = 0.02


@dataclass
class FieldScore:
    correct: int = 0
    wrong_confident: int = 0
    suggestion: int = 0
    missed: int = 0

    @property
    def n(self):
        return self.correct + self.wrong_confident + self.suggestion + self.missed

    def rate(self, attr):
        return getattr(self, attr) / self.n if self.n else 0.0


@dataclass
class BenchReport:
    provider: str
    images: int = 0
    failed: int = 0
    latencies: list[float] = field(default_factory=list)
    fields: dict = field(default_factory=lambda: defaultdict(FieldScore))
    by_category: dict = field(default_factory=lambda: defaultdict(lambda: defaultdict(FieldScore)))
    rows: list[dict] = field(default_factory=list)
    cost_per_page: float = 0.0

    @property
    def cost(self):
        return self.images * self.cost_per_page


def _normalize_truth(name, raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    if name == "total_amount":
        return int(raw.replace(".", "").replace(",", "").replace(" ", ""))
    if name == "seller_tax_id":
        return "".join(ch for ch in raw if ch.isdigit() or ch == "-")
    return raw


def _matches(name, got, truth) -> bool:
    if got is None:
        return False
    if name == "seller_name":
        a, b = content_tokens(str(got)), content_tokens(truth)
        return bool(a and b) and len(a & b) / len(a | b) >= 0.5
    if name == "seller_tax_id":
        return "".join(ch for ch in str(got) if ch.isdigit()) == "".join(ch for ch in truth if ch.isdigit())
    return got == truth


def _field_value(fields: dict | None, name: str):
    key = "counterparty_name" if name == "seller_name" else name
    v = (fields or {}).get(key)
    return (v.get("value"), v.get("confidence") or 0.0) if isinstance(v, dict) else (None, 0.0)


def score_one(fields: dict | None, truth_row: dict) -> dict[str, str]:
    out = {}
    for name in FIELDS:
        truth = _normalize_truth(name, truth_row.get(name))
        if truth is None:
            continue
        got, conf = _field_value(fields, name)
        if got is None:
            out[name] = "missed"
        elif conf < CONFIDENT:
            out[name] = "suggestion"
        else:
            out[name] = "correct" if _matches(name, got, truth) else "wrong_confident"
    return out


def run_bench(provider, images_dir: Path, truth_csv: Path, cost_per_page=0.0, timeout=60.0) -> BenchReport:
    report = BenchReport(provider.name, cost_per_page=cost_per_page)
    with open(truth_csv, newline="", encoding="utf-8-sig") as f:
        truth_rows = list(csv.DictReader(f))
    for row in truth_rows:
        path = images_dir / row["file"]
        data = path.read_bytes()
        mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        start = time.perf_counter()
        outcome = run_ocr(provider, data, mime, timeout)
        report.latencies.append(time.perf_counter() - start)
        report.images += 1
        if outcome.status == "failed":
            report.failed += 1
        verdicts = score_one(outcome.fields, row)
        for name, verdict in verdicts.items():
            setattr(report.fields[name], verdict, getattr(report.fields[name], verdict) + 1)
            cat = report.by_category[row.get("category") or "khac"][name]
            setattr(cat, verdict, getattr(cat, verdict) + 1)
        report.rows.append({"file": row["file"], "category": row.get("category"), "status": outcome.status,
                            "latency_s": round(report.latencies[-1], 3), **verdicts,
                            "amount_read": _field_value(outcome.fields, "total_amount")[0],
                            "amount_truth": row.get("total_amount")})
    return report


def render_markdown(r: BenchReport) -> str:
    lat = sorted(r.latencies) or [0.0]
    p95 = lat[min(len(lat) - 1, int(round(0.95 * (len(lat) - 1))))]
    lines = [
        f"# Spike OCR: {r.provider}",
        "",
        f"- Ảnh: {r.images}, OCR lỗi hoặc quá thời gian: {r.failed}",
        f"- Thời gian xử lý: trung vị {statistics.median(lat):.2f}s, p95 {p95:.2f}s, tối đa {max(lat):.2f}s",
        f"- Chi phí ước tính: {r.cost:,.0f} đ cho {r.images} trang",
        "",
        "| Trường | Đúng, tự tin | Sai nhưng tự tin | Chỉ gợi ý | Không đọc được | Số ảnh |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in FIELDS:
        s = r.fields.get(name)
        if not s or not s.n:
            continue
        flag = " ⚠" if s.rate("wrong_confident") > SAFE_WRONG_RATE else ""
        lines.append(f"| {name} | {s.rate('correct'):.0%} | {s.rate('wrong_confident'):.0%}{flag} | "
                     f"{s.rate('suggestion'):.0%} | {s.rate('missed'):.0%} | {s.n} |")
    lines += ["", f"⚠ = tỷ lệ sai nhưng tự tin vượt {SAFE_WRONG_RATE:.0%}. Với trường này, provider cần hạ độ tin cậy "
              "hoặc không được dùng để tự điền.", "", "## Theo nhóm ảnh", "",
              "| Nhóm | Trường | Đúng, tự tin | Sai nhưng tự tin | Số ảnh |", "|---|---|---:|---:|---:|"]
    for cat in sorted(r.by_category):
        for name in FIELDS:
            s = r.by_category[cat].get(name)
            if s and s.n:
                lines.append(f"| {cat} | {name} | {s.rate('correct'):.0%} | {s.rate('wrong_confident'):.0%} | {s.n} |")
    return "\n".join(lines) + "\n"


def write_detail_csv(r: BenchReport, path: Path):
    keys = sorted({k for row in r.rows for k in row})
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(r.rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--images", type=Path, required=True)
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument("--provider", default="tesseract")
    ap.add_argument("--cost-per-page", type=float, default=0.0)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--out", type=Path, default=Path("ocr-report.md"))
    args = ap.parse_args()
    from ..extraction import provider_for

    report = run_bench(provider_for(args.provider), args.images, args.truth, args.cost_per_page, args.timeout)
    args.out.write_text(render_markdown(report), encoding="utf-8")
    write_detail_csv(report, args.out.with_suffix(".csv"))
    print(render_markdown(report))


if __name__ == "__main__":
    main()
