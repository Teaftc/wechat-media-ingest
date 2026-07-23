from pathlib import Path

from wechat_media_ingest.parse.article import parse_article
from wechat_media_ingest.parse.native_video import choose_transcode

FIXTURE = Path(__file__).parent / "fixtures" / "article_native_video.html"


def test_article_parser_extracts_supported_and_out_of_scope_assets():
    article = parse_article(FIXTURE.read_text(encoding="utf-8"))
    assert article.title == "Synthetic WeChat Article"
    assert article.account == "Fixture Account"
    assert article.image_urls == ["https://mmbiz.qpic.cn/test/fixture.png?wx_fmt=png"]
    assert len(article.native_videos) == 1
    assert article.native_videos[0].mpvid == "wxv_1234567890"
    assert len(article.native_videos[0].transcodes) == 2
    assert article.out_of_scope[0]["type"] == "tencent_video"
    assert "synthetic fixture" in article.markdown.lower()


def test_native_video_quality_selection():
    article = parse_article(FIXTURE.read_text(encoding="utf-8"))
    selected = choose_transcode(article.native_videos[0].transcodes, "highest")
    assert selected.format_id == "10002"
    assert selected.url == "https://mpvideo.qpic.cn/test/fixture.f10002.mp4?x=1&y=2"
