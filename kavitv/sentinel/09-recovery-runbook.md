# Recovery Runbook

## Philosophy

```
detect → capture evidence → identify failing layer →
back up if necessary → authorized reversible correction only →
test → verify → document → continue
```

- **Do not blindly restart services because a check failed.** A restart is a
  treatment for a diagnosed cause, not a response to a red light. The
  evidence must point at the component being restarted.
- **Reversible first.** Every automatic action must be undoable. If the fix
  cannot be rolled back, it is not automatic — it is a proposal for Seth.
- **Retest is mandatory.** A recovery without a passing retest of the exact
  failed check is not recovery; it is an attempted recovery, recorded as such.
- **Bounded attempts.** The same automatic action is not retried indefinitely.
  After the bound is hit, hold FAILED and escalate.

## Pre-authorized automatic actions

These — and only these — may be taken by the Sentinel/watchdog without human
approval. Everything else escalates.

| # | Action | Trigger (diagnosed) | Bound | Rollback |
|---|--------|---------------------|-------|----------|
| 1 | Restart KaviTV relay (scheduled task) | Layer 1 FAIL: process down or deep-health FAIL on all channels with relay unresponsive | max 3/hour (existing watchdog v2 bound) | previous relay version kept as `.bak`; task can be reverted |
| 2 | Regenerate schedule (`generate.py`) | Schedule horizon < 2 days (existing watchdog behavior) | once per cycle | previous schedule files retained |
| 3 | Re-run `export_iptv.py` | Metadata validation FAIL: XMLTV unparseable or counts collapsed, and last export is older than the failure | max 1/hour | previous M3U/XMLTV kept as `.bak` |
| 4 | Close dangling Emby test session | Layer 3 teardown finds its own session still open | every run | n/a (cleanup) |

Notes:

- Action 1 exists today in watchdog v2 (bounded restart). The runbook adds
  the diagnosis requirement: restart only when evidence implicates the relay
  process, not on any red.
- Action 3 is new and NOT yet implemented. A bad export can *cause* a
  metadata collapse; re-running the exporter is only correct when the
  evidence shows the export is stale/broken, not when the source data
  (`library.json`) is the problem. If counts collapse right after a fresh
  export, **do not loop the exporter** — escalate.
- No action restarts Emby, modifies Emby libraries/tuners, touches
  credentials, or changes firewall/schedule configuration.

## Procedures

### P1 — Relay down (Layer 1 FAIL)

1. Capture: `test_id`, timestamps, `/api/health` and `/api/deep-health`
   responses (or connection error).
2. Check: is the scheduled task running? Is the port bound by another process?
   (Evidence first — a port conflict is not fixed by a restart.)
3. If diagnosed as relay process failure → Action 1.
4. Post-restart validation per [06](06-monitoring-specification.md).
5. On retest PASS → RECOVERED. On retest FAIL after bound → escalate.

### P2 — Stream degradation (Layer 2 FAIL, Layer 1 PASS)

1. Capture segment-level evidence: which channel, which check
   (empty/malformed/stall/termination), bytes received.
2. Correlate: does deep-health still show advancing bytes? If yes, the relay
   is producing but the playlist/segment path is broken — inspect, don't
   restart yet.
3. One bounded relay restart (Action 1) is permitted if no narrower cause is
   found.
4. Retest Layer 2. Persistent failure → escalate (likely source-media or
   ffmpeg issue needing human eyes).

### P3 — Metadata collapse (counts drop / XMLTV bad, streams fine)

1. Capture: counts before/after, last export timestamp, XMLTV parse error.
2. **Do not restart the relay** — the relay is exonerated by the passing
   stream checks.
3. If last export is old or the XMLTV is malformed → Action 3 (one bounded
   re-export), then re-run metadata validation.
4. If counts collapsed immediately after a *fresh* export → the source data
   or exporter logic is suspect. Do not loop. Escalate with the before/after
   snapshots attached.

### P4 — Emby integration failure (Layer 3 FAIL, Layers 1–2 PASS)

1. Capture: tune/session/playback step that failed, PlayMethod, Emby-side
   state (safe fields only).
2. The relay is exonerated — do not restart it for an Emby-side failure.
3. Check tuner/channel mapping in Emby (read-only inspection).
4. No automatic Emby writes. Escalate with the correlated evidence
   (relay PASS + Emby FAIL is itself the diagnosis: the break is in Emby).

### P5 — Recovery failed / unknown

1. Hold the FAILED state; stop automatic attempts.
2. Dashboard shows "needs human" with layer, reason, evidence, and attempts.
3. Digest RECOVERY section carries it ([11](11-daily-reporting.md)).
4. If CRITICAL (channel loss, program-count collapse), use the immediate
   alert path, not just the morning digest.

## What the runbook never authorizes

- Deleting, moving, renaming, or reorganizing media files (standing rule).
- Emby library/tuner/user changes beyond the read-only checks and the
  test-session cleanup.
- Credential creation, rotation, or exposure.
- Firewall, Tailscale ACL, or network changes.
- Anything irreversible without Seth's explicit approval.
