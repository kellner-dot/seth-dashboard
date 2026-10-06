# KaviTV Playback Sentinel — Canonical Technical Specification

> **CORRECTION 2026-10-05 ~19:00 EDT (verified by direct probe):** the live
> relay is **v0.1.0** with the **302-redirect design**. There is **no
> `/api/deep-health` endpoint** (`{"error": "not found"}`). Earlier
> "v2.1/deep-health" claims came from a compacted summary, not live state,
> and are retracted. Where these docs say "deep-health," read it as the
> *check type* (per-channel byte/redirect verification as implemented in
> the deployed `kavitv-sentinel.py`), not a live endpoint. `STATUS.md`
> carries the full correction record.

The Playback Sentinel is the verification system for KaviTV. Its job is to prove,
continuously and with evidence, that a real client can actually watch the channels —
not merely that the relay process answers HTTP.

**The governing rule:** a green relay/API check must never be promoted into a
claim that "KaviTV is working." Playback health and metadata health are separate
dimensions, and each layer of the chain gets its own verdict.

## Document map

| # | Document | What it specifies |
|---|----------|-------------------|
| 01 | [Architecture](01-architecture.md) | The four-layer verification model, components, data flow |
| 02 | [Metadata specification](02-metadata-specification.md) | Metadata Sentinel: identity, EPG, logos, consistency, freshness |
| 03 | [Evidence model](03-evidence-model.md) | Label definitions: VERIFIED / OBSERVED / INFERRED / BLOCKED / FAILED / RECOVERED / NOT BUILT / QUEUED |
| 04 | [Health model](04-health-model.md) | Per-dimension states, overall states, no-promotion rules |
| 05 | [Emby integration](05-emby-integration.md) | Layer 3 design, dedicated test-user approach, channel tests |
| 06 | [Monitoring specification](06-monitoring-specification.md) | Autonomous operation: schedules, tests, escalation, stream-conservation |
| 07 | [Diagnostics and evidence](07-diagnostics-evidence.md) | Per-test record schema, what to log, what to never log |
| 08 | [Dashboard specification](08-dashboard-specification.md) | Local dashboard layout and data source |
| 09 | [Recovery runbook](09-recovery-runbook.md) | Recovery philosophy, authorized actions, procedures |
| 10 | [Implementation plan](10-implementation-plan.md) | What exists, what is designed, what is blocked, build order |
| 11 | [Daily reporting](11-daily-reporting.md) | Morning-digest integration, section formats |
| 12 | [Security](12-security.md) | Credential handling, least privilege, no-secret-logging rules |
| 13 | [TeraBox playback performance](13-terabox-playback.md) | Cloud-playback reliability spec: URL refresh, preflight, recovery, health scoring, fallback, telemetry |
| — | [STATUS](STATUS.md) | Current state: verified facts, per-layer implementation state |

## The four layers in one paragraph

- **Layer 1 — Infrastructure / relay.** Is the relay alive and serving?
  (Exists today via `/api/health` plus per-channel 302-redirect verification
  in the deployed sentinel.)
- **Layer 2 — Stream integrity.** Is the stream a client could receive actually
  playable — valid segments, continuity, advancing bytes, no stalls? (Script written,
  deployment pending.)
- **Layer 3 — Emby integration.** Can Emby tune, session, and play each channel
  through the normal pathway, verified with a dedicated non-admin test user?
  (Designed; blocked on test-user creation.)
- **Layer 4 — Client playback.** Does a real Emby client render picture and sound?
  (Manual verification by Seth; blocked until Layer 3 works.)

Plus the **Metadata Sentinel** — a first-class dimension covering channel identity,
EPG/XMLTV, logos, cross-system consistency, and freshness — which can fail
independently of every layer above.

## Superseded documents

- `playback-sentinel-design-2026-10-05.md` — early Layer 1–4 sketch; superseded by
  [01](01-architecture.md) and [10](10-implementation-plan.md).
- `playback-sentinel-metadata-design-2026-10-05.md` — early metadata sketch;
  superseded by [02](02-metadata-specification.md).

## Implementation note (2026-10-05 ~19:15 EDT, Kavi 4.0)

`kavitv-sentinel.py` (three levels: infrastructure → Emby integration →
synthetic client playback) is **deployed and scheduled** on Seth's PC
(`C:\Users\sethr\kavitv\`), not a superseded prototype: tasks
`KaviTV-Sentinel-Infra` (5 min), `KaviTV-Sentinel-Emby` (30 min),
`KaviTV-Sentinel-Full` (daily 04:00 + escalation retests). It implements the
Layer 3 test procedure from [05](05-emby-integration.md) verbatim; the only
delta from the spec is auth via the existing server API key instead of a new
dedicated test user (no new credential created; Option B queued as hardening
pending Seth's approval). Source of truth for the script:
`~/workspace/goals/kavitv-emby-logo/files/kavitv-sentinel.py` (deployed copy
SHA256-verified on upload).

## Related canonical documents (outside this folder)

- `kavitv-storage-architecture-2026-10-05.md` — storage rules and failure modes
- `emby-library-baseline-2026-10-05.md` — Emby library paths baseline
- `emby-transcode-decision-tree-2026-10-05.md` — GPU/transcode decisions, iGPU
  production state, stability lock
- Repository: `kellner-dot/seth-dashboard` → `kavitv/` (relay.py, generate.py,
  export_iptv.py, kavitv.m3u, kavitv.xml, README.md, relay-deploy.md)
