from __future__ import annotations

import html as html_lib
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass

from ..errors import ErrorCode, IngestError

TRANSCODE_RE = re.compile(
    r"format_id:\s*['\"](?P<format_id>\d+)['\"]\s*\*\s*1,"
    r".*?width:\s*['\"](?P<width>\d+)['\"]\s*\*\s*1,"
    r".*?height:\s*['\"](?P<height>\d+)['\"]\s*\*\s*1,"
    r".*?(?:duration|vDuration):\s*['\"](?P<duration_s>\d+(?:\.\d+)?)['\"]\s*\*\s*1,"
    r".*?filesize:\s*['\"](?P<filesize>\d+)['\"](?:\s*\*\s*1)?(?:\s*\|\|\s*0)?,"
    r".*?url:\s*(?:JsDecode\()?['\"](?P<url>https?://[^'\"]+?\.mp4[^'\"]*)['\"]\)?",
    re.DOTALL,
)
VIDEO_BLOCK_RE = re.compile(
    r"video_id:\s*['\"](?P<mpvid>wxv_\d+)['\"].*?mp_video_trans_info:\s*\[(?P<body>.*?)\]\s*,",
    re.DOTALL,
)
IFRAME_MPVID_RE = re.compile(r'data-mpvid=["\'](?P<mpvid>wxv_\d+)["\']')


@dataclass(frozen=True)
class Transcode:
    format_id: str
    width: int
    height: int
    duration_s: float
    filesize: int
    url: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class NativeVideo:
    mpvid: str
    transcodes: tuple[Transcode, ...]


def parse_transcodes(text: str) -> list[Transcode]:
    seen: set[tuple[str, str]] = set()
    results: list[Transcode] = []
    for match in TRANSCODE_RE.finditer(text):
        values = match.groupdict()
        url = html_lib.unescape(values["url"])
        url = url.replace(r"\x26amp;", "&").replace(r"\x26", "&")
        if url.startswith("http://"):
            url = "https://" + url[len("http://") :]
        key = (values["format_id"], url.split("?", 1)[0])
        if key in seen:
            continue
        seen.add(key)
        results.append(
            Transcode(
                format_id=values["format_id"],
                width=int(values["width"]),
                height=int(values["height"]),
                duration_s=float(values["duration_s"]),
                filesize=int(values["filesize"]),
                url=url,
            )
        )
    return results


def parse_native_videos(page_html: str) -> list[NativeVideo]:
    by_id: dict[str, list[Transcode]] = {}
    for match in VIDEO_BLOCK_RE.finditer(page_html):
        transcodes = parse_transcodes(match.group("body"))
        if transcodes:
            by_id[match.group("mpvid")] = transcodes

    iframe_ids = list(dict.fromkeys(IFRAME_MPVID_RE.findall(page_html)))
    if not by_id and len(iframe_ids) == 1:
        transcodes = parse_transcodes(page_html)
        if transcodes:
            by_id[iframe_ids[0]] = transcodes

    ordered_ids = iframe_ids + [mpvid for mpvid in by_id if mpvid not in iframe_ids]
    return [NativeVideo(mpvid, tuple(by_id.get(mpvid, ()))) for mpvid in ordered_ids]


def choose_transcode(transcodes: Iterable[Transcode], policy: str) -> Transcode:
    items = list(transcodes)
    if not items:
        raise IngestError(ErrorCode.MEDIA_EXPIRED, "native video has no downloadable MP4 transcodes")
    if policy == "smallest":
        return min(items, key=lambda item: (item.filesize, item.width * item.height))
    if policy == "balanced":
        suitable = [item for item in items if item.width >= 1080]
        if suitable:
            return min(suitable, key=lambda item: (item.filesize, -(item.width * item.height)))
    if policy not in {"highest", "balanced", "smallest"}:
        raise IngestError(ErrorCode.UNSUPPORTED, f"unknown quality policy: {policy}")
    return max(items, key=lambda item: (item.width * item.height, item.filesize))
