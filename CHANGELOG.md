# Changelog

All notable user-facing changes are documented here.

## 0.2.0 - 2026-07-23

### Added

- `import-html` for authorized UTF-8/UTF-8-SIG local WeChat page exports.
- Bundled Manifest JSON Schema and structural validation during `verify`.
- Synthetic regression fixtures for text-only, lazy-image, native-video, deleted, and CAPTCHA pages.
- A thin Codex Skill that wraps the CLI without duplicating ingest logic.
- Windows/Linux CI for Python 3.10 through 3.13.
- Tag-driven GitHub Release and PyPI Trusted Publishing workflow.

### Changed

- `verify` now reports `schema_version` and `schema_valid`, rejects duplicate asset IDs, and checks summary counts.

## 0.1.0 - 2026-07-23

- Initial public release with guarded URL ingest, Markdown/images/native-video snapshots, resumable downloads, manifests, and integrity verification.
