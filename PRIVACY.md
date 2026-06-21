# Privacy Policy — Autoclaw

> **Last updated:** 2026-06-18
> **Effective for:** Autoclaw v0.1.0 and later (CLI, server, SDKs, mobile apps, desktop apps, landing site)
> **Maintained by:** [Desired Solutions](https://desiredsolutions.space) — hello@desiredsolutions.space

This is the single privacy policy covering every Autoclaw distribution: the open-source CLI/server, the Python/JS/Go SDKs, the Android APK (sideload and Play Store), the iOS build, the desktop apps (macOS/Windows/Linux), and the landing site at autoclaw.dev.

---

## TL;DR

- We collect **nothing**.
- API keys you set never leave your own server / device.
- The mobile app talks only to a server **you** configure.
- The landing site uses Plausible — cookieless, no personal data, EU-hosted.
- All install scripts verify SHA256 before exec.
- MIT license — audit the source: <https://github.com/dnzengou/autoclaw>.

---

## 1. What we collect

### 1.1 The Autoclaw server (self-hosted by you)

- **Experiment results** — written to `results.json` and committed to your own git repo. We never see them.
- **Context.md** — your goals, hypotheses, learnings. Written to your filesystem. We never see it.
- **LLM API keys** — read from environment variables. Sent only to your chosen LLM provider (Anthropic, OpenAI, DeepSeek). Never logged, never persisted, never transmitted to us.
- **Outbound network requests** — only to the LLM endpoint you configured. No telemetry.

### 1.2 The SDKs (Python, JavaScript, Go)

- Stateless HTTP/WS clients. They talk only to the server URL you pass in. No outbound calls of their own.

### 1.3 The mobile app (Android APK, iOS IPA)

- **Server URL** — stored in app-private storage (Android Keystore / iOS Keychain). Never transmitted anywhere except as the target of your own API calls.
- **In-app preferences** (theme, default tab) — stored locally only.
- **No analytics SDKs**, no crash reporters, no advertising IDs, no device fingerprinting.
- **Permissions requested:** `INTERNET`, `ACCESS_NETWORK_STATE`, `WAKE_LOCK` (only while a live-stream tab is foregrounded). That's it.

### 1.4 The desktop apps (Tauri shells for macOS / Windows / Linux)

- Same as mobile: only the server URL is stored, only outbound to that server.

### 1.5 The landing site (autoclaw.dev)

- **Plausible analytics** — page views and outbound link clicks, **cookieless**, no IP storage, no cross-site tracking. EU-hosted (plausible.io). Privacy info: <https://plausible.io/data-policy>.
- **Web3Forms waitlist** — when you submit your email, it is sent to <https://api.web3forms.com> for delivery to our inbox. Web3Forms's policy: <https://web3forms.com/privacy>. We use the submission solely to email you about Autoclaw Pro availability. We do not share it.
- **No cookies.** No localStorage tracking. No third-party scripts beyond Plausible and Web3Forms.

---

## 2. What we do NOT collect

- ❌ Names, emails, addresses (except the waitlist email you explicitly submit)
- ❌ Device identifiers, advertising IDs, fingerprints
- ❌ Location data
- ❌ Contacts, calendar, photos, files
- ❌ Microphone, camera, sensor data
- ❌ Browsing history outside autoclaw.dev
- ❌ Payment information (we don't accept payment yet)
- ❌ Health, financial, or biometric data
- ❌ Anything not listed in section 1

---

## 3. Third parties

We use exactly three third-party services and only for the purposes listed:

| Service | What for | Data sent | Policy |
|---|---|---|---|
| **Plausible Analytics** | Aggregate page-view counts on autoclaw.dev | Page URL, referrer, user agent (no IP stored, no cookies) | <https://plausible.io/data-policy> |
| **Web3Forms** | Deliver waitlist signups to our inbox | The email you typed into the waitlist form | <https://web3forms.com/privacy> |
| **GitHub** | Source-code hosting, releases, container registry, issue tracker | Public data only (commits, releases, issues you file) | <https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement> |

If you bring your own LLM key (Anthropic, OpenAI, DeepSeek), those providers' policies apply to your usage of them — independent of Autoclaw.

---

## 4. Where data lives

- **Your experiment data** lives on your hardware (or whatever VPS / cloud you ran the server on). We have no copy.
- **Your context.md** lives in your git repo. We have no copy.
- **Your LLM API key** lives in your environment. We have no copy.
- **Your waitlist email** (if you submitted one) lives in the Desired Solutions inbox + Web3Forms's transient delivery queue.
- **Plausible analytics** for autoclaw.dev are stored in the EU by Plausible Insights OÜ.

---

## 5. How long we keep things

- **Waitlist emails:** until you ask us to delete them, or 24 months after the final Pro launch announcement, whichever comes first.
- **Plausible analytics:** Plausible's default retention (24 months at the time of writing — check their policy for current value).
- **Everything else:** N/A — we don't collect it.

---

## 6. Your rights (GDPR / CCPA / etc.)

You can, at any time, email **hello@desiredsolutions.space** to:

- See what we have on you (almost certainly only your waitlist email, if any)
- Delete what we have on you
- Export what we have on you (JSON / CSV / however you'd like)
- Object to any processing
- Withdraw consent

We will respond within 30 days. No fees, no forms, no friction.

You also have the right to lodge a complaint with your local data protection authority (in the EU, find yours here: <https://edpb.europa.eu/about-edpb/board/members_en>).

---

## 7. Children

Autoclaw is a developer tool aimed at users 18 and over. We do not knowingly collect data from anyone under 13 (US COPPA) or under 16 (EU GDPR). If you believe a child has submitted data to us, email hello@desiredsolutions.space and we will delete it.

The mobile app's Play Store target audience is 18+.

---

## 8. Security

- All distribution channels (install.sh, install.ps1, APKs, .deb, GHCR images) are SHA256-checksummed by CI. The install scripts verify and refuse to install on mismatch.
- The Android APK is signed with a stable release key — same key across versions guarantees update integrity.
- The server's dashboard CSP allows scripts only from `'self'` plus Plausible. The Tauri mobile shell's `connect-src` is locked to your configured server URL.
- We follow [Responsible Disclosure](https://github.com/dnzengou/autoclaw/security/policy) for security issues — please email **security@desiredsolutions.space** with anything sensitive; we'll acknowledge within 72 hours.

---

## 9. Changes to this policy

Material changes are announced via:

1. A commit to <https://github.com/dnzengou/autoclaw/blob/main/PRIVACY.md> with the new effective date.
2. A banner on autoclaw.dev for 30 days.
3. An email to anyone on the waitlist if the change affects waitlist data.

The version of this policy in effect when you used the service is the one in `PRIVACY.md` at the corresponding git commit. Older versions remain accessible in the repo's history.

---

## 10. Contact

- **General privacy questions:** hello@desiredsolutions.space
- **Security disclosures:** security@desiredsolutions.space
- **Legal entity:** Desired Solutions (<https://desiredsolutions.space>)
- **Source repo:** <https://github.com/dnzengou/autoclaw>

This policy is also published at <https://autoclaw.dev/privacy> for Play Store / App Store linkability.
