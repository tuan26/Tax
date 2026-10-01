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
    raise ValueError(f"Nhà cung cấp OCR '{name}' chưa được duyệt cho pilot")
