# Autoclaw — Google Play Store Publication Guide

> Everything needed to take the Tauri-built APK from `gen/android/app/build/outputs/` to a published Play Store listing.

This is a working checklist, not theory. Each section is something Google will check or block on.

---

## 0. Pre-flight

- [ ] Google Play Console account ($25 one-time, lifetime) — <https://play.google.com/console>
- [ ] Developer name set, payment profile complete (even for free apps)
- [ ] D-U-N-S number registered if publishing as a business (free, takes 30 days; required for orgs since Sep 2023)
- [ ] **Closed test track** ran for ≥14 days with ≥12 testers (required for production publish since Nov 2023 for new developer accounts)

---

## 1. Build a signed Android App Bundle (.aab)

The Play Store accepts `.aab` (recommended) and `.apk` (legacy). Use AAB — smaller downloads, per-device APK splits, mandatory for new apps.

### 1.1 Generate an upload keystore (one-time)

```bash
keytool -genkey -v \
  -keystore autoclaw-upload.keystore \
  -alias autoclaw \
  -keyalg RSA -keysize 4096 -validity 10000
```

Answer the prompts honestly. Store this file in a password manager — losing it means losing the ability to update the app under the same listing.

### 1.2 Wire the keystore into Tauri

Create `mobile/gen/android/keystore.properties`:

```properties
storeFile=../../../autoclaw-upload.keystore
storePassword=********
keyAlias=autoclaw
keyPassword=********
```

Add to `mobile/.gitignore`:
```
keystore.properties
*.keystore
*.jks
```

### 1.3 Build the AAB

```bash
cd mobile
cargo tauri android build --aab
# Output: gen/android/app/build/outputs/bundle/universalRelease/app-universal-release.aab
```

To verify the signature:
```bash
jarsigner -verify -verbose -certs app-universal-release.aab
```

---

## 2. Listing copy (paste into Play Console)

### App title (max 30 chars)
```
Autoclaw — AI Loop
```

### Short description (max 80 chars)
```
Self-improving AI experiments. Set a goal, AI iterates, git tracks every change.
```

### Full description (max 4000 chars)
```
Autoclaw is the mobile dashboard for a self-improving AI experiment loop. You set the goal in plain markdown. The AI proposes hypotheses, runs experiments under a time budget, scores each one against your rubric, commits improvements to git, and reverts regressions. Indefinitely.

This app connects to an Autoclaw server you control — on your laptop, a cloud VM, or any container host. Watch experiments stream in live, edit your context from anywhere, jump to your best run with one tap.

★ FEATURES
- Live experiment stream via SSE — see scores land in real time
- One-tap start / stop / reset of the loop
- Edit context.md directly from your phone
- Best-run shortcut + score history chart
- Works against any Autoclaw server (local, VPS, Fly.io, Railway, Render)
- Dark-mode native
- No account, no telemetry, no in-app purchases

★ THIS APP NEEDS A SERVER
You need an Autoclaw server reachable from your phone. Install one on your laptop or any VPS in 30 seconds:

  pip install autoclaw   # then: autoclaw run
  curl -fsSL autoclaw.dev/install.sh | sh
  docker run -p 8080:8080 ghcr.io/dnzengou/autoclaw:latest

★ PRIVACY
The app stores only your server URL locally. No analytics, no third-party SDKs. LLM API keys live on YOUR server — the app never sees them. Full policy: autoclaw.dev/privacy

★ OPEN SOURCE
Apache MIT licensed. github.com/dnzengou/autoclaw

★ FOR WHO
Data scientists tuning models. ML engineers chasing perf. Prompt engineers iterating on LLM tasks. Anyone with a metric to push and patience to let an AI do the boring iteration.
```

### What's new (per release, max 500 chars)
```
v0.1.0 — Initial Play Store release.
- Native Android shell around the Autoclaw dashboard
- Live SSE experiment stream
- Context editor + best-run shortcut
- Dark mode default
- Works against any self-hosted Autoclaw server
```

### Tags / category
- **Category:** Tools (primary) · Productivity (secondary)
- **Tags:** developer-tools, automation, ai, machine-learning, dashboard

---

## 3. Graphic assets

Google rejects listings missing any of these. Sizes are exact, not minimum.

| Asset | Size | Format | Required |
|---|---|---|---|
| App icon | 512 × 512 | PNG (32-bit, non-transparent) | ✅ |
| Feature graphic | 1024 × 500 | PNG / JPG | ✅ |
| Phone screenshots | 1080 × 1920 (or 9:16 of any size 320–3840) | PNG / JPG | ✅ min 2, max 8 |
| 7" tablet screenshots | 1200 × 1920 | PNG / JPG | optional but recommended |
| 10" tablet screenshots | 1920 × 1200 | PNG / JPG | optional but recommended |
| Promo video | YouTube URL, 30s–2min | n/a | optional |

**Asset directory layout (commit these to `mobile/store-assets/`):**

```
mobile/store-assets/
├── icon-512.png
├── feature-1024x500.png
├── screenshots/
│   ├── phone-01-dashboard.png
│   ├── phone-02-experiments-list.png
│   ├── phone-03-live-stream.png
│   ├── phone-04-context-editor.png
│   ├── phone-05-best-run-detail.png
│   ├── phone-06-dark-mode.png
│   ├── tablet7-01-dashboard.png
│   └── tablet10-01-dashboard.png
└── promo-text.md
```

Generate screenshots from the Tauri Android dev build:
```bash
cargo tauri android dev
# Use Android Studio's screenshot tool: View → Tool Windows → Logcat → camera icon
# Or: adb shell screencap -p /sdcard/01.png && adb pull /sdcard/01.png
```

---

## 4. Content rating

In the Play Console, fill out the IARC questionnaire honestly. For Autoclaw the rating will land at **PEGI 3 / ESRB Everyone / IARC 3+** because:

- No user-generated content shown to other users
- No violence, sexual content, gambling, drugs
- No location sharing, no purchases, no ads
- No social interaction features

Save the rating certificate it generates — Google's review needs the reference number.

---

## 5. Data safety form

Required since 2022. Be honest — false declarations get the listing pulled.

| Data type | Collected? | Shared? | Encrypted in transit? | Optional? |
|---|---|---|---|---|
| Personal info | ❌ No | — | — | — |
| Financial info | ❌ No | — | — | — |
| Health & fitness | ❌ No | — | — | — |
| Messages | ❌ No | — | — | — |
| Photos / videos | ❌ No | — | — | — |
| Audio | ❌ No | — | — | — |
| Files & docs | ❌ No | — | — | — |
| Calendar / contacts | ❌ No | — | — | — |
| App activity | ❌ No | — | — | — |
| Web browsing | ❌ No | — | — | — |
| App info / performance | ❌ No | — | — | — |
| Device or other IDs | ❌ No | — | — | — |

**Security practices:**
- ✅ Data encrypted in transit (your server URL, if HTTPS)
- ✅ You can request data deletion (just uninstall — nothing to delete)
- ✅ Independent security review: not required, not done
- ✅ Committed to Play Families Policy: N/A (not aimed at children)

**Reference link in the form:** point to [PRIVACY.md](../PRIVACY.md) hosted at `https://autoclaw.dev/privacy`.

---

## 6. Target audience & content

- **Target age:** 18+ (developer tool)
- **Appeals to children?** No
- **Ads?** No
- **In-app purchases?** No
- **Government app?** No

---

## 7. App access

Some features require a server — explain to reviewers how to test:

```
TESTER LOGIN (for Google reviewers):

This app is a client for a self-hosted server. To test the full experience,
point the app at our public demo server (read-only):

  Settings → Server URL → https://demo.autoclaw.dev

The demo runs an idle loop with 50 sample experiments preloaded. No login
required. All app features (dashboard, experiments list, context editor in
read-only mode, best-run detail, dark mode) are functional against this URL.

For full read-write testing, set up your own server in 30 seconds:
  docker run -p 8080:8080 ghcr.io/dnzengou/autoclaw:latest
```

Provide this in the Play Console's **App access** section.

---

## 8. Closed test → Production

Google now requires every new app to:

1. Run a **closed test** for ≥14 continuous days
2. Recruit ≥12 testers who **opt in** via a tester group link
3. Only then can you promote to **open test** or **production**

### Closed test setup

```
Play Console → Testing → Closed testing → Create track → "early-access"
  - Upload AAB
  - Add tester emails (12+, real humans)
  - Or: create a Google Group (e.g. autoclaw-testers@googlegroups.com)
  - Send the opt-in URL: https://play.google.com/apps/testing/dev.autoclaw.mobile
  - Wait 14 days
```

Recruit via:
- Twitter / Mastodon launch tweet
- The waitlist signups from autoclaw.dev (Web3Forms)
- Sibling product (Clow.studio) audience cross-post
- /r/MachineLearning, /r/LocalLLaMA, Hacker News Show HN

### Production rollout

After 14 days + 12 testers:
- Play Console → Production → Create release
- Upload the same AAB (or newer version)
- Fill in country availability (start global, restrict only if needed)
- Submit for review (1–7 day turnaround usually)

---

## 9. Post-publish maintenance

| Cadence | Task |
|---|---|
| Per release | Bump `versionCode` (integer) and `versionName` (semver) in `mobile/tauri.conf.json` |
| Per release | Update **What's new** in Play Console |
| Quarterly | Refresh screenshots if the UI changed |
| Annually | Re-attest the Data Safety form |
| As needed | Respond to reviews within 7 days (Google ranks responsiveness) |
| As needed | Push hotfixes via staged rollout (1% → 10% → 50% → 100%) |

---

## 10. Common rejection reasons & how to avoid

| Reason | Fix |
|---|---|
| Broken intent / crash on launch | Test on a real device, not just emulator. Use `adb logcat` to catch startup exceptions. |
| Missing privacy policy URL | Set it in **Store presence → Privacy Policy** to `https://autoclaw.dev/privacy` |
| Misleading screenshots | Screenshots must show the actual app, not mockups or branding overlays |
| Unattributed open source | We're MIT-licensed; cite in the listing footer and in-app About screen |
| Permission you don't use | Tauri sometimes adds `READ_EXTERNAL_STORAGE` by default — remove from AndroidManifest if unused |
| Webview pointing at unsafe URL | Tauri CSP must restrict `connect-src` to your domain(s). Already configured in `tauri.conf.json`. |
| "App appears to be unreliable" | If the closed test crash rate exceeds Play's threshold, fix and re-test before promoting |

---

## 11. Linking from the web

After production publish, point users at:

```
https://play.google.com/store/apps/details?id=dev.autoclaw.mobile
```

Update `site/index.html` channel grid to add a "Get it on Google Play" badge once the listing is live. Asset and brand guidelines:
<https://play.google.com/intl/en_us/badges/>

---

## 12. F-Droid as a bonus channel

For users who avoid Google services, also publish to F-Droid (free, no fee, manual review). Add `mobile/metadata/en-US/` in the [F-Droid metadata format](https://f-droid.org/docs/Build_Metadata_Reference/) and submit a merge request to <https://gitlab.com/fdroid/fdroiddata>.

Approximate flow:
```yaml
# metadata/dev.autoclaw.mobile.yml
Categories:
  - Development
License: MIT
WebSite: https://autoclaw.dev
SourceCode: https://github.com/dnzengou/autoclaw
IssueTracker: https://github.com/dnzengou/autoclaw/issues
Description: |
  Mobile dashboard for the Autoclaw self-improving AI experiment loop.
AutoUpdateMode: Version v%v
UpdateCheckMode: Tags
```

---

## 13. Reference links

- Play Console: <https://play.google.com/console>
- Brand/badge assets: <https://play.google.com/intl/en_us/badges/>
- Closed test policy: <https://support.google.com/googleplay/android-developer/answer/14151465>
- Data safety form: <https://support.google.com/googleplay/android-developer/answer/10787469>
- Tauri 2 Android docs: <https://v2.tauri.app/distribute/google-play/>
- F-Droid submission: <https://f-droid.org/docs/Submitting_to_F-Droid_Quick_Start_Guide/>
