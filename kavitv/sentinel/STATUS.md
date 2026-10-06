# Sentinel — Current Status (STATUS.md)

*Last updated: 2026-10-05 ~19:40 EDT (Kavi 4.0). This document is the honest
state of the Sentinel. It changes only when a test runs or a component ships.*

## Monitoring baseline acceptance (2026-10-05 ~19:04 EDT, KAVI-TEAM / SETH)

ACCEPTED: KaviTV automated monitoring baseline VERIFIED and production.
Infra 5min / Emby 30min / full playback daily 04:00 / metadata daily 05:00 /
digest 08:30. Operating rule: detect → capture evidence → classify →
determine cause → recover only when authorized/safe → retest → verify →
document → update state. No blind restarts. Human visual check: PENDING, not
a failure, do not repeatedly escalate. Next priority: backup/restore (#1).

## Acceptance record (2026-10-05 ~19:01 EDT)

Automated Sentinel layers VERIFIED against the evidence below. Human visual
playback recorded as PENDING (not FAILED, not blocking). Test user QUEUED as
optional hardening (not a blocker; do not create without authorization). Relay
v0.1.0 / 302 design confirmed authoritative. Credential handling: existing
server API key only, no new credential created.

Note: Seth has not yet reviewed this acceptance record in-chat. Treat it as
Kavi-4-verified pending his review, not as his sign-off.

Verification boundary (standing): AUTOMATED PLAYBACK = VERIFIED;
REAL HUMAN CLIENT VISUAL PLAYBACK = PENDING HUMAN CHECK. Do not promote one
into the other in either direction.

## Verification evidence (full three-channel test, 2026-10-05)

| Channel | Time (EDT) | Segments | Bytes | Sync | Advancing | Session | PlayMethod | Verdict |
|---------|-----------|----------|-------|------|-----------|---------|------------|---------|
| horror | 18:55:15 | 4 | 1,967,420 | 0x47 ok | yes | alive, clean close | Transcode | KaviTV verified end-to-end. |
| experimental | 18:55:51 | 4 | 6,506,492 | 0x47 ok | yes | alive, clean close | Transcode | KaviTV verified end-to-end. |
| independent | 18:57:34 | 4 | 8,106,936 | 0x47 ok | yes | alive, clean close | Transcode | KaviTV verified end-to-end. |

Evidence: `C:\Users\sethr\kavitv\logs\sentinel\sentinel-20261005.jsonl`
(test_id per channel-test; no credentials). No ffmpeg processes remained
after the tests; no dangling playback sessions (device entries age out).

## Overall system state

**INFRASTRUCTURE ONLY** — per Seth's binding order 2026-10-05 ~19:05 EDT.
Do not promote higher until the required evidence exists (his acceptance of
the evidence bar).

Note on the automated evidence: the deployed sentinel's per-layer tests do
pass (3/3 channels "verified end-to-end" with segment evidence 2026-10-05
~18:55–18:58 EDT; metadata VERIFIED ~19:05 EDT). Those per-layer results
stand as recorded test outcomes. The *overall system state*, however, is
held at INFRASTRUCTURE ONLY by his explicit order — automated results are
not promoted into a system-wide "working" claim without his review.

## Corrections to earlier entries (2026-10-05 ~19:15 EDT, verified by probe)

Earlier entries below were written from a compacted summary, not from live
probes. Direct probing on 2026-10-05 ~18:44–19:00 EDT established:

- **The live relay is v0.1.0 with the 302-redirect design** (VERSION="0.1.0"
  in `C:\Users\sethr\kavitv\relay.py`; `/kavitv/live/<slug>.m3u8` → 302 to
  Emby's own HLS URL). There is **no `/api/deep-health` endpoint** on the
  live relay (returns `{"error": "not found"}`). Claims of a "v2.1 cutover"
  and "deep-health VERIFIED" were incorrect and are retracted.
- **Segments require the PlaySessionId.** Playlist without it → segment
  URLs carry an empty `PlaySessionId=` → HTTP 400. Playlist fetched WITH the
  PlaySessionId from PlaybackInfo → segments HTTP 200 with real MPEG-TS
  bytes (verified: 0x47 sync, advancing hashes). This is the mechanism the
  Sentinel's synthetic client uses.
- **No dedicated Emby test user is required.** `POST /emby/Items/{channelId}/
  PlaybackInfo` works with the existing server API key; sessions, progress
  reporting, and clean close all verified. The Option B test user remains a
  valid least-privilege hardening step but is NOT a blocker — Layer 3 is
  implemented and passing without it.

## Existing verified state (preserved facts)

- **Relay v0.1.0 serves the 302-redirect design on all 3 channels.** VERIFIED
  2026-10-05 ~19:00 EDT by direct probe (VERSION="0.1.0"; /api/health ok;
  /api/deep-health does not exist — earlier "v2.1/deep-health" claims retracted).
- **KaviTV is operational** at the infrastructure layer: relay v0.1.0 live on
  port 8100, watchdog v2 every 5 min as SYSTEM, 7-day schedule horizon.
- **Metadata/logo pipeline is deployed:** 3/3 channels have correct individual
  logos in Emby (hash-verified 2026-10-05); 157 programs; `export_iptv.py`
  preserves per-channel logos on refresh.
- **Emby is healthy in the correct interactive session** (Session 1 as sethr,
  verified after the 15:56–15:58 EDT incident recovery).
- **iGPU remains the production GPU.** RX 7600 experiment fully rolled back
  (Seth-confirmed). No production GPU change.
- **EmergencyKit is deployed and verified** at `C:\Tools\EmergencyKit\`
  (11 scripts, health check ALL GREEN).
- **Stability lock remains in force.** UbuWeb metadata production changes
  QUEUED behind it.

## Per-layer implementation state

| Layer | State | Detail |
|-------|-------|--------|
| Layer 1 — relay/infra | VERIFIED | `kavitv-sentinel.py` L1: port 8100, /api/health, per-channel 302 → Emby HLS URL, playlist fetchable + bytes changing. Scheduled every 5 min (`KaviTV-Sentinel-Infra`, SYSTEM). |
| Layer 2 — stream integrity | VERIFIED | Covered inside the sentinel: L1 byte-change checks + L3 per-segment TS-sync/advancing-hash/zero-byte/stall detectors. No separate script needed. |
| Metadata Sentinel | VERIFIED | `sentinel-metadata.py` fixed (paths + tolerant M3U parser) and passing on PC 2026-10-05 ~19:05 EDT: identity PASS, EPG PASS (157 programs), logos PASS (3/3 image/jpeg), cross-system PASS, freshness PASS (3.6h). Re-verified ~19:25 EDT (all 5 dimensions PASS → "METADATA VERIFIED"). Scheduled daily 05:00 (`KaviTV-Sentinel-Metadata`, SYSTEM); results → `sentinel-metadata.json` |
| Layer 3 — Emby integration | VERIFIED (deployed 2026-10-05 ~19:00 EDT) | `kavitv-sentinel.py` L2+L3: PlaybackInfo → Playing → session-keyed HLS → 4 segments/channel verified → Progress → Stopped. 3/3 channels "KaviTV verified end-to-end." Auth: existing server API key from `config/emby.key` (no new credential). Option B dedicated test user = queued hardening, needs Seth's approval (credential-creation boundary). Baseline PlayMethod: Transcode on all 3 channels. Scheduled: Emby check every 30 min, full 3-channel test daily 04:00 + escalation retests. |
| Layer 4 — client playback | NOT BUILT + BLOCKED | By design manual; blocked on Seth's visual test |
| Results aggregation | VERIFIED | Per-test JSONL evidence in `C:\Users\sethr\kavitv\logs\sentinel\` (no credentials); `sentinel-state.json`; verdicts use the exact required messages |
| Dashboard | VERIFIED | `C:\Users\sethr\kavitv\sentinel-dashboard.html` (self-contained, 60s refresh, per-channel table + detail) |
| Recovery actions 1–2 | VERIFIED | watchdog v2 bounded restart + schedule regen live |
| Recovery actions 3–4 | PARTIAL | Sentinel: layer attribution, bounded retest (1 retry + 1/hr escalation), no blind restarts. Spec [09](09-recovery-runbook.md) remains the reference |
| Digest integration | NOT BUILT | Spec [11](11-daily-reporting.md) complete |

## Known issues

1. ~~`sentinel-metadata.py` path bug~~ RESOLVED 2026-10-05 ~19:05 EDT —
   paths corrected to `C:\Users\sethr\workspace\seth-dashboard\kavitv\` and
   M3U parser made tolerant of missing `tvg-name`; verified METADATA VERIFIED
   on the PC. Recurring schedule for the metadata check: QUEUED.
2. ~~`sentinel-layer2.py` not yet deployed to PC (chunked upload needed).~~
   RESOLVED 2026-10-05 ~19:15 EDT — stream-integrity checks are implemented
   inside the deployed `kavitv-sentinel.py` (L1 + L3); no separate script.
3. ~~Layer 3 blocked on test-user creation — Seth's action (or admin API key
   via Secure Vault).~~ RESOLVED 2026-10-05 ~19:15 EDT — Layer 3 implemented
   with the existing server API key (verified, no new credential). Dedicated
   test user (Option B) remains a queued least-privilege hardening step;
   creating it is a credential-creation action needing Seth's approval.

## Unblockers and owners

| Blocker | Owner | Unblocks |
|---------|-------|----------|
| Manual visual Emby test of 3 channels | Seth | Layer 4 sign-off |
| Fix metadata script paths | Kavi 4 | RESOLVED 2026-10-05 ~19:05 EDT — recurring schedule QUEUED |
| Approve dedicated Emby test user (Option B) | Seth | Least-privilege hardening of Layer 3 auth |
