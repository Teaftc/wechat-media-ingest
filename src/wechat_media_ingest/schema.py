from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator


@lru_cache(maxsize=1)
def manifest_validator() -> Draft202012Validator:
    schema_path = files("wechat_media_ingest.schemas").joinpath("manifest-v1.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8-sig"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_manifest(manifest: dict[str, Any]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    for error in sorted(manifest_validator().iter_errors(manifest), key=lambda item: list(item.absolute_path)):
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        failures.append({"path": location, "message": error.message})
    return failures
