import hashlib
from pathlib import Path
from unittest import mock

from wechat_media_ingest.manifest import atomic_write_json, sha256_file
from wechat_media_ingest.verify import verify_path


def test_sha256_file_streams(tmp_path):
    path = tmp_path / "large.bin"
    payload = b"x" * 8193
    path.write_bytes(payload)
    with mock.patch.object(Path, "read_bytes", side_effect=AssertionError("whole-file read")):
        assert sha256_file(path, chunk_size=257) == hashlib.sha256(payload).hexdigest()


def test_verify_detects_corruption(tmp_path):
    snapshot = tmp_path / "job" / "snapshot"
    snapshot.mkdir(parents=True)
    data = snapshot / "article.md"
    data.write_text("ok", encoding="utf-8")
    manifest = {
        "assets": [
            {
                "id": "article_markdown",
                "status": "complete",
                "local_path": "article.md",
                "bytes": data.stat().st_size,
                "sha256": sha256_file(data),
            }
        ]
    }
    atomic_write_json(snapshot / "manifest.json", manifest)
    assert verify_path(snapshot)["ok"] is True
    data.write_text("changed", encoding="utf-8")
    report = verify_path(snapshot)
    assert report["ok"] is False
    assert report["failures"][0]["reason"] == "size mismatch"
