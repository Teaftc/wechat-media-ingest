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
