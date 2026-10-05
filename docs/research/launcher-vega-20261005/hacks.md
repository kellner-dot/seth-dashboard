# Vega OS Home Screen & Launcher Hacks — 2026-10-05

Savant research for Seth: everything a developer can influence on the Vega
launcher, so his apps feel like first-class citizens. Confidence:
[O] official · [C] community-verified · [P] plausible/unverified.
Sources dated 2026-10-05 unless noted.

---

## 1. Categories: `main` vs `launcher` — the correction

The genius guide said `com.amazon.category.launcher` is "system-reserved,
do not use." The real story, from Vega's own system dump, is more precise:

- `com.amazon.category.main` = **appears in the app launcher grid**.
  Amazon's submission docs: "Your app must register the `main` category
  in the app manifest. Without the `main` category, your app can't launch
  from the Fire TV Home launcher and will fail the Amazon Appstore
  submission process." [O — developer.amazon.com/docs/vega/0.21/app-submission.html]
- `com.amazon.category.launcher` = **registers as a launcher/home-screen
  replacement** (the home screen itself). From
  `system-rootfs/etc/pkgmgrd/factory-default-components.conf` in the Vega
  system dump: "This file defines product specific default application
  components for categories such as launcher" — the default component is
  `com.amazon.wakeuphandler.task`. [C — R0rt1z2/callie_dump, Vega system
  dump]
- A community app (Adarsh-Dhar/FamilyScreen) declares BOTH categories —
  almost certainly a mistake; it would contend for the home-screen role.
  Seth's apps need ONLY `com.amazon.category.main`. [C]

## 2. Tile artwork — the 3:2 crop trap

- Icon: 512×512 PNG, `icon = "@image/icon.png"` in `[package]`.
  Without it: no launcher tile at all (genius guide, verified). [O/C]
- **The launcher does NOT show the square.** From fortemate/dicechess-tv's
  friction log (FL-16, 2026-09-23): the launcher scales the icon to fill a
  **3:2 tile (~304×200 on 1080p)** and crops top and bottom — only the
  band from **y=100 to y=412** of the 512px icon survives. A bare mark on
  transparency looks distorted; artwork near top/bottom edges gets
  decapitated. [C — fortemate/dicechess-tv, 2026-09-23]
- **How-to:** design icons as opaque, keep all critical artwork inside the
  y=100–412 band with even side margins. dicechess-tv ships a test that
  fails the build if artwork leaves the band — steal that pattern.
- The same icon field serves Settings AND launcher (two surfaces, two
  shapes) — there is no separate launcher-tile asset. [C]
- No evidence of animated tiles or per-app tile badges on Vega. [P-negative:
  nothing found across GitHub, Amazon docs, XDA, Reddit]

## 3. Sideload vs Live App Testing — verified, twice

- **ghacks (Oct 2025):** "sideloaded apps appear with a generic 'App' icon
  and are disabled unless actively used, making them nearly unusable."
  [C — ghacks.net, 2025-10-01]
- **aftvnews (Elias Saba, updated):** originally reported no way to embed
  a custom icon (gray default); later corrected — "there is a way to
  declare and package an app icon in Vega apps by listing it in the app's
  manifest file." But: "Vega OS seems to disable sideloaded apps that
  aren't being actively worked on... every Vega OS app I've created and
  sideloaded eventually stops launching altogether" (later suspected a
  bug, not policy). [C — aftvnews.com, 2025]
- **Bottom line for Seth:** sideloading is a dev loop, not distribution.
  Full launcher integration (real tile, pinnable, stays enabled) requires
  Appstore or **Live App Testing**. This is why the LAT plan is the actual
  fix for "can't open/pin my apps."

## 4. Content Launcher — Vega's recommendations system

This is the Vega equivalent of Leanback recommendations rows, and it's
official and documented [O — developer.amazon.com/docs/vega/0.21/content-launcher-overview.html]:

- **Featured rows** on the home screen ("Next up for you", "Recommended
  free movies and TV programs", "Latest movies"): "Only Content Launcher
  integrated content is included in these featured rows. Content Launcher
  requires no additional integration to feature your content."
- Integration = EMBER catalog ingestion (describe media in Amazon's catalog
  schema, upload to S3 regularly) + Content Launcher API +
  Account Login API.
- **Universal Search:** catalog-ingested content appears in Fire TV search
  and content detail pages **even if the user hasn't installed the app**
  (Buy Box promotion). [O]
- **Voice:** "Alexa, watch <title> on <app name>" → `handleLaunchContent`
  callback; transport control ("Alexa, pause", "fast forward 5 minutes")
  via Vega Media Controls — free with the W3C Media API. [O]
- Test hook: push `KVATestData.json` to
  `/home/app_user/packages/<id>/data` and search uses only that file.
  [C — roddy87pl/vega README]
- Note: catalog integration is an Amazon-partner track (allowlist/S3) —
  realistic for Seth's apps only if he pursues it; the API surface is the
  useful part regardless.

## 5. Continue Watching Row (CWR)

- Amazon's certification tests: watching content with playback position
  **2%–92%** puts a tile in the Home tab's **Continue Watching Row** as
  the first row; resuming starts from the saved timestamp. ≤2% shows for
  10 min after last engagement, then is removed. [O —
  developer.amazon.com/docs/vega/0.21/test-cases-integration.html]
- Force refresh: Settings > Account & Profile Settings > Sync Amazon
  Content. [O]
- This is content-level recents (not app-level). Implementation detail for
  the KaviTV app: report playback position and the CWR handles the rest.

## 6. Linear TV rows + logo badging

- Live TV integration: EPG ingestion + channel tuning + provider logo.
  **Logo badging** appears top-right on channel tiles in Search, On Now,
  Guide, and provider rows — image must be **monochrome, ≤34px high,
  ≤25% width** of the overlay. [O —
  developer.amazon.com/docs/vega/0.21/get-started-with-linear-tv.html,
  May 2026]
- Requires Amazon allowlisting ("reach out to your Amazon contact").
  Realistic only if Seth pursues the partner track.

## 7. Deep links (Feature Rotator, Appstore)

- **Featured content tiles** (sponsored/promotional tiles on the home
  screen) deep-link into apps — implement "Handle Featured Content Deep
  Link" per Vega 0.23 docs. [O —
  developer.amazon.com/docs/vega/0.23/deep-links-vega-apps.html]
- Deep link to Appstore detail pages (e.g. forced update via ASIN +
  `intent=app_update`). [O]
- App-to-app: `[[message]]` + `[offers.message-target]` + RN Linking
  (already in the playbook).

## 8. Screensaver / lifespan — production truth

From screentinker's production manifest (signage app, v2.3.2) [C —
screentinker/screentinker, vega/manifest.toml]:

```toml
[[components.interactive]]
lifespan = "permanent"
timeout-secs = 86400
```

- `lifespan = "permanent"` = what LCM's idle handler treats as
  "screensaver disabled by policy."
- `timeout-secs` = how long a foreground component with no input stays up
  before LCM backgrounds it.
- **Neither is a wake lock:** "power-service-core can still force the
  display off, and there is no privilege that stops that."
- screentinker 2.2.0 (Sept 2026) added Vega OS as a player platform —
  the lifespan pattern is battle-tested on the 4K Select.

## 9. Recent apps

- The home screen has a **Recent row** (confirmed by aftvnews Vega 2.0
  reporting: "the Recent row of the Home screen"). [C — aftvnews.com,
  Oct 2026]
- On Vega 2.0 (new 2026 4K stick, NOT Seth's 1.2 stick): the app list is
  "the sole customizable portion," currently can't be reordered, and new
  installs sometimes don't appear — plus a gray-generic-icon bug
  affecting even Appstore apps (1.8-star launch). Seth's Vega 1.2 stick
  does not have these bugs; do not "fix" what isn't broken there. [C]

## 10. What you CANNOT do (honest gaps)

- **Custom launchers:** impossible on Vega. The `com.amazon.category.launcher`
  role is a system default component; XDA's Launcher Manager / Wolf
  Launcher world is Fire OS (Android) only. [C — XDA forums, hdtvtest]
- **App tile badges** (notification counts): no API found anywhere. [P-negative]
- **Animated tiles:** no evidence. [P-negative]
- **Sideloaded apps in Universal Search:** Content Launcher requires
  catalog ingestion, which requires the partner/Appstore track. [O]
- **Reordering the app list:** not user-controllable on Vega 1.2 (and
  broken on 2.0). [C]

## 11. Already in the genius guide (not duplicated)

`com.amazon.category.main` basics · icon 512×512 ≤1MB · launcher tile
requires icon · reboot to re-enumerate · `vda`/`vpm`/`vlcm` · deep-link
`[[message]]` pattern · KeplerBackHandler.
