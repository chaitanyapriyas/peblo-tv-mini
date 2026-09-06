from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class LocalStorage:
    """Small storage abstraction; replace this implementation with object storage in production."""

    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or os.getenv("STORAGE_ROOT", "./storage")).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, key: str, content: bytes) -> dict[str, str]:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        checksum = hashlib.sha256(content).hexdigest()
        return {"key": key, "version": checksum[:16], "etag": checksum}

    def put_json_versioned(self, payload: dict[str, Any], version: str) -> dict[str, str]:
        content = json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2).encode("utf-8")
        key = f"catalogue/catalogue-{version}.json"
        return self.put_bytes(key, content)

    def promote(self, versioned_key: str) -> dict[str, str]:
        source = self.root / versioned_key
        if not source.exists():
            raise FileNotFoundError(versioned_key)
        live_key = "catalogue/catalogue.json"
        (self.root / live_key).write_bytes(source.read_bytes())
        return {"key": live_key, "version": source.stem.removeprefix("catalogue-")}

    def get_json(self, key: str) -> dict[str, Any] | None:
        path = self.root / key
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None