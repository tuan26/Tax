"""Cấu hình từ biến môi trường. Mặc định an toàn: AI nước ngoài tắt."""

import os
from dataclasses import dataclass
from pathlib import Path


def _bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class Settings:
    database_url: str
    storage_dir: Path
    session_hours: int
    foreign_ai_enabled: bool
    ocr_provider: str
    max_upload_bytes: int
    ocr_timeout_seconds: float = 20.0


def load_settings() -> Settings:
    return Settings(
        database_url=os.environ.get("DATABASE_URL", "postgresql://tax_app_login@localhost/tax"),
        storage_dir=Path(os.environ.get("STORAGE_DIR", "var/storage")),
        session_hours=int(os.environ.get("SESSION_HOURS", "12")),
        # Chỉ bật khi đã có ý kiến pháp lý về pipeline hybrid. Xem app/ai_outbound.py.
        foreign_ai_enabled=_bool("FOREIGN_AI_ENABLED", False),
        ocr_provider=os.environ.get("OCR_PROVIDER", "none"),
        max_upload_bytes=int(os.environ.get("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024))),
        ocr_timeout_seconds=float(os.environ.get("OCR_TIMEOUT_SECONDS", "20")),
    )
