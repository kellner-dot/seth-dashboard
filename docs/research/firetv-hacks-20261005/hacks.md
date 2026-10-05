# Fire TV Stick 4K Select / Vega OS — Hacks, Tricks & Workarounds

Researched 2026-10-05. GitHub-first. Everything already in
`VEGA-APP-GENIUS.md` (kellner-dot/firetv-vega) is skipped except where
noted as a correction. Confidence: **[O]** verified-official ·
**[C]** verified-community/by-hand · **[P]** plausible, unverified.

Several items below were verified LIVE on Seth's stick tonight via the
socat tunnel + `vda` (`socat TCP-LISTEN:15555,fork,reuseaddr
PROXY:hatch-egress-proxy:10.0.0.151:5555,proxyport=3130 &` then
`vda connect 127.0.0.1:15555`).

---

## 1. Device access & shell

### 1.1 Component shell — run commands INSIDE a running app's sandbox [C]
**What:** `vda shell -c <component-id> "<command>"` executes in the app's
component context, seeing `/pkg/` (read-only package), `/data/` (app
private), `/tmp`. The default `vda shell` lands in a restricted sandbox
where `/var/lib/pkgmgrd` is invisible — the component shell bypasses that.
**Why:** Inspect any installed app's real manifest, assets, and data
without pulling the VPKG. Tonight: read KaviTV v0.1.0's manifest and
asset list straight off the stick.
**How:**
```bash
vda -s 127.0.0.1:15555 shell "vlcm launch-app pkg://com.kellner.channels.main"
vda -s 127.0.0.1:15555 shell -c com.kellner.channels.main 'ls -la /pkg/assets/'
```
**Catch:** the component must be RUNNING (launch it first); otherwise
`Error: No running instances of <id> found`.
**Source:** `vda help` (Vega Device Adapter 2.6, SDK 0.24.12112) + verified
live 2026-10-05.

### 1.2 `vlcm list` — live component inventory [C]
**What:** Shows every component with type (I=interactive, S=service),
pid, id, state (READY/STOPPED), lifespan, container.
**Why:** See what's actually running vs installed; all of Seth's apps
show `STOPPED / PERMANENT` — none are resident.
**Source:** verified live 2026-10-05.

### 1.3 `vmsgr send` is the preferred launch/message command [O]
**What:** `vlcm launch-app` prints `Please migrate to 'vmsgr send'
command.` The messenger CLI: `vmsgr send <uri>`, `vmsgr launch-app
<uri>`, `vmsgr listen <uri>`, `vmsgr check-access`, `vmsgr dump-state`,
`vmsgr enforce-security`.
**Why:** `vmsgr send` launches AND delivers messages with query params —
the path for remote control and app-to-app calls.
**Source:** on-device `vmsgr --help` 2026-10-05; Amazon docs
`developer.amazon.com/docs/vega/0.21/app-management-com-tools.html`.

### 1.4 `vda pair` — secure the open ADB port [C]
**What:** `vda pair HOST[:PORT] [PAIRING CODE]` — ADB-style secure
pairing for TCP/IP. Right now port 5555 accepts unauthenticated
connections from the whole LAN.
**Why:** Anyone on Seth's LAN can currently `vda connect` to the stick.
Pairing locks it down.
**Source:** `vda help` (VDA 2.6). Behavior on Vega untested — [P] for
Vega specifically.

### 1.5 `vda root` / `vda authenticate` exist in the help text [P]
**What:** `vda root` ("restart vdad with root permissions"),
`vda authenticate` ("Enable the Developer mode"), `vda sideload
OTAPACKAGE`, `vda tcpip PORT`.
**Why:** `authenticate` might trigger the devmode flow from CLI;
`root` is worth one careful try (likely blocked on production builds).
**Source:** `vda help`. Untested — do not rely on.

### 1.6 Compressed push/pull + port forwarding [C]
**What:** `vda push/pull -z zstd|brotli|lz4` for fast transfers;
`vda forward tcp:<local> tcp:<remote>` / `vda reverse` like ADB.
**Why:** Push media/config to the stick fast; forward a debug port
through the socat tunnel.
**Source:** `vda help` (VDA 2.6).

---

## 2. Deep linking — officially documented, genius guide missed it [O]

### 2.1 The deep-link docs exist
Amazon's Vega docs now have a full page:
`developer.amazon.com/docs/vega/0.23/deep-links-vega-apps.html`
(crawled 2026-10-05). The genius guide's claim ("no open-source app
implements deep links") is about community adoption, not platform
support — the platform supports it.

### 2.2 How it works
- Per-URI `[[message]]` blocks in `manifest.toml` with
  `sender-privileges` / `receiver-privileges` (`["*"]` = anyone can call).
- `[offers.message-target]` maps non-`pkg://` URIs (custom scheme or
  https) to the component to launch.
- `pkg://<component-id>` addresses lifecycle components directly.
- In RN: `Linking.addEventListener('url', …)` (app open),
  `Linking.getInitialURL()` (cold start).
- Test from CLI: `vmsgr send` with query params.

### 2.3 Why Seth cares
App-to-app contracts between his own apps become possible:
KaviTV deep-links a channel into his IPTV Player
(`kavitv://tune?channel=horror`); the phone remote sends deep links
instead of raw keys; featured-content tiles on the Fire TV home screen
can deep-link into KaviTV.
**Source:** [O] Amazon Vega docs 0.23 (2026).

---

## 3. Launcher & lifecycle

### 3.1 Why sideloaded apps feel broken [C]
Per ghacks (2025-10-01): sideloaded Vega apps "appear with a generic
'App' icon and are disabled unless actively used, making them nearly
unusable." This is exactly Seth's "can't open and close or pin"
complaint about KaviTV v0.1.0. The fix is proper packaging (real icon)
AND proper distribution — only Appstore/LAT builds get full launcher
integration.
**Source:** [C] https://www.ghacks.net/2025/10/01/amazon-announces-vega-os-for-tv-a-linux-based-os-that-doesnt-support-sideloading/

### 3.2 Declarative `[[message]]` pkg:// auto-launch [P]
**What:** The genius guide notes `[[message]]` can do "declarative
`pkg://` auto-launch without code."
**Why:** Closest thing found to a Vega-native auto-start hook. Worth
testing whether a message can fire at boot/login.
**Source:** [P] genius guide Part 2; no Vega boot-broadcast docs found
(all XDA auto-start results are Fire OS/Android only).

### 3.3 No Vega boot auto-start API found
Every "launch on boot" result is Fire OS (OnBootKodi etc., some
blacklisted by Amazon). On Vega: use `lifespan = "permanent"` +
`timeout-secs` to resist reclamation, and relaunch remotely via
`vmsgr send` (cron-able from the VM through the socat tunnel).
**Source:** [C] search 2026-10-05 — absence of evidence, stated as such.

---

## 4. Inter-app patterns worth stealing

### 4.1 QR pairing (homeboard) [C]
**What:** `kuldeep-poonia/homeboard` (created 2026-10-03, updated
2026-10-04): TV app shows a QR code with a single-use join token
(10-min TTL); phone scans it → session cookie → WebSocket live sync
room. No typing, no pairing codes.
**Why:** The exact pattern for Seth's phone-as-remote idea — TV displays
QR, Razr scans, instant control channel.
**Source:** [C] https://github.com/kuldeep-poonia/homeboard
(ARCHITECTURE.md, 2026-10-04).

### 4.2 Guided devmode setup script [C]
**What:** `giolaq/vega-firetv-setup` (2026-10-03): single Bash script,
out-of-box → devmode enabled, with automatic recovery from expired
codes/sessions.
**Why:** If Seth ever factory-resets the stick, this replaces the
manual runbook.
**Source:** [C] https://github.com/giolaq/vega-firetv-setup

### 4.3 Cloud App Program — run Android apps on Vega without porting [O]
**What:** Amazon streams Fire OS Android apps to Vega devices from the
cloud (mentioned in 2026 4K launch coverage). The app isn't installed on
the stick.
**Why:** If Seth ever wants an Android-only app on the 4K Select, check
whether it's in the cloud program before rewriting it.
**Source:** [O] https://www.ecoustics.com/products/amazon-fire-tv-stick-4k-2026/
(2026-10-01).

---

## 5. Debugging

### 5.1 Builder-tools MCP server [P]
**What:** `amazon-devices-buildertools-mcp` — MCP server with
`analyze_perfetto_traces`, `get_app_hot_functions`, `symbolicate_acr`,
plus a `search_documentation` tool. Referenced in
`g-tejas/dabloons` `.agents/skills/argent-tv-interact/SKILL.md`.
**Why:** Symbolicated crash reports + perf traces for Vega apps.
**Catch:** not on public npm (404) — likely partner/internal
distribution. Ask in the Amazon developer forums.
**Source:** [P] https://github.com/g-tejas/dabloons (SKILL.md, crawled
2026-10-05).

### 5.2 newrelic Vega agents [C]
**What:** `newrelic/FireTV-Vega-Agent` and `FireTV-Vega-Crash-Agent` —
crash/performance monitoring agents for Vega OS apps.
**Why:** Drop-in crash reporting for Seth's apps instead of hand-rolled.
**Source:** [C] https://github.com/newrelic/FireTV-Vega-Agent

---

## 6. Media & hardware reality checks

### 6.1 1GB RAM is the defining constraint [O]
Amazon's VP of Fire TV (Aidan Marcuss, ~Jul 2026): the 4K Select runs
the full modern experience on **1GB RAM** — half the previous
generation. Every Vega app decision (bundle size, `memoryWarning`
handling, `lifespan` tuning, no background JS reliance) flows from this.
**Source:** [O] https://troypoint.com/amazon-vp-fire-tv-vega-os-switch/

### 6.2 No Dolby Vision / no Dolby Atmos decode on 4K Select [O]
4K/HDR10/HDR10+/HLG yes; Dolby Vision no; Atmos is HDMI-passthrough
only. Don't build features assuming them.
**Source:** [O] https://www.ecoustics.com/products/amazon-fire-tv-stick-4k-2026/

### 6.3 The whole future lineup is Vega [O]
Amazon confirmed all future Fire TV Sticks run Vega OS; the 4K Plus/Max
are the last sideloadable Android sticks. Investment in the Vega
toolchain is safe.
**Source:** [O] https://mobilityarena.com/how-to-sideload-apps-on-firestick-and-android-tv-2026-guide/
(2026).

### 6.4 Stremio on Vega exists [C]
`deyrudra/StremioFireTvVegaOS` (2026-09-25) — a real streaming app
ported to Vega. Worth reading for their player/data-layer choices.
**Source:** [C] https://github.com/deyrudra/StremioFireTvVegaOS

---

## 7. New community projects since 2026-10-03 (genius guide cutoff)

| Project | What | Why interesting |
|---|---|---|
| `kuldeep-poonia/homeboard` | Ambient household board, QR pairing, WS sync | Pairing pattern for phone remote |
| `giolaq/vega-firetv-setup` | Guided devmode script | Factory-reset recovery |
| `deyrudra/StremioFireTvVegaOS` | Stremio on Vega | Media app architecture |
| `Ronak1167/aura-vega-tv` | Ambient hub, hackathon 2026 | Ambient-mode patterns |
| `danielhagever/everybody-moves` | Family workout app | Multi-user TV UX |
| `Jeremiah-Sakuda/sema-firetv` | Audio-description app | Accessibility API usage |
| `bayraktartahsin/vita-heart` | Health dashboard + Alexa+ MCP | Alexa+ integration example |

---

## 8. Already covered in the genius guide (one-liners, not duplicated)

- KeplerBackHandler for Back-button consume; `useTVEventHandler` HWEvent
  types; 350ms dedupe hazard — Part 7.
- w3cmedia MSE pipeline (`set_src_uri` rejects raw URLs); PlayerSession
  bitmask; `decodingInfo` probing — Part 8.
- `lifespan`/`timeout-secs`; background-kill rule; `memoryWarning` —
  Part 9.
- expo-file-system works / AsyncStorage is in-memory-only — Part 9.5.
- VPKG is zstd, not zip; `vpt validate/show-contents` — Part 10.
- `com.amazon.category.main` + 512×512 icon = launcher tile — Part 2.
- WebView `allowSystemKeyEvents` for Back-in-web — Part 4/6.
- KMMB regenerates `[needs.module]` — don't hand-edit — Part 14.
