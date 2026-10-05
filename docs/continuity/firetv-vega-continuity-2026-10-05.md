# Fire TV / Vega continuity note — 2026-10-05

Why this file exists: the Kavi 2.0 → 6.0 handoff did NOT transfer this
knowledge. On 2026-10-05 Kavi 6.0 wrongly "debunked" a real app
(`com.kellner.channels`) because its name looked like an Android package —
but Vega package IDs use reverse-DNS too. The app was real all along:
**KaviTV v0.1.0, installed 2026-10-04.** Rule: verify device claims with
`vpm list packages` on the stick itself. Never trust format-based reasoning.

## The stick
- Fire TV Stick 4K Select (2025), AFTCA002, Vega OS (Linux, NOT Android)
- LAN 10.0.0.151, devmode ENABLED, reachable via tailnet through
  SETHS-PC's 10.0.0.0/24 subnet route
- No APK/ADB. Vega apps are React Native → `.vpkg` (ARMv7)

## How to reach it from this VM
Direct raw TCP is blocked. Use the socat-through-egress-proxy tunnel:
```bash
socat TCP-LISTEN:15555,fork,reuseaddr PROXY:hatch-egress-proxy:10.0.0.151:5555,proxyport=3130 &
VDA=/home/hatch/vega/sdk/vega-sdk/main/0.24.12112/packages/KeplerCLIVegaDeviceAdaptor/KeplerCLIVegaDeviceAdaptor-2.0.14889.0/AL2_x86_64/DEV.STD.PTHREAD/build/bin/vda
$VDA connect 127.0.0.1:15555
$VDA -s 127.0.0.1:15555 shell "vpm list packages"   # full app inventory
$VDA -s 127.0.0.1:15555 shell "vpm info <package>"   # title, version, build
```
On-device tools: `vpm` (install/list/info), `vlcm` (launch/terminate).
Full Vega SDK 0.24.12112 lives at `/home/hatch/vega` (the `vega` CLI
wrapper may not see it — use `vda` + on-device tools directly).

## Prior art (read before building anything Vega)
- Repo: `kellner-dot/firetv-vega` (public) — `docs/VEGA-APP-GENIUS.md`
  is the 2,100-line definitive guide (manifest, media, input, lifecycle,
  storage, debugging). Also `DEPLOYMENT.md`, `TAILNET-SETUP.md`, and the
  Mission Control app source in `app/`.
- Seth's apps on the stick (2026-10-05, 137 packages total): KaviTV,
  Mission Control, KaviTV Console, RVG Agent, Emby Theater (x2),
  IPTV Player, Cloud Drive, Planner, Podcasts, News, Weather, Gallery,
  Radio, Torrent, Pulse, Passman.

## Seth's quality bar for TV apps
Proper apps, not WebView viewers. Launcher tile with 512x512 icon
(no icon = no tile = can't open/pin — this was KaviTV v0.1.0's flaw),
`com.amazon.category.main`, clean Back-to-exit via KeplerBackHandler,
bump version AND build number every submission, never write "Vega"
in Appstore text. Private distribution via Live App Testing.

## Pointers
- Session doc: `docs/sessions/2026-10-05-firetv-vega-app.md` (GitHub
  branch `docs/firetv-vega-app-2026-10-05`)
- Networking research: `~/workspace/research_notes/networking-savant-20261005/`
- Amazon connector: `~/workspace/skills/amazon-appstore/`
