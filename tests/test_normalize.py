import pytest

from wechat_media_ingest.errors import ErrorCode, IngestError
from wechat_media_ingest.normalize import identify_article, safe_component


def test_tracking_variants_share_job_id():
    base = "https://mp.weixin.qq.com/s?__biz=abc%3D%3D&mid=123&idx=1&sn=deadbeef"
    first = identify_article(base + "&chksm=aaa&scene=21#wechat_redirect")
    second = identify_article(base + "&from=timeline&nwr_flag=1")
    assert first.job_id == second.job_id
    assert first.canonical_url == second.canonical_url
    assert "scene=" not in first.canonical_url


def test_url_hash_fallback_is_stable():
    first = identify_article("https://mp.weixin.qq.com/s/short?scene=1")
    second = identify_article("https://mp.weixin.qq.com/s/short?scene=99")
    assert first.method == "url_hash"
    assert first.job_id == second.job_id


def test_windows_reserved_component_is_safe():
    assert safe_component("CON") == "_CON"
    assert safe_component('bad:name?') == "bad_name_"


def test_article_url_rejects_embedded_credentials():
    with pytest.raises(IngestError) as caught:
        identify_article("https://user:secret@mp.weixin.qq.com/s/example")
    assert caught.value.code == ErrorCode.UNSUPPORTED
