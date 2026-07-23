from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__

SCHEMA_VERSION = "1.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def file_asset(asset_id: str, asset_type: str, source_url: str, relative_path: str, path: Path) -> dict:
    return {
        "id": asset_id,
        "type": asset_type,
        "source_url": source_url,
        "local_path": relative_path.replace("\\", "/"),
        "status": "complete",
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "content_type": "text/html; charset=utf-8" if asset_type == "article_html" else "text/markdown; charset=utf-8",
        "error": None,
    }


def new_manifest(
    *,
    input_url: str,
    final_url: str,
    canonical_url: str,
    job_id: str,
    snapshot_id: str,
    identity_method: str,
    identity_fields: dict[str, str],
    fetch_method: str,
) -> dict:
    now = utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": {"name": "wechat-media-ingest", "version": __version__},
        "job": {
            "job_id": job_id,
            "snapshot_id": snapshot_id,
            "input_url": input_url,
            "final_url": final_url,
            "canonical_url": canonical_url,
            "identity_method": identity_method,
            "identity_fields": identity_fields,
            "fetch_method": fetch_method,
            "created_at": now,
            "updated_at": now,
            "status": "running",
            "error": None,
        },
        "article": {"title": "", "account": "", "publish_time": "", "collected_at": now},
        "assets": [],
        "summary": {"complete": 0, "skipped": 0, "out_of_scope": 0, "failed": 0},
    }


def update_summary(manifest: dict) -> None:
    counts = {"complete": 0, "skipped": 0, "out_of_scope": 0, "failed": 0}
    for asset in manifest.get("assets", []):
        status = asset.get("status")
        if status in counts:
            counts[status] += 1
    manifest["summary"] = counts
    manifest["job"]["updated_at"] = utc_now()
