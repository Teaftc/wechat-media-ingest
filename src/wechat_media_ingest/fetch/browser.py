from __future__ import annotations

from pathlib import Path

from ..errors import ErrorCode, IngestError
from ..security import ARTICLE_HOSTS, validate_public_url
from .http import HEADERS, FetchResult, classify_page, page_has_article


def browser_available() -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "playwright is not installed"
    try:
        with sync_playwright() as playwright:
            executable = Path(playwright.chromium.executable_path)
            if not executable.exists():
                return False, f"Chromium is not installed at {executable}"
    except Exception as exc:  # pragma: no cover - environment-specific
        return False, str(exc)
    return True, "available"


def fetch_browser(url: str, timeout_ms: int = 45_000) -> FetchResult:
    validate_public_url(url, ARTICLE_HOSTS)
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise IngestError(ErrorCode.UNSUPPORTED, "browser fallback requires: pip install .[browser]") from exc

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=HEADERS["User-Agent"],
                locale="zh-CN",
                extra_http_headers={"Referer": HEADERS["Referer"], "Accept-Language": HEADERS["Accept-Language"]},
            )
            page = context.new_page()

            def guard_request(route):
                request = route.request
                if not request.is_navigation_request():
                    route.abort("blockedbyclient")
                    return
                try:
                    validate_public_url(request.url, ARTICLE_HOSTS)
                except IngestError:
                    route.abort("blockedbyclient")
                    return
                route.continue_()

            page.route("**/*", guard_request)
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_selector("#js_content", timeout=timeout_ms)
            except PlaywrightTimeoutError:
                pass
            page.eval_on_selector_all(
                "img[data-src]",
                "els => els.forEach(img => { if (!img.src || img.src.startsWith('data:')) img.src = img.dataset.src; })",
            )
            html = page.content()
            final_url = page.url
            context.close()
            browser.close()
    except IngestError:
        raise
    except Exception as exc:
        raise IngestError(ErrorCode.NETWORK, f"browser fetch failed: {exc}") from exc

    validate_public_url(final_url, ARTICLE_HOSTS)
    classify_page(html, final_url)
    if not page_has_article(html):
        raise IngestError(ErrorCode.PARSE_ERROR, "browser response did not contain a complete article body")
    return FetchResult(html, final_url, "browser")
