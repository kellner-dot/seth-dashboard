# Vega app publishing — deep dive

All claims checked 2026-10-05. Confidence: [O] = verified-official (Amazon
docs), [C] = verified-community (real project, not Amazon), [P] =
plausible-unverified (strong inference, do not present as fact).

## The package
- Vega apps ship as **`.vpkg`** (Vega's package format), built from React
  Native (Kepler SDK) + TypeScript. Managed with **VPT** (create, examine,
  validate, sign: `vpt info`, `vpt show-contents`) and the **Vega CLI**
  (build/deploy workflow). [O]
  https://developer.amazon.com/docs/vega/0.21/vpt.html
- Target arch for Seth's stick (Fire TV Stick 4K Select 2025, MT8698):
  **armv7**. [C] https://github.com/amazonappdev/react-native-multi-tv-helloworld
  and https://github.com/giolaq/giojump (both build `armv7` for physical
  Vega Fire TV hardware)
- **Manifest must register the `main` category
  (`com.amazon.category.main`)** in `manifest.toml`, or the app won't launch
  from the Fire TV Home launcher and **fails Appstore submission**. [O]
  https://developer.amazon.com/docs/vega/0.21/app-submission
- **Version + build number must both increase on every submission**
  (`--build-version`, `--build-number`); the Appstore blocks installing a
  VPKG with a lower build number than what's on-device (downgrade
  protection). APK version codes and VPKG build numbers are independent
  counters. [O]
  https://developer.amazon.com/docs/vega/0.22/app-version.html
  and https://developer.amazon.com/docs/vega/0.21/app-submission

## Console submission (VPKG → Appstore)
Same flow as Fire OS apps, via the Developer Console: [O]
https://developer.amazon.com/docs/vega/0.21/app-submission
1. **Add a New App** (or **Add Upcoming Version** on an existing app).
2. **Upload Your App File** → upload the `.vpkg`.
3. **Target Your App** → Edit supported devices → **Amazon Fire TV** tab →
   **Amazon Vega TV** section → choose the device(s).
4. **Appstore Details** → metadata + all required **Fire TV assets**; in
   Release notes copy existing Fire OS notes if any. **"Do not mention
   'Vega' in any field."** [O] (same page)
5. **Review & Submit** → Submit App → Amazon review → email when live.
- One app listing can carry **both APK and VPKG** binaries (shared
  metadata, IAP, reviews; package names must match). Separate listings are
  possible but double the metadata/IAP maintenance. [O] (same page)
- **VPKG submissions have been supported since Sep 30, 2025** (release
  notes). [O] https://developer.amazon.com/docs/app-submission/release-notes.html

## Review reality
- VPKG goes through the normal Appstore review like any submission; the
  docs describe no Vega-specific fast lane. [P] (workflow documented, review
  criteria not Vega-differentiated)
- Practical: LAT first (no review gate documented), public listing later
  only if ever wanted. See `lat-deep-dive.md`.

## What the Submission API can't do for Vega
- API docs say **"Android apps only"** and exclude Web apps; VPKG is
  undocumented. Treat API management of Vega apps as **unsupported** until
  Amazon says otherwise. [O for the exclusion; P for the Vega inference]
  https://developer.amazon.com/docs/app-submission-api/overview.html
- Related: **Amazon Appstore for Android (mobile) was discontinued Aug 20,
  2025** — "you can no longer submit or update apps for Android mobile
  devices." So the API's "Android apps" now effectively means **Fire OS**
  (Fire TV / Fire tablet) apps. [O]
  https://developer.amazon.com/docs/app-submission/release-notes.html
- API also can't do first-version submissions (console only) or LAT
  versions. [O] https://developer.amazon.com/docs/app-submission-api/overview.html
- Community data point: the galonga GitHub Action (API-based APK upload)
  reports `Cannot create a new 'edit' for the app in its current state`
  unless **the app is already live** — i.e., API edits in practice require
  a live app, not just a console draft. [C]
  https://github.com/galonga/upload-amazon-appstore

## Community-verified capabilities & tricks
- **Tailscale inside the .vpkg.** `looizao/jellyfin-vega-tailnet` embeds
  Tailscale's official `tsnet` engine in an armv7 VPKG; the app joins the
  user's tailnet itself and reaches home servers by tailnet name/IP — no
  separate Tailscale app, no public ports. Directly applicable to KaviTV:
  SETHS-PC is already a tailnet node, so the app could stream from the
  relay over the tailnet instead of a hardcoded LAN IP. Caveats: project is
  a "device-testing preview", installed via Developer Mode (not an
  Appstore listing), and whether Amazon review accepts a tsnet-embedding
  app is unknown. [C] https://github.com/looizao/jellyfin-vega-tailnet
  (checked 2026-10-05)
- **WebView wrapper shortcut.** Vega ships a media-capable WebView;
  `giolaq/giojump` packages a production web app (Vite build) inside
  React Native for Vega 0.83 WebView into a `.vpkg`. KaviTV's existing web
  viewer (`~/workspace/seth-dashboard/kavitv/`: `index.html` + `guide.html`
  + `hls.min.js`) could be wrapped this way instead of a full RN rewrite —
  trade-off: faster build, less native TV feel. [C]
  https://github.com/giolaq/giojump (checked 2026-10-05)
- **Pinned working toolchain** (from the jellyfin-vega project): Vega SDK
  **0.22.5850**, Node **22.22.0**, Go 1.26.8, React Native **0.72**, WebView
  **3.5.11**, Tailscale 1.102.4. Ships a **Docker Ubuntu builder** for hosts
  Amazon doesn't support. [C] (same repo)
- **Official starter:** `amazonappdev/react-native-multi-tv-helloworld` —
  Yarn workspaces sharing code across Vega / Android TV / Apple TV; shows
  the `vega run-app <vpkg> <app-id> -d <DSN>` deploy flow. [C]
  https://github.com/amazonappdev/react-native-multi-tv-helloworld
- **Dev-mode install commands** (no Appstore): enable Developer Mode on the
  stick (triggers reboot), connect via USB with the Vega Device Adapter,
  then `vega device -d <SERIAL> install-app --packagePath <app>.vpkg` and
  `vega device -d <SERIAL> launch-app --appName <pkg>.main`. Per press
  reports, dev-installed apps show a generic icon — fine for testing, not
  for daily use. [C] (jellyfin-vega-tailnet INSTALL flow; ghacks.net on
  generic-icon behavior)
- **Vega Device Adapter (VDA)** is the USB bridge the Vega CLI uses
  (`kepler exec vda push/shell`, `vpm install`). The stick must be
  USB-connected to the dev machine — Seth's stick is not currently
  USB-connected to SETHS-PC. [O]
  https://developer.amazon.com/docs/vega/0.21/configure-app-tester.html

## Fire TV asset checklist (for the Appstore Details screen)
From the live-tested community skill (Android side; same console screens
per Amazon's "same submission process" statement — treat sizes as [C]):
icon 512px (`large-icons`), icon 114px (`small-icons`), Fire TV banner
1280×720 (`firetv-icons`, the store tile), Fire TV background 1920×1080
(`firetv-backgrounds`), Fire TV screenshots 1920×1080. Required per locale
listing; they don't inherit across locales. [C] (acerbetti/skills
amazon-appstore, verified live 2026-08-25)
https://github.com/acerbetti/skills/blob/HEAD/amazon-appstore/SKILL.md

## Strategic note
Fire TV Stick 4K Plus / 4K Max are the last sideloadable Android sticks;
all new sticks are Vega. Building the Vega/LAT pipeline now is the durable
route — Fire OS sideloading knowledge is a depreciating asset. [C]
(synthesis of Amazon's Vega rollout reporting, Oct 2026)
