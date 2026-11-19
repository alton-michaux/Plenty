"""Fetch a recipe page someone shared, without letting a URL reach into our own network.

Only http(s) on standard ports, only public IP addresses (checked on every redirect hop), with
size and time limits. Note: the address is checked before connecting, so a DNS answer that
changes between the check and the connect (rebinding) isn't covered; fine for a personal app.
"""

import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx2

MAX_BYTES = 3 * 1024 * 1024
TIMEOUT = httpx2.Timeout(10.0, connect=5.0)
MAX_REDIRECTS = 5
UA = "Mozilla/5.0 (Linux; Android 15; Pixel) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140 Mobile Safari/537.36"  # noqa: E501


class FetchError(Exception):
    """A message safe to show the user."""


def _check_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError("That doesn't look like a web link.")
    if parts.port not in (None, 80, 443):
        raise FetchError("That link uses an unusual port.")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise FetchError("Couldn't find that website.") from None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise FetchError("That link points somewhere private.")


def fetch_html(url: str) -> tuple[str, str]:
    """Return (final_url, html). Raises FetchError with a user-facing message."""
    with httpx2.Client(timeout=TIMEOUT, headers={"User-Agent": UA}) as client:
        for _ in range(MAX_REDIRECTS + 1):
            _check_url(url)
            try:
                with client.stream("GET", url, follow_redirects=False) as r:
                    if r.is_redirect and "location" in r.headers:
                        url = urljoin(url, r.headers["location"])
                        continue
                    if r.status_code >= 400:
                        raise FetchError(f"The site answered with an error ({r.status_code}).")
                    ctype = r.headers.get("content-type", "")
                    if "html" not in ctype and "xml" not in ctype:
                        raise FetchError("That link isn't a web page.")
                    body = bytearray()
                    for chunk in r.iter_bytes():
                        body += chunk
                        if len(body) > MAX_BYTES:
                            break
                    return str(r.url), bytes(body).decode(r.encoding or "utf-8", "replace")
            except httpx2.HTTPError:
                raise FetchError("Couldn't load that page.") from None
    raise FetchError("That link redirects too many times.")
