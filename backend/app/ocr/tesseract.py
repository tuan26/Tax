"""Tesseract tự host (mã nguồn mở). Chạy trên server tại Việt Nam thì dữ liệu không ra nước ngoài."""

import shutil
import subprocess

from .text_fields import extract_fields


class TesseractOcr:
    name = "tesseract-vie"
    domestic = True

    def __init__(self, langs: str = "vie", psm: int = 6):
        if shutil.which("tesseract") is None:
            raise RuntimeError("Chưa cài tesseract")
        self.langs, self.psm = langs, psm

    def text(self, data: bytes) -> str:
        r = subprocess.run(["tesseract", "stdin", "stdout", "-l", self.langs, "--psm", str(self.psm)],
                           input=data, capture_output=True, timeout=60)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.decode(errors="replace")[:300])
        return r.stdout.decode("utf-8", errors="replace")

    def extract(self, data: bytes, mime_type: str) -> dict | None:
        if mime_type == "application/pdf":
            return None  # PDF cần tách trang thành ảnh trước; chưa làm trong pilot
        text = self.text(data)
        return extract_fields(text) if text.strip() else None
