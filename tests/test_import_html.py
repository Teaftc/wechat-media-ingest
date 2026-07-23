import hashlib
from pathlib import Path

from wechat_media_ingest.pipeline import import_html
from wechat_media_ingest.verify import verify_path

FIXTURE = Path(__file__).parent / "fixtures" / "article_native_video.html"
URL = "https://mp.weixin.qq.com/s?__biz=abc%3D%3D&mid=123&idx=1&sn=deadbeef"


def test_import_html_uses_local_page_and_verifies_snapshot(tmp_path, monkeypatch):
    calls = {"download": 0}

    def fake_download(url, destination, **kwargs):
        calls["download"] += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = b"\x00\x00\x00\x18ftypmp42" + b"x" * 12 if kwargs["kind"] == "video" else b"\x89PNG\r\n\x1a\n" + b"x" * 16
        destination.write_bytes(payload)
        return {
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "content_type": "video/mp4" if kwargs["kind"] == "video" else "image/png",
            "final_url": url,
        }

    monkeypatch.setattr("wechat_media_ingest.pipeline.download_file", fake_download)
    monkeypatch.setattr("wechat_media_ingest.pipeline.probe_video", lambda path: {})
    monkeypatch.setattr(
        "wechat_media_ingest.pipeline._fetch",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network page fetch must not run")),
    )

    manifest = import_html(FIXTURE, URL, tmp_path)

    assert manifest["job"]["status"] == "complete"
    assert manifest["job"]["fetch_method"] == "local_html"
    assert manifest["summary"] == {"complete": 4, "skipped": 0, "out_of_scope": 1, "failed": 0}
    assert calls["download"] == 2
    assert verify_path(tmp_path / manifest["job"]["job_id"])["ok"] is True


def test_import_html_rejects_non_utf8_file(tmp_path):
    html_path = tmp_path / "bad.html"
    html_path.write_bytes(b"\xff\xfe\x00")
    manifest = import_html(html_path, URL, tmp_path / "output")
    assert manifest["job"]["status"] == "failed"
    assert manifest["job"]["error"]["code"] == "PARSE_ERROR"


def test_import_html_rejects_captcha_fixture(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "article_captcha.html"
    manifest = import_html(fixture, URL, tmp_path)
    assert manifest["job"]["status"] == "failed"
    assert manifest["job"]["error"]["code"] == "CAPTCHA"
