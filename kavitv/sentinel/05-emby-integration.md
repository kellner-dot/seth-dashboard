# Emby Integration — Layer 3 Specification

## Purpose

Verify that Emby itself — not just the relay behind it — can tune, session,
and play each KaviTV channel through the exact pathway a real client uses.
This is the layer that catches tuner-mapping failures, session failures, and
transcode failures that are invisible to relay-level checks.

## Selected approach: dedicated non-admin test user (Option B)

Layer 3 authenticates as a **dedicated non-admin Emby test user**, restricted
to the three KaviTV channels with minimum required permissions.

### Account requirements

- Non-admin. No administrator, library-management, or user-management access.
- Visible libraries/channels: the three KaviTV channels only
  (same allowlist mechanism used for Chelsea's login).
- Minimum permissions needed to browse Live TV and start playback; nothing else.
- Purpose-built for automated testing; never used for real watching.

### If Emby cannot restrict tightly enough

If Emby cannot provide sufficient channel-level restriction for the test user,
**stop and document the limitation** rather than weakening security. Do not
fall back to an admin account, a shared credential, or broader access. Record
the limitation in STATUS.md and treat Layer 3 as BLOCKED pending a safe path.

### Credential handling

- The test-user password is created once and stored in the OS credential store
  / Secure Vault on Seth's PC. It is **never** stored in the repository, source
  code, logs, diagnostics, documentation, chat transcripts, or kavi-mail.
- Session tokens obtained at runtime live in memory only, for the duration of
  one test run. Never written to disk or logs. See [12](12-security.md).

## Per-channel test procedure

Each channel is tested **independently** — a pass on Horror says nothing about
Experimental.

1. **Authenticate** as the test user via the normal Emby auth pathway.
   Confirm the account sees only the three KaviTV channels.
2. **Channel/tuner resolution.** Confirm the channel appears in Emby Live TV
   with the expected number, name, and ID (cross-checked against the Metadata
   Sentinel mapping, [02](02-metadata-specification.md)).
3. **Playback initiation.** Request playback through the normal client pathway
   (PlaybackInfo → session-keyed stream URL), exactly as a real client does —
   including the PlaySessionId, which the v0.1.0 incident proved is required
   for segments to resolve.
4. **Session creation.** Confirm Emby creates and maintains a playback session
   (session present, PlayState sane) for the test run.
5. **Media flow.** Verify bytes/segments actually arrive through the session —
   not just HTTP 200 on the API. Sample segments and check TS validity
   (same segment checks as Layer 2).
6. **Record PlayMethod** per channel: DirectPlay / DirectStream / Transcode.
   A change in PlayMethod vs. baseline is informative (e.g. unexpected
   transcode) and recorded, not automatically a failure.
7. **Progress/session state.** Report playback progress mid-test; confirm the
   session stays alive across the test window.
8. **Detect** stalls, errors, and restarts during the window; record each with
   timestamp and Emby-side detail that is safe to record.
9. **Correlate with relay state.** Attach the concurrent Layer 1 result. If
   Emby fails while the relay is healthy, the failure is isolated to the Emby
   layer (tuner mapping, session handling, transcode) — the relay is
   exonerated by evidence, not by assumption.
10. **Auto-stop.** Close the session cleanly when the test ends. No dangling
    tuner sessions. Verify the session is gone afterward.

## Failure isolation

| Symptom | Likely layer | Evidence that decides |
|---------|--------------|----------------------|
| Tune fails, relay deep-health green | Emby (mapping/tuner) | Layer 1 PASS + Layer 3 tune FAIL |
| Session created, no media flows | Emby (session/stream) | session present, zero bytes |
| PlayMethod flips to Transcode unexpectedly | Emby (transcode) | PlayMethod vs. baseline |
| All three channels fail identically | Emby server or relay | check Layer 1 first |
| One channel fails, others pass | channel-specific (mapping/source/schedule) | per-channel results |

## Scheduling

- Sampled, not continuous: full three-channel test on a periodic schedule
  plus post-restart validation (see [06](06-monitoring-specification.md)).
- Lightweight Emby reachability (server info, no auth) may run more often as
  part of watchdog v2's existing Emby health check.

## Status

**NOT BUILT. BLOCKED** — test-user creation requires the Emby admin API key
or Seth creating the user via Dashboard (Users → Add User). Design is complete
in this document; implementation follows unblocking.
