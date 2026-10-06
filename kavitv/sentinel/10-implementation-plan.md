# Implementation Plan

## Build order

1. **Layer 2 deployment** — deploy `sentinel-layer2.py` to PC, schedule it,
   wire results into `sentinel-results.json`. (Script written; deployment
   pending — chunked upload needed after RVG exec 400 on large payload.)
2. **Metadata script fix** — fix `sentinel-metadata.py` paths (M3U/XMLTV live
   at `C:\Users\sethr\workspace\seth-dashboard\kavitv\`), verify output,
   schedule it.
3. **Results aggregation** — `sentinel-results.json` writer + per-dimension
   verdicts + overall-state computation per [04](04-health-model.md).
4. **Dashboard** — `sentinel-dashboard.html` per [08](08-dashboard-specification.md).
5. **Test user** — unblock Layer 3 (Seth's action), then build the Layer 3
   tester per [05](05-emby-integration.md).
6. **Recovery wiring** — implement runbook actions 3–4 and the escalation
   path ([09](09-recovery-runbook.md)); action 1–2 already exist in watchdog v2.
7. **Digest integration** — Sentinel sections in the morning digest
   ([11](11-daily-reporting.md)).
8. **Layer 4 sign-off** — Seth's manual visual test after Layer 3 works.

## Component states (2026-10-05, corrected by direct probe ~19:00 EDT)

| Component | State | Evidence |
|-----------|-------|----------|
| Relay | VERIFIED (v0.1.0, 302 design) | `/api/health` ok; `/api/deep-health` does NOT exist (earlier "v2.1" claim retracted) |
| Layer 1 (relay health) | VERIFIED | `kavitv-sentinel.py` infra mode: port, /api/health, per-channel 302, playlist byte-change. Task `KaviTV-Sentinel-Infra` every 5 min |
| Layer 2 (stream integrity) | VERIFIED (inside sentinel) | Covered by sentinel L1 byte-change + L3 per-segment TS-sync/advancing-hash/stall detectors. Standalone `sentinel-layer2.py` NOT deployed (superseded, not needed) |
| Metadata Sentinel | VERIFIED | `sentinel-metadata.py` fixed + passing on PC 2026-10-05 ~19:05 EDT (identity/EPG 157/logos 3-3/cross-system/freshness all PASS). Task `KaviTV-Sentinel-Metadata` daily 05:00 |
| Layer 3 (Emby integration) | VERIFIED | `kavitv-sentinel.py`: PlaybackInfo → Playing → session-keyed HLS → 4 segments/channel → Progress → Stopped. 3/3 "verified end-to-end." Existing server API key (no new credential). Tasks: Emby 30 min, Full daily 04:00 |
| Layer 4 (client playback) | NOT BUILT + BLOCKED | By design manual; blocked on Seth's visual test |
| Results aggregation | VERIFIED | JSONL per-test evidence `logs/sentinel/`, `sentinel-state.json` |
| Dashboard | VERIFIED | `sentinel-dashboard.html` on PC (60s refresh) |
| Recovery runbook actions 1–2 | VERIFIED | watchdog v2 bounded restart + schedule regen live |
| Recovery runbook actions 3–4 | PARTIAL | Sentinel: layer attribution + bounded retest, no blind restarts. Spec [09](09-recovery-runbook.md) remains the reference |
| Digest integration | NOT BUILT | Spec [11](11-daily-reporting.md) complete; digest cron updated with 22-section format |

## Do-not-fake rule

A component is not marked complete because its architecture is documented.
The table above is the truth; the specs are the plan. The overall system
state stays INFRASTRUCTURE ONLY until Layers 2–3 verify for real.

## Constraints in force

- **Stability lock** (2026-10-05): no production changes beyond the Sentinel
  build-out and its fixes. Emby interactive session, AMF, transcode-temp on
  C:, library paths — all frozen.
- **Standing movie rule:** never move, delete, reorganize, or rename media
  files on C:/D:/T:.
- **T: is best-effort cloud:** Sentinel mirrors may use `T:\KaviTV\`; nothing
  may depend on it.
- **UbuWeb metadata production changes:** QUEUED behind the stability lock.
