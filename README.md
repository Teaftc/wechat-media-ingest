# wechat-media-ingest

Archive a **single public or authorized WeChat article URL** into an immutable,
verifiable snapshot containing the original HTML, clean Markdown, local images,
WeChat-native MP4 video, logs, and `manifest.json`.

> 中文简介：这是一个微信公众号原始资料与证据入库 CLI。它只负责采集和校验，
> 不负责转写、OCR、摘要、市场分析、发布或交易决策。

## Why

Normal article readers are convenient for one-off reading, but downstream tools
need a stable contract: deterministic job IDs, resumable downloads, per-asset
status, hashes, explicit errors, and rerun semantics. This CLI provides that
collection layer without changing system proxies, installing root certificates,
or storing login cookies.

## Scope

Supported in `0.1.0`:

- one explicit `mp.weixin.qq.com` article URL;
- guarded HTTP fetch with optional fresh Playwright browser fetch;
- title, account, publish time, canonical URL, raw HTML, and Markdown;
- local WeChat CDN images;
- WeChat-native `wxv_...` MP4 transcodes;
- streaming downloads, `.part` resume, SHA-256, optional ffprobe metadata;
- idempotent reruns and explicit new snapshots;
- `doctor`, `inspect`, `ingest`, and `verify` commands.

Explicitly not supported:

- Tencent Video or WeChat Channels downloads;
- account discovery, history crawling, search, cookies, private content;
- transcription, OCR, keyframes, summaries, reports, publishing, or trading.

Unsupported media is recorded as `out_of_scope` instead of being silently lost.

## Install

Python 3.10+:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e .
```

Optional browser fallback:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[browser]"
.\.venv\Scripts\playwright.exe install chromium
```

Optional development tools:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[browser,dev]"
```

The CLI never installs browsers or changes the machine automatically. Run the
read-only environment check:

```powershell
wechat-media-ingest doctor
```

## Usage

Inspect only; do not download media:

```powershell
wechat-media-ingest inspect "https://mp.weixin.qq.com/s?..."
```

The explicit ingest dry-run form is equivalent and does not require an output
directory:

```powershell
wechat-media-ingest ingest "https://mp.weixin.qq.com/s?..." --dry-run
```

Archive an article:

```powershell
wechat-media-ingest ingest "https://mp.weixin.qq.com/s?..." --output D:\WeChatArchive
```

Force a new immutable snapshot when an article may have changed:

```powershell
wechat-media-ingest ingest "https://mp.weixin.qq.com/s?..." --output D:\WeChatArchive --force-new-snapshot
```

Verify a job or snapshot:

```powershell
wechat-media-ingest verify D:\WeChatArchive\wechat_123_1_ab12cd34ef
```

Choose a fetcher explicitly if needed:

```powershell
wechat-media-ingest inspect "https://mp.weixin.qq.com/s?..." --fetcher browser
```

`auto` tries guarded HTTP first. It may use the browser for incomplete/network
responses, but an explicit CAPTCHA stops the job immediately to avoid repeated
requests. The browser fetcher blocks non-navigation subresources; media is
downloaded separately through the same allowlist and IP checks as HTTP mode.

## Output

```text
<output>/
  <job_id>/
    job.json
    <snapshot_id>/
      original.html
      article.md
      manifest.json
      assets/
        images/
        videos/
      logs/
        ingest.jsonl
```

A default rerun verifies and returns an already complete snapshot without
refetching or redownloading. Partial jobs reuse `.part` files. If page content
changes inside the active snapshot, the CLI reports `INTEGRITY`; use
`--force-new-snapshot` to preserve both versions.

See [docs/MANIFEST.md](docs/MANIFEST.md) for the contract and
[docs/VALIDATION.md](docs/VALIDATION.md) for reproducible validation evidence.

## Exit codes

| Code | Meaning |
|---:|---|
| 0 | Complete / verification passed |
| 10 | Partial job; one or more assets failed |
| 20 | Job failed (fetch, parse, CAPTCHA, unsupported input) |
| 30 | Integrity verification failed |
| 40 | Required runtime dependency missing |

Per-asset errors in `manifest.json` are authoritative. Error codes include
`CAPTCHA`, `DELETED`, `AUTH_REQUIRED`, `MEDIA_EXPIRED`, `NETWORK`, `INTEGRITY`,
`PARSE_ERROR`, and `UNSUPPORTED`.

## Safety and responsible use

Use only public or authorized content. Keep requests serial and low-frequency.
Do not use this project to bypass access controls or platform protections.
WeChat behavior can change; a CAPTCHA is an external stop condition, not a
signal to retry aggressively.

## License

MIT. See `NOTICE.md` and `LICENSES/` for third-party attribution.
