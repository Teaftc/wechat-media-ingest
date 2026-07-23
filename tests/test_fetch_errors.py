import pytest

from wechat_media_ingest.errors import ErrorCode, IngestError
from wechat_media_ingest.fetch.http import classify_page


def test_captcha_redirect_is_explicit_error():
    with pytest.raises(IngestError) as caught:
        classify_page("<html></html>", "https://mp.weixin.qq.com/mp/wappoc_appmsgcaptcha?token=x")
    assert caught.value.code == ErrorCode.CAPTCHA
