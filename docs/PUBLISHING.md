# Publishing

## Continuous integration

`.github/workflows/ci.yml` tests Windows and Linux on Python 3.10-3.13, runs pytest, compileall, Ruff, builds a wheel, and performs a CLI smoke test.

## One-time PyPI setup

The release workflow uses OpenID Connect Trusted Publishing and intentionally stores no long-lived PyPI token.

Before pushing the first release tag:

1. Create or claim the `wechat-media-ingest` project on PyPI.
2. Add a Trusted Publisher for this GitHub repository.
3. Set the workflow filename to `release.yml` and environment name to `pypi`.
4. Create the `pypi` environment in the GitHub repository if deployment approval or protection rules are desired.
5. Set the repository variable `PYPI_PUBLISH_ENABLED` to `true`. Until then, tag pushes still create GitHub Releases and safely skip PyPI.

## Release procedure

1. Update the versions in `pyproject.toml` and `src/wechat_media_ingest/__init__.py`.
2. Update `CHANGELOG.md` and `PROJECT_STATUS.md`.
3. Run all commands from `AGENTS.md` plus a clean wheel-install smoke test.
4. Commit and push `main`.
5. Create and push a matching annotated tag, for example `v0.2.0`.

Pushing the tag builds the distributions once and creates a GitHub Release. It publishes the same files to PyPI only when `PYPI_PUBLISH_ENABLED=true`; otherwise the PyPI job is skipped.
