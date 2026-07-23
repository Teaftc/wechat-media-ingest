# Manifest contract (`schema_version: 1.0`)

Each snapshot contains `manifest.json`. Downstream consumers should depend on
this file and local asset paths, not on internal Python modules.

## Top-level fields

- `schema_version`: manifest schema version.
- `tool`: tool name and version.
- `job`: URL identity, job/snapshot IDs, fetch method, status, timestamps, and
  article-level error.
- `article`: title, account, publish time, and collection time.
- `assets`: one record per archived or detected asset.
- `summary`: counts by final asset status.

## Asset statuses

- `complete`: local file exists with recorded byte count and SHA-256.
- `skipped`: reserved for a deliberately skipped supported asset.
- `out_of_scope`: detected but intentionally unsupported media.
- `failed`: acquisition or validation failed; inspect `error`.

`manifest.json` and the append-only live log are not self-hashed. All archived
content files (`original.html`, `article.md`, images, and videos) are represented
as assets and verified by `wechat-media-ingest verify`.

## Identity

When `__biz`, `mid`, `idx`, and `sn` are present, they form the canonical
identity. Tracking parameters such as `chksm`, `scene`, sharing fields, and
`nwr_flag` are removed. Short or nonstandard links fall back to a normalized URL
hash until their final article URL is fetched.

## Reruns and snapshots

- A verified complete current snapshot is returned without network access.
- A partial current snapshot resumes missing media and `.part` downloads.
- Existing files with mismatched size/hash are never silently overwritten.
- `--force-new-snapshot` creates a new timestamped directory and preserves the
  previous snapshot.
