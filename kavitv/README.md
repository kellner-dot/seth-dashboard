# KaviTV — 24/7 Scheduled Streaming Channels for Emby

Three always-on channels (Horror, Experimental, Independent) served to Emby
Live TV via a local relay. Deterministic 7-day schedules, self-healing,
zero AI dependency at runtime.

## How it works

```
generate.py → timeline.json → relay.py (port 8100) → Emby Live TV tuner
```

1. **generate.py** builds a 7-day gapless schedule from `library.json`
   (deterministic SHA256 per-day seeds — same input, same output, no duplicates).
   Writes `timeline.json`, `kavitv.xml` (XMLTV guide), `kavitv.m3u` (playlist).
2. **relay.py** (v2.1) reads `timeline.json`, runs its own ffmpeg per channel,
   serves direct MPEG-TS on `http://<PC_LAN>:8100/kavitv/live/<slug>.m3u8`.
   No HLS session, no PlaySessionId. If a source file is missing, serves a
   slate instead of erroring — the tuner never sees a broken channel.
3. **Emby** tunes the relay URLs as a Live TV tuner. Guide comes from `kavitv.xml`.

## Endpoints (relay, port 8100)

- `/kavitv/live/<slug>.m3u8` → MPEG-TS video stream (200, video/mp2t)
- `/api/health` → basic status (version, ffmpeg, channels)
- `/api/deep-health` → per-channel byte verification (pulls real media bytes,
  checks MPEG-TS sync). This is what the watchdog polls.

## Files

| File | Purpose |
|------|---------|
| `relay.py` | The relay server (v2.1, production) |
| `generate.py` | Schedule generator (stdlib only) |
| `library.json` | Movie pools per channel (14/12/10 movies) |
| `export_iptv.py` | M3U/XMLTV exporter with per-channel logos |
| `channels.json` | Channel metadata for the exporter |
| `kavitv.m3u` / `kavitv.xml` | Generated playlist + guide (do not hand-edit) |
| `logo-{horror,experimental,independent}.jpg` | Per-channel logos (512x512) |

## Configuration

- `KAVITV_WINDOW_DAYS` env (default 7) — schedule horizon
- `KAVITV_FAST_DRIVES` env (default "C,D,T") — movie scan drives
- `KAVITV_LOGO_SRC` env — logo source dir for the exporter
- `config/` — relay runtime config (timeline.json, emby.key, schedules.json)

## Scheduled tasks (on the PC, run as SYSTEM)

- **KaviTV-relay** — starts `relay.py` at boot via pythonw
- **KaviTV Watchdog** — every 5 min: deep-health check, bounded restart
  (max 3/hr), schedule auto-refresh when horizon < 2 days, disk monitoring,
  status.json + dashboard.html

## Recovery

- Relay down → watchdog restarts it (check `logs/watchdog.log`)
- Still down after 3 restarts/hr → manual: `taskkill /F /IM pythonw.exe`,
  then start the "KaviTV-relay" scheduled task
- Rollback: `relay.py.v010-live-20261005.bak` (pre-v2.1)
- Schedule corrupt → delete `config/timeline.json`, watchdog regenerates
- Full procedure: see `KAVI-TV-RECOVERY.md` in Drive (AI-OUTAGE-EMERGENCY-DOCS)

## Ports

- 8100 — KaviTV relay
- 8096 — Emby
- 8899 — RVG agent
- 5244 — Alist (TeraBox backend)

## No secrets in this repo

Emby API key lives in `config/emby.key` on the PC only. RVG tokens in Drive.
Never commit credentials.

## Playback Sentinel

Four-layer stream verification (relay → stream integrity → Emby integration →
client playback) plus a first-class Metadata Sentinel (identity/EPG/logos/
freshness). Canonical 14-doc spec: see `sentinel/` (start with
`sentinel/README.md`; live state in `sentinel/STATUS.md`).
