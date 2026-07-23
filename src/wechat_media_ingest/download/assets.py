from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx

from ..errors import ErrorCode, IngestError
from ..fetch.http import HEADERS
from ..manifest import sha256_file
from ..security import redirect_target, validate_public_url

CHUNK_SIZE = 1024 * 1024


def image_extension(url: str) -> str:
    parts = urlsplit(url)
    suffix = Path(parts.path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    fmt = parse_qs(parts.query).get("wx_fmt", [""])[0].lower()
    return {"jpeg": ".jpg", "jpg": ".jpg", "png": ".png", "gif": ".gif", "webp": ".webp"}.get(fmt, ".img")


def _valid_magic(kind: str, header: bytes) -> bool:
    if kind == "video":
        return b"ftyp" in header[:32]
    return bool(
        header.startswith(b"\xff\xd8\xff")
        or header.startswith(b"\x89PNG\r\n\x1a\n")
        or header.startswith((b"GIF87a", b"GIF89a"))
        or (header.startswith(b"RIFF") and header[8:12] == b"WEBP")
        or header.startswith(b"BM")
    )


def _validate_type(kind: str, content_type: str, header: bytes) -> None:
    base = content_type.split(";", 1)[0].strip().lower()
    if kind == "video":
        allowed = base in {"video/mp4", "application/octet-stream", "binary/octet-stream"}
    else:
        allowed = base.startswith("image/") or base in {"application/octet-stream", "binary/octet-stream"}
    if not allowed or not _valid_magic(kind, header):
        raise IngestError(ErrorCode.INTEGRITY, f"unexpected {kind} response: content-type={base or '<missing>'}")


@contextmanager
def _stream_with_redirects(client, url: str, allowed_hosts: set[str], headers: dict[str, str], max_redirects: int = 8):
    current = validate_public_url(url, allowed_hosts)
    for _ in range(max_redirects + 1):
        with client.stream("GET", current, headers=headers) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise IngestError(ErrorCode.NETWORK, "asset redirect omitted Location")
                current = redirect_target(current, location, allowed_hosts)
                continue
            yield response, current
            return
    raise IngestError(ErrorCode.NETWORK, f"too many asset redirects (>{max_redirects})")


def download_file(
    url: str,
    destination: Path,
    *,
    allowed_hosts: set[str],
    kind: str,
    expected_size: int | None = None,
    timeout: float = 120.0,
) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise IngestError(ErrorCode.INTEGRITY, f"refusing to overwrite existing file: {destination}")
    part = destination.with_name(destination.name + ".part")
    start = part.stat().st_size if part.exists() else 0
    request_headers = dict(HEADERS)
    if start:
        request_headers["Range"] = f"bytes={start}-"

    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            with _stream_with_redirects(client, url, allowed_hosts, request_headers) as (response, final_url):
                if response.status_code in {401, 403, 404, 410}:
                    code = ErrorCode.MEDIA_EXPIRED if kind == "video" else ErrorCode.NETWORK
                    raise IngestError(code, f"asset HTTP status {response.status_code}")
                response.raise_for_status()
                append = bool(start and response.status_code == 206)
                if start and not append:
                    start = 0
                digest = hashlib.sha256()
                header = b""
                if append:
                    with part.open("rb") as existing:
                        header = existing.read(64)
                        digest.update(header)
                        while chunk := existing.read(CHUNK_SIZE):
                            digest.update(chunk)
                iterator = response.iter_bytes(CHUNK_SIZE)
                try:
                    first = next(iterator)
                except StopIteration as exc:
                    raise IngestError(ErrorCode.NETWORK, "asset response body was empty") from exc
                if not header:
                    header = first[:64]
                _validate_type(kind, response.headers.get("content-type", ""), header)
                mode = "ab" if append else "wb"
                with part.open(mode) as handle:
                    handle.write(first)
                    digest.update(first)
                    for chunk in iterator:
                        handle.write(chunk)
                        digest.update(chunk)
                    handle.flush()
                    os.fsync(handle.fileno())
    except IngestError:
        raise
    except httpx.HTTPStatusError as exc:
        raise IngestError(ErrorCode.NETWORK, f"asset HTTP status {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise IngestError(ErrorCode.NETWORK, str(exc)) from exc

    total = part.stat().st_size
    if expected_size and total != expected_size:
        raise IngestError(ErrorCode.INTEGRITY, f"asset size {total} does not match expected {expected_size}")
    os.replace(part, destination)
    return {
        "bytes": total,
        "sha256": digest.hexdigest(),
        "content_type": response.headers.get("content-type", "").split(";", 1)[0],
        "final_url": final_url,
    }


def probe_video(path: Path) -> dict:
    executable = shutil.which("ffprobe")
    if not executable:
        return {}
    command = [
        executable,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,codec_name:format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
        data = json.loads(completed.stdout)
        stream = (data.get("streams") or [{}])[0]
        fmt = data.get("format") or {}
        return {
            "duration": float(fmt["duration"]) if fmt.get("duration") else None,
            "width": stream.get("width"),
            "height": stream.get("height"),
            "codec": stream.get("codec_name"),
        }
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
        return {}


def existing_file_matches(path: Path, expected_bytes: int, expected_sha256: str) -> bool:
    return path.exists() and path.stat().st_size == expected_bytes and sha256_file(path) == expected_sha256
