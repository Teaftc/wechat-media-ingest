from __future__ import annotations

import argparse
import importlib.metadata
import json
import shutil
import sys
from pathlib import Path

from . import __version__
from .errors import EXIT_ENVIRONMENT, EXIT_INTEGRITY, EXIT_JOB_FAILED, EXIT_OK, EXIT_PARTIAL, ErrorCode, IngestError
from .fetch import browser_available
from .pipeline import ingest_url, inspect_url
from .verify import verify_path


def _print_json(data: dict, stream=None) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2), file=stream or sys.stdout)


def doctor() -> dict:
    packages = {}
    for name in ("httpx", "beautifulsoup4", "lxml", "markdownify", "playwright"):
        try:
            packages[name] = {"available": True, "version": importlib.metadata.version(name)}
        except importlib.metadata.PackageNotFoundError:
            packages[name] = {"available": False, "version": ""}
    browser_ok, browser_detail = browser_available()
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    required_ok = all(packages[name]["available"] for name in ("httpx", "beautifulsoup4", "lxml", "markdownify"))
    return {
        "ok": required_ok,
        "tool_version": __version__,
        "python": {"version": sys.version.split()[0], "executable": sys.executable},
        "packages": packages,
        "browser": {"available": browser_ok, "detail": browser_detail, "optional": True},
        "ffmpeg": {"available": bool(ffmpeg), "path": ffmpeg or "", "optional": True},
        "ffprobe": {"available": bool(ffprobe), "path": ffprobe or "", "optional": True},
        "notes": [
            "doctor is read-only and does not install browsers or change system settings",
            "browser support is optional; install with pip install .[browser] and playwright install chromium",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wechat-media-ingest", description="Archive public WeChat article media")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="check runtime dependencies without changing the system")

    inspect_parser = sub.add_parser("inspect", help="fetch and list article assets without downloading media")
    inspect_parser.add_argument("url")
    inspect_parser.add_argument("--fetcher", choices=("auto", "http", "browser"), default="auto")
    inspect_parser.add_argument("--quality", choices=("highest", "balanced", "smallest"), default="highest")

    ingest_parser = sub.add_parser("ingest", help="archive an article and its supported assets")
    ingest_parser.add_argument("url")
    ingest_parser.add_argument("--output", type=Path)
    ingest_parser.add_argument("--fetcher", choices=("auto", "http", "browser"), default="auto")
    ingest_parser.add_argument("--quality", choices=("highest", "balanced", "smallest"), default="highest")
    ingest_parser.add_argument("--force-new-snapshot", action="store_true")
    ingest_parser.add_argument("--dry-run", action="store_true", help="inspect assets without writing files")

    verify_parser = sub.add_parser("verify", help="verify manifest file sizes and SHA-256 hashes")
    verify_parser.add_argument("path", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "doctor":
            report = doctor()
            _print_json(report)
            return EXIT_OK if report["ok"] else EXIT_ENVIRONMENT
        if args.command == "inspect":
            _print_json(inspect_url(args.url, fetcher=args.fetcher, quality=args.quality))
            return EXIT_OK
        if args.command == "ingest":
            if args.dry_run:
                _print_json(inspect_url(args.url, fetcher=args.fetcher, quality=args.quality))
                return EXIT_OK
            if args.output is None:
                raise IngestError(ErrorCode.UNSUPPORTED, "--output is required unless --dry-run is used")
            manifest = ingest_url(
                args.url,
                args.output,
                fetcher=args.fetcher,
                quality=args.quality,
                force_new_snapshot=args.force_new_snapshot,
            )
            _print_json(manifest)
            status = manifest.get("job", {}).get("status")
            if status == "complete":
                return EXIT_OK
            if status == "partial":
                return EXIT_PARTIAL
            error_code = manifest.get("job", {}).get("error", {}).get("code") if manifest.get("job", {}).get("error") else None
            return EXIT_INTEGRITY if error_code == ErrorCode.INTEGRITY else EXIT_JOB_FAILED
        if args.command == "verify":
            report = verify_path(args.path)
            _print_json(report)
            return EXIT_OK if report["ok"] else EXIT_INTEGRITY
    except IngestError as exc:
        _print_json({"ok": False, "error": {"code": exc.code, "message": exc.message}}, stream=sys.stderr)
        return EXIT_INTEGRITY if exc.code == ErrorCode.INTEGRITY else EXIT_JOB_FAILED
    except (FileNotFoundError, ValueError) as exc:
        _print_json({"ok": False, "error": {"code": ErrorCode.INTEGRITY, "message": str(exc)}}, stream=sys.stderr)
        return EXIT_INTEGRITY
    return EXIT_JOB_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
