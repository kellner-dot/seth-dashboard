# Networking App Ideas for Seth — ranked by value × feasibility (2026-10-05)

Grounding: tailnet = SETHS-PC (subnet router, Emby, relay v2.0, RVG) · Razr ·
iPhone · MacBook Air · muse VMs · Fire TV Stick 4K Select on Vega OS (NOT on
tailnet; KaviTV Vega app in build with embedded tsnet + tailnet control
endpoint `/status`, `/tune`, `/diag`).

Review-risk scale for Vega (.vpkg) ideas: **low** = benign utility, no special
permissions · **unknown** = tsnet/networking inside the app, untested with
review · private LAT distribution lowers the stakes for all of these.

---

## 1. KaviTV tailnet control endpoint ⭐ (in build)
**What:** the Vega app exposes `/status` (version, channel, play state, relay
host, last error), `/tune {"channel"}`, `/diag` (recent logs) on the tailnet
via embedded tsnet + WhoIs auth (only Seth's login).
**Who:** Seth (via me/Kavi) — "what's the stick playing?", remote channel
changes, diagnostics without touching the TV.
**Build:** already specified to the build agent (tsnet `Listen` + `WhoIs`
middleware, shared-secret header as belt-and-braces).
**Review risk:** unknown (tsnet in app) — LAT-private, acceptable.

## 2. Phone universal remote (Razr)
**What:** channel buttons (Horror/Experimental/Independent), now-playing +
position, play/pause/seek, relay host switcher — driving the KaviTV control
endpoint and the Emby Sessions API over the tailnet.
**Who:** Seth on the couch; replaces digging through Emby's UI.
**Build:** Android (Kotlin, one activity) or a PWA served from SETHS-PC over
`tailscale serve --set-path` (zero install, always current — start here).
Uses MagicDNS names, never hardcoded IPs.
**Review risk:** n/a (not a Vega app; sideload/PWA).

## 3. Network watchdog → kavi-mail alerts
**What:** watches relay v2.0 health, Emby reachability, and the tailnet path
(`tailscale ping --until-direct=false` to detect DERP-vs-direct per peer);
alerts via kavi-mail when anything degrades. Catches "KaviTV down" before Seth
notices on the TV.
**Who:** runs on SETHS-PC (scheduled task) or this VM (cron).
**Build:** Python, stdlib + `tailscale` CLI JSON parsing. ~200 lines.
**Review risk:** n/a.

## 4. Tailnet dashboard on the Firestick (Vega .vpkg)
**What:** 10-foot view of the tailnet: nodes online/offline, per-peer latency
(direct vs DERP badge), Emby now-playing across the house.
**Who:** Seth glancing at the TV.
**Build:** Vega React Native + tsnet (or plain HTTPS to a tiny status service
on SETHS-PC — simpler, no tsnet review question). Reuse the KaviTV app's
scaffolding.
**Review risk:** low without tsnet; unknown with.

## 5. Remote ops console (web UI on the tailnet)
**What:** single pane: Emby sessions (with play/pause/seek buttons), relay
status + logs, KaviTV timeline (what's on now), tailnet peers + paths, RVG
screenshot. The "mission control" for the whole setup.
**Who:** Seth / Kavi from any tailnet device.
**Build:** small web app on SETHS-PC served via `tailscale serve`; WhoIs-header
auth (localhost-only backend). NOTE: check `~/workspace/seth-dashboard/
mission-control/` first — extend it rather than duplicating.
**Review risk:** n/a.

## 6. One-tap exit-node switcher (Razr)
**What:** Quick Settings tile / widget: toggle exit node on/off, show current
egress IP. For travel on hotel Wi-Fi.
**Who:** Seth on the Razr.
**Build:** Android app using Tailscale's local API (or TailSocks, which already
has per-app exclusion + exit-node switch — evaluate before building).
**Review risk:** n/a. Feasibility note: may be redundant with TailSocks.

## 7. Wake-on-LAN over tailnet
**What:** wake sleeping LAN devices from the phone via an always-on
same-segment sender (WoL is link-local broadcast; SETHS-PC or a Pi sends it on
request over the tailnet).
**Who:** Seth, if/when machines sleep.
**Build:** tiny HTTP endpoint on SETHS-PC → `wakeonlan` to MAC. Trivial.
**Value caveat:** SETHS-PC is always on, so near-zero need today. Build only
if something starts sleeping.

## 8. Taildrop media ingest → Emby
**What:** drop a video on the PC from the phone (`tailscale file cp`), a
watcher auto-imports it into the Emby library and notifies via kavi-mail.
**Who:** Seth adding media from the couch/away.
**Build:** PowerShell/Python watcher on the Taildrop receive dir + Emby
library scan API call.
**Review risk:** n/a.

---

## Ranking (value × feasibility)

| # | Idea | Value | Feas. | Notes |
|---|------|-------|-------|-------|
| 1 | KaviTV control endpoint | 10 | 9 | in build |
| 2 | Phone universal remote | 9 | 8 | start as PWA, zero install |
| 3 | Network watchdog + kavi-mail | 9 | 9 | ~200 lines Python |
| 4 | Tailnet dashboard (Vega) | 7 | 7 | reuse KaviTV scaffolding |
| 5 | Remote ops console (web) | 8 | 7 | check mission-control first |
| 6 | Exit-node switcher | 6 | 8 | TailSocks may already cover |
| 7 | Taildrop ingest | 5 | 7 | nice-to-have |
| 8 | WoL over tailnet | 4 | 8 | no sleeper devices today |

**Suggested order:** 1 (done via build) → 3 (watchdog — protects everything
else) → 2 (remote PWA — daily tactile win) → 5 (console) → 4 (stick dashboard).
