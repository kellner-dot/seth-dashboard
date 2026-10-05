# Fire TV Stick 4K Select (Vega OS) — Remote Input/Control Protocols

Savant research, 2026-10-05. Feeds the Razr phone-as-remote project.
Confidence: [O] verified-official · [C] verified-community · [P] plausible · [L] verified LIVE on Seth's stick tonight.

## Method 1: `inputd-cli` via vda shell — THE Vega input injection path [L]

Vega does NOT have Android's `input` binary (`/bin/sh: input: command not found` — verified live).
Its replacement is `inputd-cli`, reached through the vda device adapter:

```bash
# tunnel + connect (once per session)
socat TCP-LISTEN:15555,fork,reuseaddr PROXY:hatch-egress-proxy:10.0.0.151:5555,proxyport=3130 &
VDA=/home/hatch/vega/sdk/vega-sdk/main/0.24.12112/packages/KeplerCLIVegaDeviceAdaptor/KeplerCLIVegaDeviceAdaptor-2.0.14889.0/AL2_x86_64/DEV.STD.PTHREAD/build/bin/vda
$VDA connect 127.0.0.1:15555

# inject a D-pad press (verified live: "Injecting Button Press As Driver: KEY_UP State: short")
$VDA -s 127.0.0.1:15555 shell "inputd-cli button_press KEY_UP"

# long-press (900ms) — for held-Select behaviors
$VDA -s 127.0.0.1:15555 shell "inputd-cli button_press KEY_ENTER --holdDuration 900"
# or: inputd-cli button_press KEY_ENTER long   (also: short | superLong)

# type text into the focused field
$VDA -s 127.0.0.1:15555 shell "inputd-cli send_text 'hello'"

# touch / swipe / mouse (devmode only)
$VDA -s 127.0.0.1:15555 shell "inputd-cli touch 960 540"
$VDA -s 127.0.0.1:15555 shell "inputd-cli swipe 960 800 960 200"
$VDA -s 127.0.0.1:15555 shell "inputd-cli mouse_click 960 540"

# hold + release (multi-button combos, scripted)
$VDA -s 127.0.0.1:15555 shell "{ echo 'button_hold KEY_BACK'; echo 'button_hold KEY_MENU'; sleep 3; echo 'button_release KEY_BACK'; echo 'button_release KEY_MENU'; echo exit; } | inputd-cli start"
```

**Key names are Linux evdev, NOT Android.** `DPAD_UP`, `KEYCODE_DPAD_UP` → `invalid button value`.
Numeric codes are Linux codes too (`19` → warned "Use the key name 'KEY_R' instead" — 19 is KEY_R in Linux input.h, not Android's DPAD_UP).
Remote mapping: KEY_UP/DOWN/LEFT/RIGHT, KEY_ENTER (select), KEY_BACK, KEY_HOME, KEY_MENU,
KEY_PLAYPAUSE, KEY_REWIND, KEY_FASTFORWARD, KEY_VOLUMEUP, KEY_VOLUMEDOWN, KEY_MUTE.
(KEY_UP [L] verified live; KEY_LEFT/KEY_DOWN/KEY_BACK/KEY_MENU [O] appear in Amazon's official
scripting example; the rest [P] standard Linux evdev names.)

**Devmode gate [O]:** per https://developer.amazon.com/docs/vega/0.22/run-apps.html —
advanced commands (touch, swipe, button_press, send_text) require Developer Mode.
Without it, only basic commands work (get_screen_size, get_mic_state, get_camera_cover_open_close).
Seth's stick has devmode enabled. Note the silent-failure trap found by software-mansion/argent:
`get_screen_size` succeeds without devmode, so don't use it as a capability probe —
a failed `button_press` is the real test.

**Latency [C]:** each `vda shell` invocation pays ~1.6s handshake overhead
(software-mansion-labs/vega-fast-cli measurement). For a phone remote this is unusable
per-press — see Method 2.

Sources: live test 2026-10-05 [L]; https://developer.amazon.com/docs/vega/0.21/inputdcli.html [O];
https://github.com/software-mansion-labs/vega-fast-cli [C].

## Method 2: Persistent `inputd-cli` REPL / on-device server — the low-latency path [C]

**software-mansion-labs/vega-fast-cli** (GitHub): replaces the ~1.6s-per-call handshake with an
on-device server holding an `inputd-cli` REPL open — presses then cost milliseconds:

```
vega-fast-cli press up right select   # D-pad / remote buttons, one round-trip
vega-fast-cli type "hello world"      # type into the focused field
vega-fast-cli key enter               # a single named key
```

How it works: host binary `adb forward`s a localhost port, deploys a static musl server to the
device if missing, and sends commands over HTTP/1.1 JSON to the held-open REPL.
Built for the Vega Virtual Device, but the mechanism (`vda forward` + `vda push` + `inputd-cli start`
REPL) is transport-identical on a physical stick [P — not yet tried on hardware].

**This is the recommended architecture for the Razr remote:** phone → (tailnet or LAN) → tiny
HTTP bridge → persistent `inputd-cli` REPL on the stick. Millisecond presses, no per-press handshake.
Alternative without a custom server: keep one `vda shell` session open piping into `inputd-cli start`
and write `button_press KEY_X` lines into its stdin (the Amazon docs scripting pattern above) —
same effect, zero new binaries.

Sources: https://github.com/software-mansion-labs/vega-fast-cli [C];
https://developer.amazon.com/docs/vega/0.21/inputdcli.html ("Automate input with scripts") [O].

## Method 3: `vmsgr send` / `vlcm` — app launching and messaging (NOT input) [C]

- `vlcm launch-app` launches components but now prints a deprecation notice pointing to `vmsgr send`.
- `vmsgr send` is the preferred launch/message primitive; `vpm` handles install/list/info.
- These control the app lifecycle — they cannot inject D-pad/media keys. Use Method 1/2 for input,
  Method 3 for "open KaviTV / open IPTV Player" from the remote's app grid.

## Method 4: Fire TV HTTPS remote API (port 8080) — NOT on Vega [L]

The reverse-engineered protocol in arinaggarwal1/firestickremote
(https://github.com/arinaggarwal1/firestickremote — `docs/FIRETV_HTTPS_PROTOCOL.md` [C]):
HTTPS on port 8080, static `x-api-key: 0987654321`, PIN pairing (`POST /v1/FireTV/pin/display`
→ PIN on TV → `POST /v1/FireTV/pin/verify` → client token), then
`POST /v1/FireTV?action=dpad_up|home|back…` and `POST /v1/media?action=play|scan`.
Elegant — but it was validated against **Fire OS** devices only.

**Verified live on Seth's Vega stick: port 8080 is NOT listening** (`/proc/net/tcp` shows no
0x1F90 listener). The whole HTTPS remote API is absent on Vega OS. Do not build on it.

## Method 5: DIAL on port 8009 — present on Vega [L]

Port 8009 (0x1F49) IS listening on the Vega stick (verified via `/proc/net/tcp`).
On Fire OS, `POST http://<ip>:8009/apps/FireTVRemote` returns 201 and works as a wake/launch
primitive for the remote service [C]. On Vega its exact behavior is untested [P] —
potentially useful as a wake-up ping, but not a control channel.

## Method 6: Official Fire TV mobile app — works with Vega, protocol unknown [O]/[P]

Amazon's spec sheets list "Fire TV mobile app" as a voice-control/remote option for the
4K Select (Vega) — e.g. https://www.groupon.co.uk/deals/amazon-fire-tv-stick-4k-select-2025-alexa [O].
Pairing is Wi-Fi + 4-digit PIN on the TV (beebom.com guide [C]).
The underlying protocol on Vega is undocumented — on Fire OS it rode the port-8080 HTTPS API,
which doesn't exist on Vega, so Amazon must use a different (proprietary) channel there [P].
Useful as a fallback remote for Seth, but not something we can build on without reverse-engineering.

## Method 7: HDMI-CEC — wrong direction for a phone remote [O]

The stick supports HDMI-CEC Device Control (Settings > Display & Sounds): the TV's remote can
drive the stick, and the stick can power on the TV / switch inputs (in.amazonforum.com, Amazon staff [O]).
But CEC is TV-remote→stick and stick→TV only — a phone cannot inject CEC frames. Not applicable
to the Razr remote. (Volume keys on the Fire TV remote itself go out over CEC to the TV/soundbar,
not to the stick — slideshow-digital docs [C].)

## Method 8: In-app Kepler input APIs — for apps, not remote control [O]

Inside a Vega app: `useTVEventHandler` (HWEvent: up/down/left/right/select/back/playpause/…),
`TVFocusGuideView`, `KeplerBackHandler` (the only way to *consume* Back). These let an app
*receive* remote input, not inject it. Relevant only if the remote drives apps through their
own network APIs (which is Method 9).

## Method 9: Custom Vega app with network listener — the app-aware path [C]

A Vega app can open listeners (tsnet `Listen` proven by looizao/jellyfin-vega-tailnet [C]).
The KaviTV app's planned `/status` + `POST /tune` + `/diag` tailnet endpoint is this pattern:
instead of blind key injection, the remote sends semantic commands ("tune to Horror") and the
app acts natively. Lower latency than key-mashing for app-specific actions, and it works over
the tailnet from anywhere — no LAN/vda needed. Best for: channel changes, playback state,
now/next queries. Blind navigation (arbitrary menus) still needs Method 1/2.

## Community projects (GitHub)

- **arinaggarwal1/firestickremote** — Electron Fire TV remote, reverse-engineered HTTPS protocol
  docs. Fire OS only; protocol absent on Vega. Useful as protocol documentation, not code to reuse.
  https://github.com/arinaggarwal1/firestickremote [C]
- **software-mansion-labs/vega-fast-cli** — persistent inputd-cli REPL server, ms-latency input.
  The pattern to copy for the Razr remote bridge. https://github.com/software-mansion-labs/vega-fast-cli [C]
- **francbonet/adb-mcp-server** — MCP server mapping press_key/tap/swipe/type_text to `inputd-cli`
  on Vega targets; confirms the inputd-cli key model. https://github.com/francbonet/adb-mcp-server [C]
- **thatswiftdev/agent-device** — `tv-remote press <button>`; Vega support limited to virtual device.
  https://github.com/thatswiftdev/agent-device [C]
- **douwebos/conductor** — Vega platform support via stock `inputd-cli` for press-key/tap/swipe.
  https://github.com/douwebos/conductor [C]
- **aksbad007/fire_tv_stick_remote_app** — Android volume remote via ADB; Fire OS assumptions,
  not Vega-applicable. https://github.com/aksbad007/fire_tv_stick_remote_app [C]

## Comparison table

| Method | What it does | Vega works? | Latency | Needs devmode? | Phone-ready? |
|---|---|---|---|---|---|
| inputd-cli via vda shell | full key/text/touch/swipe injection | ✅ [L] | ~1.6s/press (handshake) | yes [O] | via bridge |
| persistent inputd-cli REPL | same, ms-latency | ✅ pattern [C], HW untested [P] | ms | yes | via bridge ✅ |
| vmsgr send / vlcm | launch apps, send messages | ✅ [C] | ~1s | n/a | via bridge |
| HTTPS remote API :8080 | full remote (Fire OS) | ❌ not listening [L] | — | — | no |
| DIAL :8009 | wake/launch primitive | port open [L], behavior untested [P] | low | no | maybe |
| official Fire TV app | full remote + voice | ✅ per spec sheets [O] | low | no | ✅ (proprietary) |
| HDMI-CEC | TV remote → stick | ✅ [O] | n/a | no | ❌ wrong direction |
| in-app Kepler APIs | receive input in-app | ✅ [O] | n/a | no | n/a |
| custom app listener | semantic commands | ✅ [C] | tailnet RTT | no | ✅ |

## Recommended Razr-remote architecture

1. **Semantic layer (primary):** phone → tailnet → KaviTV app's tsnet endpoint (`POST /tune`,
   playback state). No vda, works from anywhere, ms-scale over tailnet.
2. **Blind-input layer (fallback):** phone → tailnet → tiny HTTP bridge on the VM (or on-device
   server per vega-fast-cli) → persistent `inputd-cli` REPL → `button_press KEY_*`.
   Avoids the 1.6s per-press vda handshake. Covers arbitrary menus and non-KaviTV apps.
3. **App launching:** `vmsgr send` (or the semantic endpoint) for the app grid.
4. Keep the official Fire TV mobile app installed as the zero-maintenance fallback.
