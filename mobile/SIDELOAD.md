# Sideload Autoclaw — Standalone APK Install

> Install the Autoclaw Android app outside the Play Store. Takes 2 minutes.

Sideloading lets you run the app immediately, before the Play Store listing is live, on any Android 7.0+ (API 24) device.

---

## 1. Download the APK

| Source | Verified | Use when |
|---|---|---|
| **GitHub Releases** (recommended) | SHA256-signed by CI | Always available |
| **autoclaw.dev/download** | Mirror of GitHub Releases | Faster on slow GitHub days |

Direct links to the latest release:

```
https://github.com/dnzengou/autoclaw/releases/latest/download/autoclaw-android-arm64-v8a.apk
https://github.com/dnzengou/autoclaw/releases/latest/download/autoclaw-android-armeabi-v7a.apk
https://github.com/dnzengou/autoclaw/releases/latest/download/autoclaw-android-x86_64.apk
https://github.com/dnzengou/autoclaw/releases/latest/download/autoclaw-android-universal.apk
```

Most modern phones (2018+) need **arm64-v8a**. Older devices or emulators may need armeabi-v7a or x86_64. If unsure, grab the **universal** APK (~3× larger, runs anywhere).

### Verify the download

```bash
# On the desktop, before transferring to your phone:
sha256sum -c autoclaw-android-arm64-v8a.apk.sha256
# Expected: autoclaw-android-arm64-v8a.apk: OK
```

The `.sha256` file lives next to each APK on Releases.

---

## 2. Allow installs from unknown sources

**Android 8.0+ (per-app permission, recommended):**

1. Settings → Apps → Special access → **Install unknown apps**
2. Pick the app you'll use to open the APK (Files, Chrome, Firefox, Drive)
3. Toggle **Allow from this source**

**Android 7.x (global toggle):**

1. Settings → Security → **Unknown sources** → enable

Disable it again after install for safety.

---

## 3. Install

| Method | Steps |
|---|---|
| **From phone browser** | Open the GitHub release link → tap the APK → tap **Install** when prompted |
| **From file manager** | Transfer APK via USB / Drive / AirDrop → tap the file → **Install** |
| **From `adb`** (developer mode) | `adb install autoclaw-android-arm64-v8a.apk` |

Play Protect may show "Blocked by Play Protect — this app is not commonly downloaded". Tap **More details → Install anyway**. This is normal for any APK signed outside the Play Store.

---

## 4. First launch — point the app at a server

The Android app is a **dashboard**, not the loop itself. The loop runs as a server on your laptop, VPS, or container — the app connects to it over HTTP/WS.

**Pick where your server runs:**

| Server location | `AUTOCLAW_URL` to enter |
|---|---|
| Your laptop on same Wi-Fi | `http://192.168.1.42:8080` (your laptop's LAN IP) |
| Cloud VPS / Fly.io / Railway | `https://your-app.fly.dev` |
| Android emulator → host machine | `http://10.0.2.2:8080` |
| Termux on the same device | `http://127.0.0.1:8080` |

**In-app:** Settings → Server URL → paste → **Connect**. The status dot turns green when reachable.

---

## 5. Run your first experiment from the app

Once connected:

1. Tap **Context** → edit the markdown → save.
2. Tap **▶ Start** in the header.
3. Watch experiments stream into the **Experiments** tab.
4. Tap any experiment for its hypothesis, params, metrics, git hash.
5. Tap **Best** to jump to the highest-scoring run.

The app uses native Android components for tabs/lists and the React dashboard for charts — both work offline once the page is cached (just the data needs the server live).

---

## 6. Update

Sideloaded apps **do not auto-update**. To upgrade:

1. Download the newer APK from Releases.
2. Install over the existing app (signature must match — all releases are signed with the same key).
3. Your server URL and settings persist.

To get automatic updates, install via the Play Store once it's live (see [PLAY_STORE.md](PLAY_STORE.md)).

---

## 7. Uninstall

Long-press the app icon → **App info** → **Uninstall**.

Server config is stored in app-private storage and removed with the app. No leftover files.

---

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| "App not installed" | Existing app signed with a different key — uninstall it first |
| "Parse error" | Wrong ABI for your device — try the universal APK |
| Status dot stays red | Server unreachable — `curl` the URL from your phone's browser to confirm |
| Connection works once then dies | Sleep-mode network throttling — keep the phone awake while watching live runs, or use a hosted server |
| Can't see LAN server | Phone and laptop on different SSIDs / VLANs / VPNs |
| Play Protect warning loops | Open the APK from a file manager (not browser) and try again |

---

## 9. Security notes

- Every release APK is signed with our release key — same key across versions guarantees in-place upgrades work without uninstalling.
- The APK has only three runtime permissions: `INTERNET`, `ACCESS_NETWORK_STATE`, `WAKE_LOCK` (last one only while a stream tab is open). No camera, mic, location, contacts, files, or background data.
- The app never sees your LLM API key — the **server** holds it. The app only talks to your server's `/api/*` and `/events`.
- Webview is locked to your configured server URL via CSP — it cannot navigate to arbitrary sites even if a hostile link arrives via the dashboard.
- Full policy: [PRIVACY.md](../PRIVACY.md).

---

## 10. Build the APK yourself

If you don't trust pre-built APKs (good instinct), build from source:

```bash
git clone https://github.com/dnzengou/autoclaw && cd autoclaw
# Prereqs: JDK 17, Android Studio + NDK, rustup with android targets
rustup target add aarch64-linux-android armv7-linux-androideabi i686-linux-android x86_64-linux-android
cargo install tauri-cli --version "^2.0" --locked

cd ui && npm install && npm run build && cd ..
cd mobile
cargo tauri android init
cargo tauri android build --apk
# Output: mobile/gen/android/app/build/outputs/apk/universal/release/app-universal-release.apk
```

CI also builds these on every tag push — see `.github/workflows/android.yml`.
