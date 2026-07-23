from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from markdownify import markdownify

from .native_video import NativeVideo, parse_native_videos

PUBLISH_TS_RE = re.compile(r"var\s+ct\s*=\s*['\"](\d+)['\"]")
IMAGE_URL_RE = re.compile(r"^https?://mmbiz\.(?:qpic|qlogo)\.cn/", re.IGNORECASE)


@dataclass
class ParsedArticle:
    title: str
    account: str
    publish_time: str
    content_html: str
    markdown: str
    image_urls: list[str]
    native_videos: list[NativeVideo]
    out_of_scope: list[dict]


def _clean_markdown(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\(data:[^)]+\)", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def _publish_time(soup: BeautifulSoup, page_html: str) -> str:
    visible = soup.select_one("#publish_time")
    if visible and visible.get_text(" ", strip=True):
        return visible.get_text(" ", strip=True)
    match = PUBLISH_TS_RE.search(page_html)
    if match:
        return datetime.fromtimestamp(int(match.group(1)), tz=timezone.utc).isoformat()
    return ""


def _detect_out_of_scope(soup: BeautifulSoup, page_html: str) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for iframe in soup.select("iframe"):
        src = iframe.get("data-src") or iframe.get("src") or ""
        if "v.qq.com" in src:
            key = ("tencent_video", src)
            if key not in seen:
                seen.add(key)
                rows.append({"type": "tencent_video", "source_url": src, "reason": "not supported by MVP"})
        if "channels.weixin.qq.com" in src or "finder" in src.lower():
            key = ("wechat_channels", src)
            if key not in seen:
                seen.add(key)
                rows.append({"type": "wechat_channels", "source_url": src, "reason": "not supported by MVP"})
    if "channels.weixin.qq.com" in page_html and not any(row["type"] == "wechat_channels" for row in rows):
        rows.append({"type": "wechat_channels", "source_url": "", "reason": "detected but not supported by MVP"})
    return rows


def parse_article(page_html: str) -> ParsedArticle:
    soup = BeautifulSoup(page_html, "lxml")
    title_tag = soup.select_one("#activity-name, h1.rich_media_title")
    account_tag = soup.select_one("#js_name")
    content = soup.select_one("#js_content")
    if content is None:
        raise ValueError("article body #js_content was not found")

    image_urls: list[str] = []
    for image in content.select("img"):
        source = image.get("data-src") or image.get("src") or ""
        if source and IMAGE_URL_RE.match(source):
            if source not in image_urls:
                image_urls.append(source)
            image["src"] = source
        image.attrs.pop("data-src", None)
        if image.get("src", "").startswith("data:"):
            image.decompose()

    content_html = str(content)
    md = _clean_markdown(markdownify(content_html, heading_style="ATX", bullets="-"))
    return ParsedArticle(
        title=title_tag.get_text(" ", strip=True) if title_tag else "",
        account=account_tag.get_text(" ", strip=True) if account_tag else "",
        publish_time=_publish_time(soup, page_html),
        content_html=content_html,
        markdown=md,
        image_urls=image_urls,
        native_videos=parse_native_videos(page_html),
        out_of_scope=_detect_out_of_scope(soup, page_html),
    )
