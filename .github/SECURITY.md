# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ active |
| < 0.1.0 | ❌        |

## Reporting a vulnerability

**Please do not open a public issue for security findings.**

Email **security@desiredsolutions.space** with:

1. A description of the issue and its impact.
2. Steps to reproduce, ideally with a minimal proof-of-concept.
3. Affected version(s) — release tag or commit SHA.
4. Your name / handle for credit (optional).

You'll get an acknowledgement within **72 hours** and a fix or mitigation plan within **14 days** for confirmed issues.

Once a fix is shipped:

- A CVE is requested for issues rated medium or higher.
- A GitHub Security Advisory is published with credit.
- A patched release is tagged + the previous version is yanked from package managers if exploitable.

## Scope

In scope:
- The Rust core (`src/`), Go agent (`agent.go`), Python agent (`agent.py`)
- All three SDKs (`sdk/python`, `sdk/js`, `sdk/go`)
- Mobile shell (`mobile/`) and its Tauri configuration
- The Docker image (`ghcr.io/dnzengou/autoclaw:*`)
- Install scripts (`install.sh`, `install.ps1`)
- The landing site (`site/`) and its CSP / form handling

Out of scope:
- Issues in upstream dependencies (report to the dep's maintainers first)
- Self-inflicted exposure (e.g. running the server on `0.0.0.0` without a firewall)
- LLM provider issues (report to Anthropic / OpenAI / DeepSeek directly)

## Hall of fame

Reporters who follow this process get a permanent shout-out in [CHANGELOG.md](../CHANGELOG.md).
