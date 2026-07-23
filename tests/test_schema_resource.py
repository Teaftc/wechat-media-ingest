from importlib.resources import files

from wechat_media_ingest.schema import manifest_validator


def test_manifest_schema_is_bundled():
    schema = files("wechat_media_ingest.schemas").joinpath("manifest-v1.schema.json")
    assert schema.is_file()
    assert manifest_validator().schema["properties"]["schema_version"]["const"] == "1.0"
