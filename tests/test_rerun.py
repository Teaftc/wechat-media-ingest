from pathlib import Path

from wechat_media_ingest.fetch.http import FetchResult
from wechat_media_ingest.pipeline import ingest_url
from wechat_media_ingest.verify import verify_path

FIXTURE = Path(__file__).parent / "fixtures" / "article_native_video.html"
URL = "https://mp.weixin.qq.com/s?__biz=abc%3D%3D&mid=123&idx=1&sn=deadbeef&scene=21"


def test_ingest_and_idempotent_rerun(tmp_path, monkeypatch):
    html = FIXTURE.read_text(encoding="utf-8")
    calls = {"fetch": 0, "download": 0}

    def fake_fetch(url, fetcher):
        calls["fetch"] += 1
        return FetchResult(html, URL, "fixture")

    def fake_download(url, destination, **kwargs):
        calls["download"] += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        if kwargs["kind"] == "video":
            payload = b"\x00\x00\x00\x18ftypmp42" + b"x" * 12
        else:
            payload = b"\x89PNG\r\n\x1a\n" + b"x" * 16
        destination.write_bytes(payload)
        import hashlib

        return {
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "content_type": "video/mp4" if kwargs["kind"] == "video" else "image/png",
            "final_url": url,
        }

    monkeypatch.setattr("wechat_media_ingest.pipeline._fetch", fake_fetch)
    monkeypatch.setattr("wechat_media_ingest.pipeline.download_file", fake_download)
    monkeypatch.setattr("wechat_media_ingest.pipeline.probe_video", lambda path: {})

    first = ingest_url(URL, tmp_path)
    assert first["job"]["status"] == "complete"
    assert first["summary"] == {"complete": 4, "skipped": 0, "out_of_scope": 1, "failed": 0}
    job_dir = tmp_path / first["job"]["job_id"]
    assert verify_path(job_dir)["ok"] is True

    second = ingest_url(URL, tmp_path)
    assert second["rerun"]["action"] == "skipped"
    assert calls == {"fetch": 1, "download": 2}


def test_force_new_snapshot_fetch_failure_does_not_clone_old_assets(tmp_path, monkeypatch):
    from wechat_media_ingest.errors import ErrorCode, IngestError
    from wechat_media_ingest.manifest import atomic_write_json
    from wechat_media_ingest.normalize import identify_article

    identity = identify_article(URL)
    job_dir = tmp_path / identity.job_id
    old_snapshot = job_dir / "old-snapshot"
    old_snapshot.mkdir(parents=True)
    old_manifest = {
        "schema_version": "1.0",
        "job": {"job_id": identity.job_id, "snapshot_id": "old-snapshot", "status": "complete"},
        "article": {"title": "old"},
        "assets": [{"id": "old_asset", "status": "complete"}],
        "summary": {"complete": 1, "skipped": 0, "out_of_scope": 0, "failed": 0},
    }
    atomic_write_json(old_snapshot / "manifest.json", old_manifest)
    atomic_write_json(
        job_dir / "job.json",
        {"current_snapshot": "old-snapshot", "job_id": identity.job_id, "canonical_url": identity.canonical_url},
    )

    def blocked_fetch(url, fetcher):
        raise IngestError(ErrorCode.CAPTCHA, "blocked")

    monkeypatch.setattr("wechat_media_ingest.pipeline._fetch", blocked_fetch)
    failed = ingest_url(URL, tmp_path, force_new_snapshot=True)

    assert failed["job"]["status"] == "failed"
    assert failed["job"]["snapshot_id"] != "old-snapshot"
    assert failed["assets"] == []
    assert old_manifest == __import__("wechat_media_ingest.manifest", fromlist=["load_json"]).load_json(
        old_snapshot / "manifest.json"
    )
