"""connectors/email_imap.py — read-only IMAP inbox access. Stdlib only.

Env:
    EMAIL_HOST, EMAIL_PORT (default 993), EMAIL_USER, EMAIL_PASSWORD
    EMAIL_MAILBOX (default INBOX)
    EMAIL_USE_SSL (default True — set to '0' to use STARTTLS)
"""
from __future__ import annotations

import email
import imaplib
import os
from email.header import decode_header
from typing import Iterable

HOST = os.environ.get("EMAIL_HOST")
PORT = int(os.environ.get("EMAIL_PORT", "993"))
USER = os.environ.get("EMAIL_USER")
PASSWORD = os.environ.get("EMAIL_PASSWORD")
MAILBOX = os.environ.get("EMAIL_MAILBOX", "INBOX")
USE_SSL = os.environ.get("EMAIL_USE_SSL", "1") != "0"


def _connect() -> imaplib.IMAP4:
    if not (HOST and USER and PASSWORD):
        raise RuntimeError("Set EMAIL_HOST, EMAIL_USER, EMAIL_PASSWORD env vars first.")
    if USE_SSL:
        m = imaplib.IMAP4_SSL(HOST, PORT)
    else:
        m = imaplib.IMAP4(HOST, PORT)
        m.starttls()
    m.login(USER, PASSWORD)
    m.select(MAILBOX, readonly=True)
    return m


def _decode(hdr: str) -> str:
    if not hdr:
        return ""
    parts = decode_header(hdr)
    out = []
    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            out.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(chunk)
    return "".join(out)


def list_inbox(limit: int = 20) -> list[dict]:
    """Return the last `limit` messages as {uid, from, subject, date}."""
    m = _connect()
    try:
        typ, data = m.search(None, "ALL")
        if typ != "OK":
            return []
        uids = data[0].split()[-limit:][::-1]
        out = []
        for uid in uids:
            typ, msg_data = m.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1] if isinstance(msg_data[0], tuple) else msg_data[0]
            msg = email.message_from_bytes(raw)
            out.append({
                "uid": int(uid),
                "from": _decode(msg.get("From", "")),
                "subject": _decode(msg.get("Subject", "")),
                "date": msg.get("Date", ""),
            })
        return out
    finally:
        # SELECTed mailbox may not have been established — ignore CLOSE errors.
        try:
            m.close()
        except Exception:
            pass
        m.logout()


def get_message(uid: int) -> dict:
    """Return one message: {uid, from, to, subject, date, body}."""
    m = _connect()
    try:
        typ, msg_data = m.fetch(str(uid).encode(), "(RFC822)")
        if typ != "OK" or not msg_data or not msg_data[0]:
            return {"uid": uid, "error": "not found"}
        raw = msg_data[0][1] if isinstance(msg_data[0], tuple) else msg_data[0]
        msg = email.message_from_bytes(raw)
        body = _extract_body(msg)
        return {
            "uid": uid,
            "from": _decode(msg.get("From", "")),
            "to": _decode(msg.get("To", "")),
            "subject": _decode(msg.get("Subject", "")),
            "date": msg.get("Date", ""),
            "body": body[:20000],  # cap
        }
    finally:
        # SELECTed mailbox may not have been established — ignore CLOSE errors.
        try:
            m.close()
        except Exception:
            pass
        m.logout()


def _extract_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        # Prefer text/plain
        for part in _walk(msg):
            if part.get_content_type() == "text/plain":
                return _payload_to_str(part)
        for part in _walk(msg):
            if part.get_content_type() == "text/html":
                return _strip_html(_payload_to_str(part))
        return ""
    return _payload_to_str(msg)


def _walk(msg: email.message.Message) -> Iterable[email.message.Message]:
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        if part.get("Content-Disposition", "").startswith("attachment"):
            continue
        yield part


def _payload_to_str(part: email.message.Message) -> str:
    payload = part.get_payload(decode=True) or b""
    charset = part.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def _strip_html(html: str) -> str:
    # Naive strip — good enough for readable summarization; not a security boundary.
    from html.parser import HTMLParser

    class _S(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.out: list[str] = []
        def handle_data(self, data: str) -> None:
            self.out.append(data)

    p = _S()
    p.feed(html)
    return "\n".join(t.strip() for t in p.out if t.strip())
