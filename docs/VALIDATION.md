# Validation record

Date: 2026-07-23 (Asia/Shanghai)

## Stage 0 sample survey

Six low-frequency serial HTTP checks were made against three ordinary public
articles and three WeChat-native-video articles selected from two existing,
authorized local project corpora. Every request was redirected to WeChat's
`/mp/wappoc_appmsgcaptcha` page. One subsequent Playwright browser check also
returned the explicit `CAPTCHA` error. Testing against live article pages then
stopped; no proxy, root certificate, login cookie, credential, or MITM tool was
used.

Conclusion:

- native-video demand is real: the authorized local corpus already contains 238
  previously archived `wxv_...` article videos with hashes and completed
  downstream processing;
- plain HTTP and a fresh browser session cannot be treated as universally
  reliable from the current IP;
- CAPTCHA is an explicit stop condition, not a reason to retry aggressively;
- offline parser fixtures and archived authorized pages are necessary for
  deterministic regression testing.

## Release verification

The release candidate was checked with Python 3.12.13 on Windows:

```text
pytest:                 26 passed
compileall src tests:   passed
ruff check src tests:   passed
doctor:                 ok=true, version=0.2.0
Manifest Schema:         bundled in wheel and validated
Codex Skill:             quick_validate passed
Offline import smoke:    complete; verify ok=true; schema_valid=true
Wheel install smoke:     version=0.2.0; doctor ok=true
Playwright Chromium:    available
FFmpeg / ffprobe:       not on PATH (optional)
```

The exact core commands are:

```powershell
python -m pytest -q
python -m compileall -q src tests
ruff check src tests
wechat-media-ingest doctor
python -m build --outdir dist
```

The built `0.2.0` wheel was installed into a fresh temporary virtual environment.
The installed CLI reported version `0.2.0`, `doctor` returned `ok=true`, and the wheel
contained `schema.py` plus `schemas/manifest-v1.schema.json`.

The repository Skill was validated with the Codex `skill-creator` `quick_validate.py`
helper under UTF-8 mode.

## Authorized local HTML import

A synthetic text-only WeChat fixture was passed through the real CLI without monkeypatching:

```powershell
wechat-media-ingest import-html tests\fixtures\article_text_only.html `
  --source-url "https://mp.weixin.qq.com/s?__biz=..." `
  --output .local-output\offline-smoke-<timestamp>
wechat-media-ingest verify <generated-job-directory>
```

The job completed with two complete assets (`original.html` and `article.md`). Verification
returned `ok=true`, `schema_valid=true`, two checked files, and no failures. This test made no
article-page network request.

## Authorized local-material replay

No copied article body or downloaded media is committed to this repository. A
separate, authorized local replay produced these results:

| Check | Result |
|---|---|
| Archived HTML parse | 2,531 Markdown characters, 3 images, 1 native video |
| Native-video identity | `wxv_4599515870535843846` |
| Available MP4 transcodes | 4 |
| Smallest transcode metadata | 480x360, 6,990,985 bytes |
| Real CDN image download | 416,454 bytes |
| Image SHA-256 | `ed904df4f2fe8874e8d5755478ed0de990867d325d4abba4debb6664f7fb8ae7` |
| Existing real video verification | 32,294,536 bytes, size and SHA-256 passed |
| Video SHA-256 | `000b81b391d4db7f4595b8c3bf045356dd1d95663cc7b984f8593f72840727f7` |

The real video verification used streaming SHA-256 through the same manifest
verifier shipped by the CLI. The downloaded image and video remain outside Git.

## Epistemic boundary

Passing local tests verifies normalization, parsing, manifest generation,
streaming downloads and hashes, idempotent reruns, forced-snapshot isolation,
and corruption detection. It cannot promise that WeChat will serve every
article at every time or from every IP. The CLI reports external failures rather
than hiding them.
