import json

from wechat_media_ingest.cli import main
from wechat_media_ingest.errors import EXIT_JOB_FAILED, EXIT_OK


def test_ingest_dry_run_does_not_require_output(monkeypatch, capsys):
    monkeypatch.setattr(
        "wechat_media_ingest.cli.inspect_url",
        lambda url, fetcher, quality: {"url": url, "fetcher": fetcher, "quality": quality},
    )
    code = main(["ingest", "https://mp.weixin.qq.com/s/example", "--dry-run", "--quality", "smallest"])
    report = json.loads(capsys.readouterr().out)
    assert code == EXIT_OK
    assert report["quality"] == "smallest"


def test_ingest_requires_output_without_dry_run(capsys):
    code = main(["ingest", "https://mp.weixin.qq.com/s/example"])
    report = json.loads(capsys.readouterr().err)
    assert code == EXIT_JOB_FAILED
    assert report["error"]["code"] == "UNSUPPORTED"


def test_import_html_command(monkeypatch, capsys, tmp_path):
    html_file = tmp_path / "article.html"
    html_file.write_text("<html></html>", encoding="utf-8")
    captured = {}

    def fake_import(path, source_url, output, quality, force_new_snapshot):
        captured.update(
            path=path,
            source_url=source_url,
            output=output,
            quality=quality,
            force_new_snapshot=force_new_snapshot,
        )
        return {"job": {"status": "complete"}}

    monkeypatch.setattr("wechat_media_ingest.cli.import_html", fake_import)
    code = main(
        [
            "import-html",
            str(html_file),
            "--source-url",
            "https://mp.weixin.qq.com/s/example",
            "--output",
            str(tmp_path / "archive"),
            "--quality",
            "balanced",
        ]
    )

    assert code == EXIT_OK
    assert json.loads(capsys.readouterr().out)["job"]["status"] == "complete"
    assert captured["path"] == html_file
    assert captured["quality"] == "balanced"
