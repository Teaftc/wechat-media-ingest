from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

from .errors import ErrorCode, IngestError

ARTICLE_HOSTS = {"mp.weixin.qq.com"}
IMAGE_HOSTS = {"mmbiz.qpic.cn", "mmbiz.qlogo.cn"}
VIDEO_HOSTS = {"mpvideo.qpic.cn"}


def _is_forbidden_ip(text: str) -> bool:
    ip = ipaddress.ip_address(text)
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_public_url(url: str, allowed_hosts: set[str]) -> str:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"}:
        raise IngestError(ErrorCode.UNSUPPORTED, f"unsupported URL scheme: {parts.scheme}")
    if parts.username or parts.password:
        raise IngestError(ErrorCode.UNSUPPORTED, "credentials in URLs are not allowed")
    host = (parts.hostname or "").lower().rstrip(".")
    if host not in allowed_hosts:
        raise IngestError(ErrorCode.UNSUPPORTED, f"host is not allowlisted: {host or '<missing>'}")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, parts.port or 443, type=socket.SOCK_STREAM)}
    except OSError as exc:
        raise IngestError(ErrorCode.NETWORK, f"DNS resolution failed for {host}: {exc}") from exc
    if not addresses:
        raise IngestError(ErrorCode.NETWORK, f"DNS returned no addresses for {host}")
    forbidden = [address for address in addresses if _is_forbidden_ip(address)]
    if forbidden:
        raise IngestError(ErrorCode.UNSUPPORTED, f"host resolved to forbidden address: {forbidden[0]}")
    return url


def redirect_target(current_url: str, location: str, allowed_hosts: set[str]) -> str:
    target = urljoin(current_url, location)
    return validate_public_url(target, allowed_hosts)
