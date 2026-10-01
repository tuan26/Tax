"""Chuẩn hóa văn bản tiếng Việt để so khớp."""

import re
import unicodedata

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Từ quá chung, không dùng làm bằng chứng nội dung khớp.
STOPWORDS = {
    "tien", "hd", "hoa", "don", "nha", "nhe", "cua", "cac", "loai", "va", "la", "day", "nay",
    "hom", "qua", "toi", "thang", "tuan", "truoc", "sau", "mua", "ban", "chi", "cho", "em",
    "anh", "cai", "tren", "duoi", "hang", "so", "voi", "da", "roi", "di", "ve", "o", "tai",
    "cua", "nhe", "a", "ah", "oi", "ok", "kg", "cong", "ty", "tnhh", "cua", "dai", "ly",
}


def fold(text: str) -> str:
    """Chữ thường, bỏ dấu, đ → d, gộp khoảng trắng."""
    text = text.lower().replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


def content_tokens(text: str | None) -> set[str]:
    if not text:
        return set()
    return {t for t in _TOKEN_RE.findall(fold(text)) if len(t) >= 2 and t not in STOPWORDS}


def contains_any(folded: str, phrases) -> bool:
    return any(re.search(rf"(?<![a-z0-9]){re.escape(p)}(?![a-z0-9])", folded) for p in phrases)
