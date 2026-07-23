# Project status

- Version: `0.2.0`
- Scope: one public/authorized WeChat article URL or authorized local HTML export
- Commands: `doctor`, `inspect`, `ingest` (including `--dry-run`), `import-html`, `verify`
- Fetchers: guarded HTTP plus optional fresh Playwright browser fallback
- Assets: article HTML, Markdown, images, WeChat-native MP4
- Contract: bundled Manifest JSON Schema `1.0` plus size and SHA-256 verification
- Integration: thin Codex Skill under `skills/wechat-media-ingest`
- Excluded: Tencent Video, WeChat Channels, account discovery, transcription,
  OCR, analysis, sending, publishing

## Validation status

See `docs/VALIDATION.md` for the exact test and live-sample evidence. The CLI remains
an alpha because WeChat anti-bot behavior is external and can vary by IP and time.
