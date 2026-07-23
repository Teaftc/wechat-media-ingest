from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .download import download_file, existing_file_matches, image_extension, probe_video
from .errors import ErrorCode, IngestError
from .fetch import fetch_browser, fetch_http
from .manifest import atomic_write_json, file_asset, load_json, new_manifest, sha256_file, update_summary, utc_now
from .normalize import ArticleIdentity, identify_article
from .parse import choose_transcode, parse_article
from .security import IMAGE_HOSTS, VIDEO_HOSTS
from .verify import verify_path


def _fetch(url: str, fetcher: str):
    if fetcher == "http":
        return fetch_http(url)
    if fetcher == "browser":
        return fetch_browser(url)
    if fetcher != "auto":
        raise IngestError(ErrorCode.UNSUPPORTED, f"unknown fetcher: {fetcher}")
    try:
        return fetch_http(url)
    except IngestError as exc:
        if exc.code not in {ErrorCode.PARSE_ERROR, ErrorCode.NETWORK}:
            raise
        return fetch_browser(url)


def inspect_url(url: str, fetcher: str = "auto", quality: str = "highest") -> dict:
    result = _fetch(url, fetcher)
    identity = identify_article(result.final_url)
    article = parse_article(result.html)
    images = [
        {"id": f"image_{index:03d}", "type": "image", "source_url": source, "status": "planned"}
        for index, source in enumerate(article.image_urls, 1)
    ]
    videos = []
    for item in article.native_videos:
        row: dict[str, Any] = {"id": f"native_video_{item.mpvid}", "type": "native_video", "mpvid": item.mpvid}
        try:
            row["selected_transcode"] = choose_transcode(item.transcodes, quality).to_dict()
            row["status"] = "planned"
        except IngestError as exc:
            row.update(status="failed", error={"code": exc.code, "message": exc.message})
        videos.append(row)
    out_of_scope = [
        {
            "id": f"out_of_scope_{index:03d}",
            "type": item["type"],
            "source_url": item["source_url"],
            "status": "out_of_scope",
            "reason": item["reason"],
        }
        for index, item in enumerate(article.out_of_scope, 1)
    ]
    return {
        "job_id": identity.job_id,
        "canonical_url": identity.canonical_url,
        "final_url": result.final_url,
        "fetch_method": result.method,
        "article": {
            "title": article.title,
            "account": article.account,
            "publish_time": article.publish_time,
            "markdown_chars": len(article.markdown),
        },
        "assets": images + videos + out_of_scope,
        "summary": {
            "images": len(images),
            "native_videos": len(videos),
            "out_of_scope": len(out_of_scope),
        },
    }


def _snapshot_id(job_dir: Path) -> str:
    base = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = base
    counter = 1
    while (job_dir / candidate).exists():
        candidate = f"{base}-{counter:02d}"
        counter += 1
    return candidate


def _load_current(job_dir: Path) -> tuple[str | None, dict | None]:
    state_path = job_dir / "job.json"
    if not state_path.exists():
        return None, None
    state = load_json(state_path)
    snapshot_id = state.get("current_snapshot")
    manifest_path = job_dir / str(snapshot_id) / "manifest.json"
    if not snapshot_id or not manifest_path.exists():
        return None, None
    return str(snapshot_id), load_json(manifest_path)


def _write_state(job_dir: Path, identity: ArticleIdentity, snapshot_id: str) -> None:
    atomic_write_json(
        job_dir / "job.json",
        {
            "schema_version": "1.0",
            "job_id": identity.job_id,
            "canonical_url": identity.canonical_url,
            "current_snapshot": snapshot_id,
            "updated_at": utc_now(),
        },
    )


def _asset_map(manifest: dict) -> dict[str, dict]:
    return {asset["id"]: asset for asset in manifest.get("assets", []) if asset.get("id")}


def _set_asset(manifest: dict, asset: dict) -> None:
    assets = manifest.setdefault("assets", [])
    for index, existing in enumerate(assets):
        if existing.get("id") == asset.get("id"):
            assets[index] = asset
            return
    assets.append(asset)


def _save_manifest(path: Path, manifest: dict) -> None:
    update_summary(manifest)
    atomic_write_json(path, manifest)


def _log(snapshot: Path, event: str, **payload) -> None:
    path = snapshot / "logs" / "ingest.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"time": utc_now(), "event": event, **payload}
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _complete_existing(asset: dict | None, snapshot: Path, desired_path: Path) -> dict | None:
    if not asset or asset.get("status") != "complete":
        if desired_path.exists():
            raise IngestError(ErrorCode.INTEGRITY, f"untracked existing file would be overwritten: {desired_path}")
        return None
    recorded_path = snapshot / asset.get("local_path", "")
    if recorded_path.resolve() != desired_path.resolve():
        raise IngestError(ErrorCode.INTEGRITY, f"asset path changed for {asset.get('id')}")
    if existing_file_matches(recorded_path, int(asset.get("bytes", -1)), str(asset.get("sha256", ""))):
        return asset
    raise IngestError(ErrorCode.INTEGRITY, f"existing file failed its recorded hash: {recorded_path}")


def _failure_manifest(
    output_root: Path,
    identity: ArticleIdentity,
    input_url: str,
    error: IngestError,
    force_new_snapshot: bool,
) -> dict:
    job_dir = output_root / identity.job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    current_id, current = _load_current(job_dir)
    snapshot_id = _snapshot_id(job_dir) if force_new_snapshot or not current_id else current_id
    snapshot = job_dir / snapshot_id
    snapshot.mkdir(parents=True, exist_ok=True)
    manifest = (
        current
        if current and not force_new_snapshot
        else new_manifest(
            input_url=input_url,
            final_url="",
            canonical_url=identity.canonical_url,
            job_id=identity.job_id,
            snapshot_id=snapshot_id,
            identity_method=identity.method,
            identity_fields=identity.fields,
            fetch_method="",
        )
    )
    manifest["job"]["status"] = "failed"
    manifest["job"]["error"] = {"code": error.code, "message": error.message}
    _save_manifest(snapshot / "manifest.json", manifest)
    _write_state(job_dir, identity, snapshot_id)
    _log(snapshot, "job_failed", code=error.code, message=error.message)
    return manifest


def ingest_url(
    url: str,
    output_root: Path,
    *,
    fetcher: str = "auto",
    quality: str = "highest",
    force_new_snapshot: bool = False,
) -> dict:
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    preliminary = identify_article(url)
    preliminary_job = output_root / preliminary.job_id
    current_id, current = _load_current(preliminary_job) if preliminary_job.exists() else (None, None)
    if current and not force_new_snapshot and current.get("job", {}).get("status") == "complete":
        report = verify_path(preliminary_job)
        if report["ok"]:
            current["rerun"] = {"action": "skipped", "reason": "existing complete snapshot verified"}
            return current
        raise IngestError(ErrorCode.INTEGRITY, "existing complete snapshot failed verification")

    try:
        result = _fetch(url, fetcher)
    except IngestError as exc:
        return _failure_manifest(output_root, preliminary, url, exc, force_new_snapshot)

    identity = identify_article(result.final_url)
    job_dir = output_root / identity.job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    current_id, current = _load_current(job_dir)
    if current and not force_new_snapshot and current.get("job", {}).get("status") == "complete":
        report = verify_path(job_dir)
        if report["ok"]:
            current["rerun"] = {"action": "skipped", "reason": "existing complete snapshot verified"}
            return current
        raise IngestError(ErrorCode.INTEGRITY, "existing complete snapshot failed verification")
    snapshot_id = _snapshot_id(job_dir) if force_new_snapshot or not current_id else current_id
    snapshot = job_dir / snapshot_id
    snapshot.mkdir(parents=True, exist_ok=True)
    manifest_path = snapshot / "manifest.json"
    manifest = current if current_id == snapshot_id and current else new_manifest(
        input_url=url,
        final_url=result.final_url,
        canonical_url=identity.canonical_url,
        job_id=identity.job_id,
        snapshot_id=snapshot_id,
        identity_method=identity.method,
        identity_fields=identity.fields,
        fetch_method=result.method,
    )
    manifest["job"].update(final_url=result.final_url, fetch_method=result.method, status="running", error=None)
    _write_state(job_dir, identity, snapshot_id)
    _log(snapshot, "fetch_complete", method=result.method, final_url=result.final_url)

    existing_assets = _asset_map(manifest)
    original_path = snapshot / "original.html"
    encoded_html = result.html.encode("utf-8")
    if original_path.exists():
        if sha256_file(original_path) != hashlib.sha256(encoded_html).hexdigest():
            raise IngestError(ErrorCode.INTEGRITY, "article HTML changed inside the active snapshot; use --force-new-snapshot")
    else:
        original_path.write_bytes(encoded_html)
    _set_asset(manifest, file_asset("article_html", "article_html", result.final_url, "original.html", original_path))

    try:
        article = parse_article(result.html)
    except ValueError as exc:
        error = IngestError(ErrorCode.PARSE_ERROR, str(exc))
        manifest["job"].update(status="failed", error={"code": error.code, "message": error.message})
        _save_manifest(manifest_path, manifest)
        return manifest

    manifest["article"].update(
        title=article.title,
        account=article.account,
        publish_time=article.publish_time,
        collected_at=utc_now(),
    )
    _save_manifest(manifest_path, manifest)

    replacements: dict[str, str] = {}
    failures = 0
    for index, source_url in enumerate(article.image_urls, 1):
        asset_id = f"image_{index:03d}"
        extension = image_extension(source_url)
        name_hash = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:12]
        relative = Path("assets") / "images" / f"{index:03d}_{name_hash}{extension}"
        destination = snapshot / relative
        try:
            reused = _complete_existing(existing_assets.get(asset_id), snapshot, destination)
            if reused:
                _set_asset(manifest, reused)
                replacements[source_url] = relative.as_posix()
                continue
            info = download_file(source_url, destination, allowed_hosts=IMAGE_HOSTS, kind="image")
            asset = {
                "id": asset_id,
                "type": "image",
                "source_url": source_url,
                "final_url": info["final_url"],
                "local_path": relative.as_posix(),
                "status": "complete",
                "bytes": info["bytes"],
                "sha256": info["sha256"],
                "content_type": info["content_type"],
                "error": None,
            }
            replacements[source_url] = relative.as_posix()
            _set_asset(manifest, asset)
            _log(snapshot, "asset_complete", asset_id=asset_id, bytes=info["bytes"])
        except IngestError as exc:
            failures += 1
            _set_asset(
                manifest,
                {
                    "id": asset_id,
                    "type": "image",
                    "source_url": source_url,
                    "local_path": relative.as_posix(),
                    "status": "failed",
                    "bytes": 0,
                    "sha256": "",
                    "content_type": "",
                    "error": {"code": exc.code, "message": exc.message},
                },
            )
            _log(snapshot, "asset_failed", asset_id=asset_id, code=exc.code, message=exc.message)
        _save_manifest(manifest_path, manifest)

    for item in article.native_videos:
        asset_id = f"native_video_{item.mpvid}"
        try:
            selected = choose_transcode(item.transcodes, quality)
            relative = Path("assets") / "videos" / f"{item.mpvid}_{selected.width}x{selected.height}.mp4"
            destination = snapshot / relative
            reused = _complete_existing(existing_assets.get(asset_id), snapshot, destination)
            if reused:
                _set_asset(manifest, reused)
                continue
            info = download_file(
                selected.url,
                destination,
                allowed_hosts=VIDEO_HOSTS,
                kind="video",
                expected_size=selected.filesize or None,
            )
            technical = {
                "duration": selected.duration_s,
                "width": selected.width,
                "height": selected.height,
                "codec": "",
            }
            technical.update({key: value for key, value in probe_video(destination).items() if value is not None})
            _set_asset(
                manifest,
                {
                    "id": asset_id,
                    "type": "native_video",
                    "mpvid": item.mpvid,
                    "source_url": selected.url,
                    "final_url": info["final_url"],
                    "local_path": relative.as_posix(),
                    "status": "complete",
                    "bytes": info["bytes"],
                    "sha256": info["sha256"],
                    "content_type": info["content_type"],
                    "quality_policy": quality,
                    "transcode": selected.to_dict(),
                    "technical": technical,
                    "error": None,
                },
            )
            _log(snapshot, "asset_complete", asset_id=asset_id, bytes=info["bytes"])
        except IngestError as exc:
            failures += 1
            _set_asset(
                manifest,
                {
                    "id": asset_id,
                    "type": "native_video",
                    "mpvid": item.mpvid,
                    "source_url": "",
                    "local_path": "",
                    "status": "failed",
                    "bytes": 0,
                    "sha256": "",
                    "content_type": "",
                    "error": {"code": exc.code, "message": exc.message},
                },
            )
            _log(snapshot, "asset_failed", asset_id=asset_id, code=exc.code, message=exc.message)
        _save_manifest(manifest_path, manifest)

    for index, item in enumerate(article.out_of_scope, 1):
        _set_asset(
            manifest,
            {
                "id": f"out_of_scope_{index:03d}",
                "type": item["type"],
                "source_url": item["source_url"],
                "local_path": "",
                "status": "out_of_scope",
                "bytes": 0,
                "sha256": "",
                "content_type": "",
                "reason": item["reason"],
                "error": {"code": ErrorCode.UNSUPPORTED, "message": item["reason"]},
            },
        )

    markdown = article.markdown
    for source, local in replacements.items():
        markdown = markdown.replace(source, local).replace(source.replace("&", "&amp;"), local)
    header = [f"# {article.title or 'WeChat article'}", ""]
    if article.account:
        header.append(f"- Account: {article.account}")
    if article.publish_time:
        header.append(f"- Published: {article.publish_time}")
    header.extend([f"- Source: {identity.canonical_url}", "", markdown])
    markdown_path = snapshot / "article.md"
    markdown_text = "\n".join(header).rstrip() + "\n"
    if markdown_path.exists() and sha256_file(markdown_path) != hashlib.sha256(markdown_text.encode("utf-8")).hexdigest():
        raise IngestError(ErrorCode.INTEGRITY, "article Markdown changed inside the active snapshot; use --force-new-snapshot")
    if not markdown_path.exists():
        markdown_path.write_text(markdown_text, encoding="utf-8", newline="\n")
    _set_asset(manifest, file_asset("article_markdown", "article_markdown", result.final_url, "article.md", markdown_path))

    manifest["job"]["status"] = "partial" if failures else "complete"
    manifest["job"]["error"] = (
        {"code": ErrorCode.NETWORK, "message": f"{failures} asset(s) failed; inspect per-asset errors"}
        if failures
        else None
    )
    _save_manifest(manifest_path, manifest)
    _write_state(job_dir, identity, snapshot_id)
    _log(snapshot, "job_finished", status=manifest["job"]["status"], failures=failures)
    return manifest
