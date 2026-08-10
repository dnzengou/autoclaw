"""connectors/web_fetch.py — fetch URL, strip HTML, return text. Stdlib only.

Denies private-IP ranges + non-http(s) schemes via `agents/policies.yaml`
constraints (checked at the orchestrator layer before this is invoked).

Usage:
    from connectors.web_fetch import fetch
    r = fetch("https://example.com")
    print(r["text"][:500])
"""
from __future__ import annotations

import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse


USER_AGENT = "AutoclawAI/0.6 (private ai os; local; +https://autoclaw.dev)"


class _TextExtractor(HTMLParser):
    """Naive HTML→text. Skips <script>/<style>. Not a security boundary."""

    _SKIP = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._stack: list[str] = []
        self.out: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        self._stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        if any(t in self._SKIP for t in self._stack):
            return
        s = data.strip()
        if s:
            self.out.append(s)


def fetch(url: str, max_bytes: int = 200_000, timeout: int = 30) -> dict:
    """Fetch a URL, return {url, status, content_type, bytes, text}."""
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        return {"url": url, "error": f"scheme not allowed: {p.scheme}"}

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            content_type = r.headers.get("Content-Type", "")
            raw = r.read(max_bytes + 1)
            status = r.status
    except Exception as e:
        return {"url": url, "error": str(e)}

    truncated = len(raw) > max_bytes
    raw = raw[:max_bytes]

    text = ""
    charset = "utf-8"
    if "charset=" in content_type.lower():
        charset = content_type.split("charset=", 1)[1].split(";")[0].strip() or "utf-8"

    if "text/html" in content_type.lower():
        html = raw.decode(charset, errors="replace")
        ex = _TextExtractor()
        ex.feed(html)
        text = "\n".join(ex.out)
    elif content_type.startswith("text/") or "json" in content_type or "xml" in content_type:
        text = raw.decode(charset, errors="replace")
    else:
        text = f"(binary: {content_type}, {len(raw)} bytes)"

    return {
        "url": url,
        "status": status,
        "content_type": content_type,
        "bytes": len(raw),
        "truncated": truncated,
        "text": text,
    }
