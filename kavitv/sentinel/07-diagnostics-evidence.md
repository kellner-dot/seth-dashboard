# Diagnostics and Evidence — Record Schema

## Principle

Every test records enough to diagnose the failure later without re-running
it — and never records secrets. If a field would contain a password, API key,
token, cookie, or session secret, it is omitted or replaced with a
non-sensitive descriptor (e.g. `auth: ok`, `session: active`).

## Per-test record

Each test execution writes one record with these fields:

| Field | Description |
|-------|-------------|
| `timestamp` | ISO-8601, America/New_York |
| `test_id` | Unique ID per execution (e.g. `l2-horror-20261005-190201`) |
| `channel` | horror / experimental / independent (or `all`) |
| `layer` | 1 / 2 / 3 / 4 / metadata |
| `check` | Specific check name (e.g. `segment-continuity`, `xmltv-parse`, `emby-tune`) |
| `result` | PASS / FAIL / WARN |
| `evidence` | Evidence label: VERIFIED / OBSERVED / INFERRED / BLOCKED / FAILED / RECOVERED / NOT BUILT / QUEUED |
| `duration_ms` | Wall-clock duration of the test |
| `bytes_received` | Bytes/segments received (counts and sizes, never content) |
| `segments_checked` | Number of segments sampled (Layer 2/3) |
| `emby_session` | Safe session info only: session active yes/no, PlayState, position ticks — no IDs that are secrets, no tokens |
| `play_method` | DirectPlay / DirectStream / Transcode / n/a |
| `metadata_state` | Counts snapshot: channels, programs, logos-ok, epg-age-hours |
| `failure_reason` | Machine-readable reason + human sentence (only on FAIL/WARN) |
| `failing_layer` | Which layer the evidence points to |
| `recovery_action` | What was done (only if recovery attempted), from the authorized list |
| `final_result` | Post-recovery retest outcome |

## What is safe to record (Emby session info)

- Session active: yes/no
- PlayState: Playing / Paused / Stopped
- PositionTicks / progress counters
- PlayMethod
- Channel number and name being tested

## What is NEVER recorded

- Passwords (including the test-user password)
- API keys
- Session tokens / PlaySessionId values
- Cookies
- Any credential from the OS store or Secure Vault
- Full HTTP Authorization headers

If a diagnostic would be more useful with a secret in it, the answer is a
better non-secret diagnostic (timing, counters, state names), not the secret.

## Storage

- `sentinel-results.json` at `C:\Users\sethr\kavitv\` — rolling current state
  + append-only run history (bounded, e.g. last 500 runs).
- Best-effort mirror to `T:\KaviTV\sentinel-results.json` (cloud; never a
  dependency — see storage architecture doc).
- Logs are plain text/JSON; no binary blobs.

## Retention

- Current-state section: always fresh (overwritten each run).
- Run history: last 500 executions or 30 days, whichever is smaller.
- Incident records (FAILED → RECOVERED chains): kept 90 days for trend review.
