"""Immutable, content-addressed local assets. Paths are never supplied by a model."""
import hashlib
import os
import re
import tempfile
from pathlib import Path


class AssetStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, data: bytes, suffix: str = "bin") -> dict:
        if not re.fullmatch(r"[a-z0-9]{1,12}", suffix):
            raise ValueError("Unsupported asset suffix.")
        digest = hashlib.sha256(data).hexdigest()
        key = f"{digest[:2]}/{digest}.{suffix}"
        path = self.resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError("Existing asset checksum mismatch.")
        else:
            fd, name = tempfile.mkstemp(dir=path.parent)
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(name, path)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
        return {
            "asset_id": digest,
            "key": key,
            "sha256": digest,
            "size_bytes": len(data),
        }

    def resolve(self, key: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{2}/[a-f0-9]{64}\.[a-z0-9]{1,12}", key):
            raise ValueError("Invalid content-addressed asset key.")
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Asset path escapes the asset store.")
        return path

    def read(self, asset: dict) -> bytes:
        data = self.resolve(asset["key"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != asset["sha256"]:
            raise ValueError("Asset checksum verification failed.")
        return data
