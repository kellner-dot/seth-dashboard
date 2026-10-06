# Playback Sentinel — Architecture

## Purpose

Verify the end-to-end playback chain for KaviTV's three channels with recorded
evidence at each layer, so a failure is localized to the layer that actually
broke instead of surfacing as a vague "TV is down."

## System under test

- **Relay v0.1.0** (`C:\Users\sethr\kavitv\relay.py`, port 8100) — 302-redirect
  design: `/kavitv/live/<slug>.m3u8` → 302 to Emby's session-keyed HLS URL.
  (No `/api/deep-health` endpoint; earlier "v2.1" claims retracted 2026-10-05.)
- **Channels:** horror, experimental, independent
  (Emby channel IDs 470348 / 470349 / 470350)
- **M3U:** `http://10.0.0.98:8100/kavitv/live/<slug>.m3u8`
- **Guide data:** `kavitv.m3u` + `kavitv.xml` (XMLTV), 157 programs
- **Watchdog v2** (`kavitv-watchdog.ps1`, every 5 min as SYSTEM) — health
  checks, bounded restart, schedule horizon, Emby health, disk monitoring,
  `status.json` (local + `T:\KaviTV\` mirror), `dashboard.html`
- **Deployed sentinel** (`kavitv-sentinel.py`, 3 SYSTEM tasks: Infra 5 min /
  Emby 30 min / Full daily 04:00 + Metadata daily 05:00) — per-channel
  302 verification, PlaybackInfo → session-keyed HLS → segment verification,
  JSONL evidence in `logs/sentinel/`, `sentinel-dashboard.html`

## The four layers

### Layer 1 — Infrastructure / relay

Answers: *is the relay alive and serving?*

The live relay is **v0.1.0** with the **302-redirect design**: `/api/health`
exists; there is **no `/api/deep-health` endpoint** (verified 2026-10-05 —
earlier "v2.1/deep-health" claims were incorrect and are retracted).

| Check | Source | Evidence |
|-------|--------|----------|
| Relay process listening on :8100 | TCP probe | connection accepted/refused |
| `/api/health` → ok | HTTP 200 + body | `ok:true`, `version:"0.1.0"`, channel list |
| Per-channel 302 redirect live | `GET /kavitv/live/<slug>.m3u8` → 302 | redirect target is Emby's session-keyed HLS URL |
| Redirect target fetchable | playlist fetchable, bytes changing between fetches | proves the relay resolves the current program |
| Channel availability | all three slugs respond | 3/3 reachable |

Implemented in the deployed `kavitv-sentinel.py` (infra mode, every 5 min):
port check, `/api/health`, per-channel 302 verification, playlist fetch × 2
with byte-change detection.

**What Layer 1 cannot prove:** that the bytes form a playable stream, that Emby
can tune it, or that a client renders it. A Layer 1 PASS is necessary but never
sufficient for an overall "working" verdict.

### Layer 2 — Stream integrity

Answers: *would a client actually be able to play this?*

Simulates what a client does, without needing Emby:

1. Fetch the HLS/M3U8 playlist from `/kavitv/live/<slug>.m3u8`.
2. Fetch N consecutive segments.
3. Verify each segment:
   - Non-empty, valid MPEG-TS (sync byte `0x47`, 188-byte packet alignment).
   - Contains audio + video PIDs (not just null packets).
   - Segment hashes differ between fetches (bytes are *advancing*, not a stuck buffer).
4. Detect: malformed or empty segments, stalls (no new bytes), premature
   termination, redirect loops, HTTP errors (4xx/5xx).
5. Verify playlist updates: new segments appear, old ones rotate (live edge moves).
6. Measure: time-to-first-segment, segment fetch latency, bitrate stability,
   stream duration observed.

**Status:** VERIFIED as implemented inside the deployed `kavitv-sentinel.py`
(L1 playlist byte-change checks + L3 per-segment TS-sync / advancing-hash /
zero-byte / stall detectors, 4 segments/channel in full mode). The standalone
`sentinel-layer2.py` reference implementation was superseded — not deployed,
per the anti-duplication rule.

**Design constraint:** do not continuously consume live streams. Layer 2 runs
periodic sampled tests (see [06](06-monitoring-specification.md)), not a
persistent pull.

### Layer 3 — Emby integration

Answers: *can Emby tune, session, and play the channel through the normal pathway?*

For each channel, independently, authenticated as the dedicated non-admin test
user (see [05](05-emby-integration.md)):

1. Authenticate as test user; confirm only the three KaviTV channels are visible.
2. Resolve channel/tuner: channel appears in Emby Live TV with expected
   number/name/ID.
3. Initiate playback through the normal pathway (PlaybackInfo → session-keyed
   stream), the same calls a real client makes.
4. Confirm a playback session is created and maintained (session present in
   Emby sessions, PlayState sane).
5. Verify media flow: bytes/segments arriving through the session, not just
   HTTP 200 on the API.
6. Record PlayMethod (DirectPlay / DirectStream / Transcode) per channel.
7. Detect stalls, errors, restarts during the test window; report progress and
   session state.
8. Correlate result with relay state: if Emby fails while relay is healthy, the
   failure is isolated to the Emby layer (tuner mapping, session handling,
   transcode).
9. Auto-stop the session cleanly afterward — no dangling tuner sessions.
10. Never log the password, tokens, cookies, or session secrets
    (see [12](12-security.md)).

**Status:** NOT BUILT. BLOCKED on test-user creation (needs Emby admin API key
or Seth creating the user via Dashboard). Approach selected: Option B —
dedicated non-admin test user.

### Layer 4 — Actual client playback

Answers: *does a real Emby client render picture and sound?*

- Play each channel in a real Emby client (web/app/TV).
- Confirm audio + video, no sustained buffering or freezing.
- Confirm the program shown matches the EPG "now playing."
- This is **final human verification**, clearly distinguished from all
  server/API health. Server checks can be green while rendering fails
  (codec, client, network-to-client issues).

**Status:** NOT BUILT as automation (by design). BLOCKED on Seth's manual
visual test, which follows a working Layer 3. Layer 4 is a human sign-off,
not a script.

## The Metadata Sentinel (first-class dimension)

Runs alongside the four layers, not inside them. Covers channel identity,
EPG/XMLTV, logos, cross-system consistency (M3U ↔ XMLTV ↔ Emby), and freshness.
Full specification: [02](02-metadata-specification.md).

Key property: metadata can fail while every playback layer passes, and playback
can fail while metadata is perfect. The overall verdict keeps them separate
(see [04](04-health-model.md)).

## Data flow

```
Relay :8100 ──/api/health, per-channel 302──▶ Layer 1 checks
     │
     └──/kavitv/live/<slug>.m3u8──▶ Layer 2 checks (segment sampling)
                                        │
Emby :8096 ──Live TV / sessions API─────▶ Layer 3 checks (test-user pathway)
     │
     └──real client─────────────────────▶ Layer 4 (human verification)

kavitv.m3u + kavitv.xml ──parse + cross-check──▶ Metadata Sentinel
     │
     └──all results──▶ sentinel-results.json ──▶ dashboard + digest + alerts
```

## Components and where they run

| Component | Runs on | Trigger |
|-----------|---------|---------|
| relay.py v0.1.0 (/api/health; 302-redirect design) | Seth's PC, SYSTEM scheduled task "KaviTV-relay" | always-on |
| kavitv-watchdog.ps1 (infra) | Seth's PC, SYSTEM scheduled task every 5 min | schedule |
| kavitv-sentinel.py (Layers 1–3) | Seth's PC, 3 SYSTEM tasks: Infra 5 min / Emby 30 min / Full daily 04:00 | schedule |
| sentinel-metadata.py | Seth's PC, SYSTEM task `KaviTV-Sentinel-Metadata` daily 05:00 | schedule |
| sentinel-results.json / logs/sentinel/*.jsonl | `C:\Users\sethr\kavitv\` (+ `T:\KaviTV\` mirror best-effort) | written by each run |
| sentinel-dashboard.html | `C:\Users\sethr\kavitv\` | 60s refresh |
| Morning digest | Kavi agent cron | daily ~8:30 AM ET |

## Non-goals

- The Sentinel does not fix Emby, transcode settings, or client apps; it
  detects, captures evidence, and (where authorized) performs safe reversible
  recovery per [09](09-recovery-runbook.md).
- The Sentinel does not replace Seth's eyes on Layer 4.
- The Sentinel never stores or logs credentials ([12](12-security.md)).
