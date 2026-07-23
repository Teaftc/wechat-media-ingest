---
name: wechat-media-ingest
description: Archive and verify public or authorized WeChat public-account articles with the wechat-media-ingest CLI. Use when a user provides an mp.weixin.qq.com article URL or an authorized local HTML export and asks to collect, archive, download, inspect, verify, or preserve its HTML, Markdown, images, or WeChat-native video. Also trigger for 微信公众号文章归档、微信文章媒体下载、公众号原始资料入库、manifest 校验. Do not use for account-history crawling, search, cookies, CAPTCHA bypass, Tencent Video or WeChat Channels downloads, transcription, OCR, summarization, publishing, or trading.
---

# WeChat Media Ingest

Use the installed `wechat-media-ingest` CLI as the only implementation. Do not duplicate its fetch, parsing, download, hashing, or verification logic in the skill.

## Resolve the CLI

1. Prefer `wechat-media-ingest` when it is on `PATH`.
2. In a source checkout, use its active virtual environment or run `python -m wechat_media_ingest`.
3. Run `wechat-media-ingest doctor` before the first ingest operation in an unfamiliar environment. Treat it as read-only; do not install browsers or change system settings without an explicit request.

## Choose one workflow

### Archive an explicit URL

Use one ingest request rather than fetching the page twice:

```powershell
wechat-media-ingest ingest "<mp.weixin.qq.com URL>" --output "<archive root>"
```

Add `--quality balanced` or `--quality smallest` only when the user requests a smaller native-video transcode. Add `--force-new-snapshot` only when the user explicitly wants a new immutable version or the CLI reports changed content in the active snapshot.

Use `inspect` or `ingest --dry-run` only when the user asks for a preview without writing files.

### Import an authorized local HTML export

Use this when direct fetching is blocked, the user already saved the page, or the page must be handled through an authorized browser session:

```powershell
wechat-media-ingest import-html "<article.html>" `
  --source-url "<original mp.weixin.qq.com URL>" `
  --output "<archive root>"
```

The HTML file must be UTF-8 or UTF-8-SIG. Do not request, read, or store browser cookies. The command may still download allowlisted image and WeChat-native-video assets referenced by the HTML.

### Verify an archive

Always verify after a new or resumed ingest unless the command returned a verified idempotent rerun:

```powershell
wechat-media-ingest verify "<job or snapshot path>"
```

Require `ok: true`, `schema_valid: true`, no failed assets, and a complete job before reporting success. Report partial results as partial, not complete.

## Handle stop conditions

- Stop on `CAPTCHA`; do not retry aggressively. Offer `import-html` as the safe fallback.
- Report `DELETED`, `AUTH_REQUIRED`, `MEDIA_EXPIRED`, `NETWORK`, `PARSE_ERROR`, and `INTEGRITY` exactly as external or verification failures.
- Leave Tencent Video and WeChat Channels entries as `out_of_scope`.
- Do not change proxies, install root certificates, use MITM tooling, manage cookies, discover account history, or start parallel download workers.

## Report the result

Return:

- job status and exit meaning;
- job and snapshot paths;
- article title/account when available;
- complete, failed, and out-of-scope asset counts;
- verification result and Manifest path;
- the exact blocker and safe next action when incomplete.

Keep transcription, OCR, summarization, RAG, research, and publishing in separate downstream tools that consume `manifest.json`.
