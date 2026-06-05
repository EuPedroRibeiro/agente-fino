from __future__ import annotations

import ipaddress
import socket
import urllib.parse
import urllib.request
from dataclasses import dataclass

from app.core.config import settings


BLOCKED_SCHEMES = {"file", "ftp"}
MAX_PAGE_BYTES = 1_200_000


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    content_type: str
    text: str
    fetched_at: str


def _is_blocked_host(hostname: str) -> bool:
    clean = hostname.lower().strip("[]")
    if clean in {"localhost", "0.0.0.0"}:
        return True
    try:
        addresses = [ipaddress.ip_address(clean)]
    except ValueError:
        try:
            addresses = [ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(clean, None)]
        except OSError:
            return True
    for address in addresses:
        if address.is_loopback or address.is_private or address.is_link_local or address.is_multicast or address.is_reserved:
            return True
    return False


def assert_url_safe(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() in BLOCKED_SCHEMES or parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("URL bloqueada: esquema nao permitido.")
    if not parsed.hostname or _is_blocked_host(parsed.hostname):
        raise ValueError("URL bloqueada por protecao SSRF.")


def fetch_page(url: str) -> FetchResult:
    from datetime import datetime

    assert_url_safe(url)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": settings.web_user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
        },
    )
    with urllib.request.urlopen(request, timeout=settings.web_timeout) as response:
        final_url = response.geturl()
        assert_url_safe(final_url)
        content_type = response.headers.get("Content-Type", "")
        raw = response.read(MAX_PAGE_BYTES + 1)
        if len(raw) > MAX_PAGE_BYTES:
            raw = raw[:MAX_PAGE_BYTES]
        encoding = response.headers.get_content_charset() or "utf-8"
        text = raw.decode(encoding, errors="replace")
        status_code = getattr(response, "status", 200)
    return FetchResult(
        url=url,
        final_url=final_url,
        status_code=status_code,
        content_type=content_type,
        text=text,
        fetched_at=datetime.now().astimezone().isoformat(timespec="seconds"),
    )
