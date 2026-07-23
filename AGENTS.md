# AGENTS.md

## Scope

This repository implements a standalone CLI for archiving public or authorized
WeChat article pages, images, and WeChat-native videos. It produces immutable
snapshots and a verifiable `manifest.json` contract.

## Hard boundaries

- Do not add account discovery, bulk account crawling, search, transcription,
  OCR, summarization, market analysis, publishing, or trading logic.
- Do not download Tencent Video or WeChat Channels content. Record it as
  `out_of_scope` when detected.
- Do not read/save login cookies or credentials, install root certificates,
  change system proxies, or use MITM tooling.
- Keep requests serial and low-frequency. A CAPTCHA stops the job.
- Validate allowed hosts and resolved IP addresses on redirects.
- Stream large files and hashes; never use whole-file `read_bytes()` for media.
- Tests must use synthetic fixtures or user-owned local samples; do not commit
  copyrighted article bodies, downloaded media, tokens, or private data.

## Validation

Run from the repository root:

```powershell
python -m pytest
python -m compileall -q src tests
python -m ruff check src tests
wechat-media-ingest doctor
python -m build --outdir dist
```
