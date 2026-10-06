# Monitoring Specification — Autonomous Operation

## Goal

The Sentinel operates autonomously on Seth's PC: it checks, tests, records
evidence, recovers safely where authorized, retests, and escalates when it
cannot recover. It does not depend on any Kavi being online.

## Check tiers

| Tier | What runs | Cadence | Cost |
|------|-----------|---------|------|
| Infra (lightweight) | Layer 1: TCP probe, `/api/health`, `/api/deep-health`; Emby server reachability (unauthenticated); disk space | every 5 min (existing watchdog v2) | negligible |
| Stream integrity (sampled) | Layer 2: playlist + N segments per channel, continuity, advancing bytes | every 30 min | ~1–2 min of stream sampling per channel |
| Metadata validation | Metadata Sentinel: M3U/XMLTV parse, mapping, logos, freshness, counts | every 30 min (with Layer 2) + after every `export_iptv.py` run | negligible (file reads + a few HTTP HEADs) |
| Emby integration (sampled) | Layer 3: full three-channel test-user playback test | every 6 hours | ~3–5 min, one session per channel, auto-closed |
| Full test | Layers 1+2+3 + metadata, all channels | daily + on escalation | ~10 min |

### Stream-conservation rule

Do **not** continuously consume live streams. Layer 2 and Layer 3 are sampled
tests with bounded duration. Between tests, no stream is held open. The relay's
slate fallback and ffmpeg processes are unaffected by sampling.

## Post-restart validation

After any relay restart (watchdog-initiated or manual):

1. Wait for `/api/health` → ok.
2. Run Layer 1 deep-health immediately.
3. Run one Layer 2 sampled test per channel.
4. Run metadata validation (restart can coincide with schedule regeneration).
5. Record results as the post-restart validation set. If any fail, follow the
   recovery runbook ([09](09-recovery-runbook.md)) — do not assume the restart
   fixed everything.

## Failure detection

- **Consecutive-failure counting:** a single failed sample is recorded but does
  not alert; alert on N consecutive failures (default N=2 for infra, N=1 for
  CRITICAL metadata regressions like channel/program count collapse).
- **Flap detection:** rapid PASS/FAIL oscillation is recorded as its own
  condition (flapping) rather than spamming alerts.
- **Regression detection:** counts (channels, programs, logos) compared against
  last verified snapshot; sudden drops alert immediately even if all stream
  checks pass.

## Evidence capture

Every run writes to `sentinel-results.json`
(`C:\Users\sethr\kavitv\`, mirror to `T:\KaviTV\` best-effort):

- Per-tier, per-channel, per-layer results with evidence labels
  ([07](07-diagnostics-evidence.md) for the record schema).
- Consecutive-failure counters, last PASS timestamp, last FAIL reason.
- The record is append-only history plus a rolling current-state section.

## Safe, reversible recovery

On failure, the Sentinel follows [09](09-recovery-runbook.md):

detect → capture evidence → identify failing layer → back up if necessary →
authorized reversible correction only → test → verify → document → continue.

- The only automatic corrections permitted are the pre-authorized,
  reversible ones in the runbook (e.g. bounded relay restart, max 3/hour —
  already implemented in watchdog v2).
- The Sentinel never blindly restarts services because a check failed; it
  restarts a specific component for a diagnosed reason, then retests.
- Anything destructive, irreversible, or outside the runbook's authorized
  list → escalate, do not act.

## Retest after recovery

Every recovery action is followed by re-running the exact test that failed.
RECOVERED is recorded only on a passing retest ([03](03-evidence-model.md)).

## Escalation when recovery fails

If recovery fails or the failure is outside authorized actions:

1. Record FAILED with layer, reason, evidence, and recovery attempts.
2. Write the escalation into `sentinel-results.json` and the dashboard.
3. Surface in the next morning digest ([11](11-daily-reporting.md)) under
   RECOVERY, and immediately via the existing alert path if CRITICAL
   (channel loss, program-count collapse).
4. Do not retry indefinitely: bounded attempts, then hold the FAILED state
   with a clear "needs human" flag rather than churning.

## Schedules live in Task Scheduler

All Sentinel schedules are Windows scheduled tasks (SYSTEM where no user
context is needed), consistent with the existing KaviTV-relay and
KaviTV-Watchdog tasks. The Sentinel must survive reboot and PC sleep/wake
the same way the relay does.
