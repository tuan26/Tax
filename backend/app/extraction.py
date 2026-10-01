"""Nhà cung cấp OCR/trích xuất. Mặc định không có OCR: ảnh vào hàng chờ để kế toán nhập.

Chỉ nhà cung cấp chạy trong nước được dùng cho dữ liệu thật. Nhà cung cấp nước ngoài
phải đi qua app/ai_outbound.py.
"""

from __future__ import annotations


class NoOcr:
    name = "none"
    domestic = True

    def extract(self, data: bytes, mime_type: str) -> dict | None:
        return None


class FixtureOcr:
    """Dùng trong test: trả kết quả đã chuẩn bị sẵn theo sha256."""

    name = "fixture"
    domestic = True

    def __init__(self, by_sha: dict[str, dict]):
        self.by_sha = by_sha

    def extract(self, data: bytes, mime_type: str) -> dict | None:
        import hashlib

        return self.by_sha.get(hashlib.sha256(data).hexdigest())


def provider_for(name: str):
    if name == "none":
        return NoOcr()
    if name == "tesseract":
        from .ocr.tesseract import TesseractOcr

        return TesseractOcr()
    raise ValueError(f"Nhà cung cấp OCR '{name}' chưa được duyệt cho pilot")


# --------------------------------------------------------------------------- chạy an toàn

import concurrent.futures as _futures
from dataclasses import dataclass

_EXECUTOR = _futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="ocr")


@dataclass
class OcrOutcome:
    status: str  # ok | empty | failed
    fields: dict | None
    error: str | None = None

    def to_row(self, engine: str) -> dict:
        if self.status == "ok":
            return {"status": "ok", **self.fields}
        return {"status": self.status, "error": self.error}


def run_ocr(provider, data: bytes, mime_type: str, timeout_seconds: float) -> OcrOutcome:
    """OCR lỗi, quá thời gian hay trả về rác đều thành 'failed'/'empty', không bao giờ ném lỗi ra ngoài."""
    future = _EXECUTOR.submit(provider.extract, data, mime_type)
    try:
        fields = future.result(timeout=timeout_seconds)
    except _futures.TimeoutError:
        future.cancel()
        return OcrOutcome("failed", None, f"timeout>{timeout_seconds}s")
    except Exception as e:  # noqa: BLE001 — mọi lỗi của provider đều phải giảm cấp an toàn
        return OcrOutcome("failed", None, f"{type(e).__name__}: {e}"[:500])
    if not fields:
        return OcrOutcome("empty", None)
    if not isinstance(fields, dict) or not isinstance(fields.get("doc_type"), dict):
        return OcrOutcome("failed", None, "invalid_provider_output")
    return OcrOutcome("ok", fields)
