from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .errors import ErrorCode, IngestError

ARTICLE_HOSTS = {"mp.weixin.qq.com"}
IDENTITY_KEYS = ("__biz", "mid", "idx", "sn")
TRACKING_KEYS = {
    "chksm",
    "scene",
    "srcid",
    "sharer_shareinfo",
    "sharer_shareinfo_first",
    "exportkey",
    "pass_ticket",
    "wx_header",
    "from",
    "isappinstalled",
    "clicktime",
    "enterid",
    "subscene",
    "sessionid",
    "ascene",
    "fasttmpl_type",
    "fasttmpl_fullversion",
    "fasttmpl_flag",
    "realreporttime",
    "devicetype",
    "version",
    "nettype",
    "lang",
    "nwr_flag",
}
WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


@dataclass(frozen=True)
class ArticleIdentity:
    canonical_url: str
    job_id: str
    method: str
    fields: dict[str, str]


def _validate_article_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"}:
        raise IngestError(ErrorCode.UNSUPPORTED, "URL must use http or https")
    host = (parts.hostname or "").lower().rstrip(".")
    if host not in ARTICLE_HOSTS:
        raise IngestError(ErrorCode.UNSUPPORTED, f"unsupported article host: {host or '<missing>'}")


def identify_article(url: str) -> ArticleIdentity:
    _validate_article_url(url)
    parts = urlsplit(url)
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    params: dict[str, str] = {}
    for key, value in pairs:
        if key not in TRACKING_KEYS and key not in params:
            params[key] = value
    fields = {key: params.get(key, "") for key in IDENTITY_KEYS}
    if all(fields.values()):
        canonical_query = urlencode([(key, fields[key]) for key in IDENTITY_KEYS])
        canonical_url = f"https://mp.weixin.qq.com/s?{canonical_query}"
        raw = "|".join(fields[key] for key in IDENTITY_KEYS)
        suffix = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]
        job_id = f"wechat_{fields['mid']}_{fields['idx']}_{suffix}"
        return ArticleIdentity(canonical_url, job_id, "wechat_identity", fields)

    kept = [(key, value) for key, value in pairs if key not in TRACKING_KEYS]
    kept.sort()
    path = re.sub(r"/+", "/", parts.path or "/")
    canonical_url = urlunsplit(("https", "mp.weixin.qq.com", path, urlencode(kept), ""))
    suffix = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:16]
    return ArticleIdentity(canonical_url, f"wechat_url_{suffix}", "url_hash", fields)


def safe_component(value: str, fallback: str = "item", max_length: int = 80) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        cleaned = fallback
    if cleaned.upper() in WINDOWS_RESERVED:
        cleaned = f"_{cleaned}"
    return cleaned[:max_length].rstrip(" .") or fallback
