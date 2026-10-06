# Local Dashboard — Specification

## Purpose

A single local HTML page on Seth's PC showing the true state of KaviTV at a
glance — five dimensions plus overall state, with evidence labels, so a green
relay can never masquerade as a working system.

## Location and refresh

- `C:\Users\sethr\kavitv\sentinel-dashboard.html` (alongside the existing
  watchdog `dashboard.html`; may be merged later — for now, separate pages,
  separate jobs).
- Regenerated at the end of every Sentinel run; auto-refresh 60s via meta tag.
- Read from `sentinel-results.json`; no live probing from the page itself.

## Layout

### Header

- Overall state (one of [04](04-health-model.md): FULLY VERIFIED / PLAYBACK
  VERIFIED / METADATA DEGRADED / METADATA VERIFIED / PLAYBACK DEGRADED /
  INFRASTRUCTURE ONLY / FAILED), with timestamp of the determination.
- One-line plain-language summary ("Relay healthy, stream playable, Emby not
  yet tested — infrastructure only").

### Per-channel table

One row per channel (horror, experimental, independent). Minimum columns:

| Column | Content |
|--------|---------|
| Channel | name + Emby channel number |
| Infrastructure | Layer 1 verdict + evidence label |
| Stream integrity | Layer 2 verdict + evidence label |
| Metadata | metadata verdict (identity/EPG/logos/freshness rollup) |
| Emby | Layer 3 verdict + evidence label |
| Playback | Layer 4 verdict (human sign-off state) |
| Last successful test | timestamp per dimension |
| Last failure | timestamp + failing check |
| Consecutive failures | counter per dimension |
| Failure reason | human sentence |
| Last test duration | ms |

Cells show verdict + evidence label together, e.g. "PASS (VERIFIED)" vs
"PASS (INFERRED)" — the label is what keeps an inference from looking like
proof.

### Metadata panel

- Channel count (3), program count (~157), logos OK (3/3), EPG age per channel.
- M3U and XMLTV refresh timestamps.
- Count-trend sparkline or last-10 values (catches slow decay, not just cliffs).

### Recovery panel

- Current incidents (FAILED states with layer + reason).
- Recovery actions taken with timestamps and outcomes.
- Escalations awaiting human attention.

### Footer

- Sentinel version, config summary (cadences), link to this spec folder.

## Data source contract

The dashboard renders **only** what is in `sentinel-results.json`. It performs
no independent checks. If the JSON is stale, the dashboard says so
("data age: 47 min — STALE") rather than showing old greens as current.

## Non-requirements

- No authentication (local file on his PC; not served beyond it).
- No secrets displayed (there are none in the JSON by construction — [07](07-diagnostics-evidence.md)).
- No controls that change the system (dashboard is read-only; recovery is the
  runbook's job, [09](09-recovery-runbook.md)).
