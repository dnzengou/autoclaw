# Autoclaw Mobile — Tauri 2

Native wrappers (Android APK, iOS IPA, macOS .app, Windows .exe, Linux .AppImage) around the React dashboard at `../ui`.

## Prerequisites

```bash
cargo install tauri-cli --version "^2.0"
rustup target add aarch64-linux-android armv7-linux-androideabi i686-linux-android x86_64-linux-android
# Android Studio + NDK (set ANDROID_HOME, NDK_HOME)
# JDK 17
```

## Build APK

```bash
# Dev (live reload from ../ui)
cargo tauri android dev

# Production APK
cargo tauri android build
# → src-tauri/gen/android/app/build/outputs/apk/universal/release/app-universal-release.apk

# Production AAB (Google Play)
cargo tauri android build --aab
```

## Build iOS

```bash
cargo tauri ios build
# → src-tauri/gen/apple/build/arm64/Autoclaw.ipa
```

## Build desktop

```bash
cargo tauri build
# → src-tauri/target/release/bundle/
```

## Server connection

The mobile shell connects to a running Autoclaw server (Rust / Go / Python). Default:

- Android emulator: `http://10.0.2.2:8080` (host machine)
- Physical device: set `AUTOCLAW_URL` to your server's LAN IP

Override at runtime via the in-app settings panel (writes to platform secure storage).
