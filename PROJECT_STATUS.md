# Project status

- Version: `0.1.0`
- Scope: single public/authorized WeChat article URL
- Commands: `doctor`, `inspect`, `ingest` (including `--dry-run`), `verify`
- Fetchers: guarded HTTP plus optional fresh Playwright browser fallback
- Assets: article HTML, Markdown, images, WeChat-native MP4
- Excluded: Tencent Video, WeChat Channels, account discovery, transcription,
  OCR, analysis, sending, publishing

## Validation status

See `docs/VALIDATION.md` for the exact test and live-sample evidence. The CLI is
released as an alpha because WeChat anti-bot behavior is external and can vary
by IP and time.
