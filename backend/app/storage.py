"""Kho file gốc theo nội dung (sha256). Ghi một lần, không bao giờ ghi đè hay xóa."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path


class ImmutableStorage:
    def __init__(self, root: Path):
        self.root = Path(root)

    def key_for(self, tenant_id, sha256: str) -> str:
        return f"{tenant_id}/{sha256[:2]}/{sha256}"

    def put(self, tenant_id, data: bytes) -> tuple[str, str]:
        sha = hashlib.sha256(data).hexdigest()
        key = self.key_for(tenant_id, sha)
        path = self.root / key
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                raise RuntimeError(f"File gốc {key} không khớp hash, kho có thể đã bị sửa")
            return sha, key
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".tmp{os.getpid()}")
        with open(tmp, "xb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o440)
        try:
            os.link(tmp, path)
        except FileExistsError:
            pass
        finally:
            tmp.unlink()
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise RuntimeError(f"File gốc {key} không khớp hash sau khi ghi")
        return sha, key

    def get(self, key: str) -> bytes:
        data = (self.root / key).read_bytes()
        if hashlib.sha256(data).hexdigest() != key.rsplit("/", 1)[-1]:
            raise RuntimeError(f"File gốc {key} không khớp hash")
        return data
