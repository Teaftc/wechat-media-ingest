from pathlib import Path

import pytest

from wechat_media_ingest.errors import ErrorCode, IngestError
from wechat_media_ingest.fetch.http import classify_page
from wechat_media_ingest.parse.article import parse_article

FIXTURES = Path(__file__).parent / "fixtures"


def test_text_only_fixture_parses_without_assets():
    article = parse_article((FIXTURES / "article_text_only.html").read_text(encoding="utf-8-sig"))
    assert article.title == "Text Only Fixture"
    assert article.image_urls == []
    assert article.native_videos == []


def test_lazy_image_fixture_prefers_data_src():
    article = parse_article((FIXTURES / "article_images.html").read_text(encoding="utf-8-sig"))
    assert article.image_urls == [
        "https://mmbiz.qpic.cn/test/first.jpg?wx_fmt=jpeg",
        "https://mmbiz.qlogo.cn/test/second.png",
    ]


@pytest.mark.parametrize(
    ("fixture", "code"),
    [("article_deleted.html", ErrorCode.DELETED), ("article_captcha.html", ErrorCode.CAPTCHA)],
)
def test_static_error_fixtures_are_classified(fixture, code):
    text = (FIXTURES / fixture).read_text(encoding="utf-8-sig")
    with pytest.raises(IngestError) as caught:
        classify_page(text, "https://mp.weixin.qq.com/s/example")
    assert caught.value.code == code
