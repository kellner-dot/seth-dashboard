# 2026-10-05 — Fire TV Vega app session

How the "real Firestick app" project started, what we learned, what we built,
and the rules that will save the next session. Written because last time's
Fire Stick work failed here: claims without repos, handoffs without proof.

## Stick truth (verified tonight, not from handoffs)
- Fire TV Stick 4K Select (2025), model AFTCA002, **Vega OS** (Linux, not Android)
- LAN 10.0.0.151; **not** on the tailnet (no Fire TV node enrolled)
- Emby for Fire TV v0.1.3 confirmed on it; was playing `!KaviTV Experimental`
- `com.kellner.channels` (old handoff claim) **debunked** — Android package
  name, impossible on Vega. Lesson: verify device claims with live probes.

## Decisions
- Build a **native Vega app** (React Native → `.vpkg`, armv7), not a web viewer.
- Distribute **privately via Live App Testing** (Seth's email only); install
  on-stick via the **Appstore Beta Hub** app (Vega-compatible).
- App architecture: embedded Tailscale `tsnet` (stick joins tailnet from inside
  the app) + tailnet HTTP control endpoint (`/status`, `/tune`, `/diag`) so the
  app is remotely operable. WebView-wrap of the existing KaviTV viewer evaluated
  as the faster alternative to full native playback.

## Built tonight
- `devtools/amazon-appstore-skill/` — connector for the Amazon App Submission
  API: auth check, edit lifecycle, APK upload, listing get/put, device-targeting
  fix, review submit. For Seth's **existing Android apps** (Remote, …).
- `devtools/amazon-appstore-skill/references/` — `api-reference.md`,
  `lat-deep-dive.md`, `vega-publishing.md` (sourced, confidence-labeled).

## Still in progress
- `kavitv-vega-app/` build (separate track; lands here when the `.vpkg` is done)
- Networking savant research (tricks + app ideas)

## Rules learned (do not re-learn)
1. `manifest.toml` MUST declare `com.amazon.category.main` — else the app
   won't launch from Home and fails submission.
2. Never write the word "Vega" in any Appstore submission field.
3. Every submission must bump BOTH version and build number.
4. App Submission API: **no** LAT management, **no** first-version submits,
   Android apps only, `commit` = immediate review (no staging hold), edits
   require the app to already be live.
5. Vega has no ADB, no sideloading, no app-inventory API. Installs only via
   Appstore or dev-mode USB + Vega Device Adapter.
6. RVG from side chats: use `bin/pcps.py <script.ps1>`; never `bin/rvg.py`
   directly (credential unavailable to the sandbox).
7. Emby Sessions API = remote-operation workaround for the stick today
   (play/pause/seek to the Firestick's session, no stick cooperation needed).
