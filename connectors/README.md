# Connectors — enterprise integrations (Layer 5)

Currently ships two: **email (IMAP read-only)** and **web fetch**. GitHub is
implemented via the `gh` CLI directly in `agents/tools.py` so no auth wiring
here.

More connectors (Microsoft Graph, Google Workspace, Salesforce, SAP,
SharePoint) are planned but require OAuth flows we're deferring to the
enterprise SKU — the community edition proves the pattern with local IMAP + web
+ files + github.

## Files

- `email_imap.py` — list inbox, fetch message body/headers, no `SEND` verb. Uses stdlib `imaplib`.
- `web_fetch.py` — fetch a URL, strip HTML tags, return plain text. Uses stdlib `urllib` + a naive HTML→text parser. No external deps.

## Configuration

Email requires 4 env vars (or set them in `.env`):

```bash
export EMAIL_HOST=imap.gmail.com
export EMAIL_PORT=993
export EMAIL_USER=you@example.com
export EMAIL_PASSWORD=app_password           # never your regular password
# Optional
export EMAIL_MAILBOX=INBOX
```

For Gmail: create an **App Password** (not your account password) at
https://myaccount.google.com/apppasswords.

For Outlook/Microsoft 365: enable IMAP and use an app password.

## Security

- **Passwords never touch the LLM.** The IMAP client authenticates locally and
  returns opaque message data.
- **web_fetch denies private-IP ranges** via `agents/policies.yaml` — no
  SSRF path to your internal network.
- **Audit log** captures every fetch (URL hash, response size).

## Roadmap

- Microsoft Graph (Outlook, Teams, SharePoint, OneDrive)
- Google Workspace (Gmail, Calendar, Drive)
- Slack (webhooks + Web API)
- Salesforce (REST)
- Local files as a first-class connector (currently handled by `rag/ingest.py`)
