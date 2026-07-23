from __future__ import annotations

from pathlib import Path

from .manifest import load_json, sha256_file


def _snapshot_dir(path: Path) -> Path:
    if (path / "manifest.json").exists():
        return path
    state = path / "job.json"
    if state.exists():
        current = load_json(state).get("current_snapshot")
        if current and (path / current / "manifest.json").exists():
            return path / current
    candidates = sorted((item for item in path.iterdir() if item.is_dir() and (item / "manifest.json").exists()), reverse=True)
    if candidates:
        return candidates[0]
    raise FileNotFoundError(f"manifest.json not found under {path}")


def verify_path(path: Path) -> dict:
    snapshot = _snapshot_dir(path.resolve())
    manifest_path = snapshot / "manifest.json"
    manifest = load_json(manifest_path)
    failures: list[dict] = []
    checked = 0
    for asset in manifest.get("assets", []):
        status = asset.get("status")
        if status == "failed":
            failures.append({"id": asset.get("id"), "reason": "asset status is failed"})
            continue
        if status != "complete":
            continue
        local_path = asset.get("local_path")
        if not local_path:
            failures.append({"id": asset.get("id"), "reason": "complete asset has no local_path"})
            continue
        candidate = (snapshot / local_path).resolve()
        try:
            candidate.relative_to(snapshot.resolve())
        except ValueError:
            failures.append({"id": asset.get("id"), "reason": "local_path escapes snapshot"})
            continue
        if not candidate.is_file():
            failures.append({"id": asset.get("id"), "reason": "file is missing", "path": local_path})
            continue
        checked += 1
        actual_size = candidate.stat().st_size
        if actual_size != asset.get("bytes"):
            failures.append({"id": asset.get("id"), "reason": "size mismatch", "path": local_path})
            continue
        actual_hash = sha256_file(candidate)
        if actual_hash != asset.get("sha256"):
            failures.append({"id": asset.get("id"), "reason": "sha256 mismatch", "path": local_path})
    return {
        "ok": not failures,
        "snapshot": str(snapshot),
        "manifest": str(manifest_path),
        "checked_files": checked,
        "failures": failures,
    }
