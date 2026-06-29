# Autoclaw — Icons

Source: `icon.svg` (512×512, brand orange `#ff7a3d` on dark `#0b0d10`).

## Generate platform variants

Tauri 2 includes an icon generator that takes one PNG and produces the full pack
(Android, iOS, Windows, macOS, Linux). From the repo root:

```bash
cd mobile
cargo tauri icon icons/icon.svg
```

This writes to `mobile/icons/`:

```
32x32.png            # tray, small UI
128x128.png          # menu bar
128x128@2x.png       # retina menu bar
icon.icns            # macOS
icon.ico             # Windows
Square*Logo.png      # Windows Store sizes
StoreLogo.png        # Windows Store
android/             # all densities (mdpi → xxxhdpi) + adaptive
ios/                 # all iOS sizes
```

Commit everything in this directory. The Tauri config (`tauri.conf.json`)
points to the files here at build time.

## Re-generate after a brand change

```bash
# Edit icon.svg, then:
cargo tauri icon icons/icon.svg --force
git add icons/ && git commit -m "chore(mobile): refresh icons"
```

## Play Store / App Store hero icon

The 512×512 hero icon for the Play Store listing is rendered separately to
`store-assets/icon-512.png` — see `mobile/PLAY_STORE.md` section 3.
