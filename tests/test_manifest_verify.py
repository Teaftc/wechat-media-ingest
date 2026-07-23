import hashlib
from pathlib import Path
from unittest import mock

from wechat_media_ingest.manifest import atomic_write_json, file_asset, new_manifest, sha256_file, update_summary
from wechat_media_ingest.verify import verify_path

URL = "https://mp.weixin.qq.com/s?__biz=abc%3D%3D&mid=123&idx=1&sn=deadbeef"


def test_sha256_file_streams(tmp_path):
    path = tmp_path / "large.bin"
    payload = b"x" * 8193
    path.write_bytes(payload)
    with mock.patch.object(Path, "read_bytes", side_effect=AssertionError("whole-file read")):
        assert sha256_file(path, chunk_size=257) == hashlib.sha256(payload).hexdigest()


def _valid_manifest(snapshot: Path, data: Path) -> dict:
    manifest = new_manifest(
        input_url=URL,
        final_url=URL,
        canonical_url=URL,
        job_id="wechat_123_1_fixture",
        snapshot_id=snapshot.name,
        identity_method="wechat_identity",
        identity_fields={"__biz": "abc==", "mid": "123", "idx": "1", "sn": "deadbeef"},
        fetch_method="fixture",
    )
    manifest["job"]["status"] = "complete"
    manifest["assets"] = [file_asset("article_markdown", "article_markdown", URL, "article.md", data)]
    update_summary(manifest)
    return manifest


def test_verify_detects_corruption(tmp_path):
    snapshot = tmp_path / "job" / "snapshot"
    snapshot.mkdir(parents=True)
    data = snapshot / "article.md"
    data.write_text("ok", encoding="utf-8")
    atomic_write_json(snapshot / "manifest.json", _valid_manifest(snapshot, data))

    report = verify_path(snapshot)
    assert report["ok"] is True
    assert report["schema_valid"] is True

    data.write_text("changed", encoding="utf-8")
    report = verify_path(snapshot)
    assert report["ok"] is False
    assert report["failures"][0]["reason"] == "size mismatch"


def test_verify_rejects_manifest_schema_error(tmp_path):
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    atomic_write_json(snapshot / "manifest.json", {"schema_version": "1.0", "assets": []})

    report = verify_path(snapshot)
    assert report["ok"] is False
    assert report["schema_valid"] is False
    assert any(failure["reason"] == "schema validation failed" for failure in report["failures"])


def test_verify_rejects_failed_job_even_without_assets(tmp_path):
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    marker = snapshot / "article.md"
    marker.write_text("ok", encoding="utf-8")
    manifest = _valid_manifest(snapshot, marker)
    manifest["job"]["status"] = "failed"
    manifest["job"]["error"] = {"code": "CAPTCHA", "message": "blocked"}
    manifest["assets"] = []
    update_summary(manifest)
    atomic_write_json(snapshot / "manifest.json", manifest)

    report = verify_path(snapshot)
    assert report["ok"] is False
    assert any(failure["id"] == "<job>" for failure in report["failures"])
