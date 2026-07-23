# Manifest contract (`schema_version: 1.0`)

Each snapshot contains `manifest.json`. Downstream consumers should depend on
this file and local asset paths, not on internal Python modules. The canonical bundled
JSON Schema is `src/wechat_media_ingest/schemas/manifest-v1.schema.json`.

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
as assets. `wechat-media-ingest verify` first validates the Manifest against the
bundled Schema, rejects duplicate asset IDs and inconsistent summary counts, then
streams every complete file through size and SHA-256 verification.

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

## Compatibility

Schema `1.0` allows additional properties so compatible producers and consumers can add
metadata without breaking validation. Removing or changing required fields requires a new
Schema version. Downstream consumers should reject unsupported major Schema versions rather
than guessing.

`fetch_method: local_html` means the article page came from an authorized local export; it
does not mean that referenced media assets were embedded or downloaded offline.
