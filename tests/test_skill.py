from pathlib import Path


def test_bundled_skill_is_thin_and_complete():
    skill_root = Path(__file__).parents[1] / "skills" / "wechat-media-ingest"
    text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    metadata = (skill_root / "agents" / "openai.yaml").read_text(encoding="utf-8")

    assert text.startswith("---\nname: wechat-media-ingest\n")
    assert "wechat-media-ingest import-html" in text
    assert "Do not duplicate" in text
    assert "TODO" not in text
    assert "$wechat-media-ingest" in metadata
