from __future__ import annotations

from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from ..errors import ErrorCode, IngestError
from ..security import ARTICLE_HOSTS, redirect_target, validate_public_url

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36 "
    "MicroMessenger/8.0.43"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://mp.weixin.qq.com/",
}


@dataclass(frozen=True)
class FetchResult:
    html: str
    final_url: str
    method: str


def classify_page(text: str, final_url: str) -> None:
    lower_url = final_url.lower()
    if "appmsgcaptcha" in lower_url or "请输入验证码" in text or "环境异常" in text:
        raise IngestError(ErrorCode.CAPTCHA, "WeChat returned an anti-bot challenge; stop and retry later")
    if "该内容已被发布者删除" in text or "内容已被发布者删除" in text:
        raise IngestError(ErrorCode.DELETED, "the article was deleted by its publisher")
    if "此内容因违规无法查看" in text or "已停止访问该网页" in text:
        raise IngestError(ErrorCode.DELETED, "the article is unavailable")
    if "登录后可查看" in text or "请在微信客户端打开链接" in text:
        raise IngestError(ErrorCode.AUTH_REQUIRED, "the article requires an authenticated client")


def page_has_article(text: str) -> bool:
    soup = BeautifulSoup(text, "lxml")
    content = soup.select_one("#js_content")
    title = soup.select_one("#activity-name, h1.rich_media_title")
    return bool(content and title and content.get_text("", strip=True))


def fetch_http(url: str, timeout: float = 45.0, max_redirects: int = 8) -> FetchResult:
    current = validate_public_url(url, ARTICLE_HOSTS)
    try:
        with httpx.Client(headers=HEADERS, timeout=timeout, follow_redirects=False) as client:
            for _ in range(max_redirects + 1):
                response = client.get(current)
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise IngestError(ErrorCode.NETWORK, "redirect response omitted Location")
                    current = redirect_target(current, location, ARTICLE_HOSTS)
                    continue
                response.raise_for_status()
                text = response.text
                final_url = str(response.url)
                classify_page(text, final_url)
                if not page_has_article(text):
                    raise IngestError(ErrorCode.PARSE_ERROR, "HTTP response did not contain a complete article body")
                return FetchResult(text, final_url, "http")
    except IngestError:
        raise
    except httpx.HTTPStatusError as exc:
        raise IngestError(ErrorCode.NETWORK, f"HTTP status {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise IngestError(ErrorCode.NETWORK, str(exc)) from exc
    raise IngestError(ErrorCode.NETWORK, f"too many redirects (>{max_redirects})")
