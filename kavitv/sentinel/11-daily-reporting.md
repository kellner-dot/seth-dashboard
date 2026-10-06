# Daily Reporting — Sentinel in the Morning Digest

## Placement

Sentinel results are a standing section of the Kavi Team Morning Digest
(~8:30 AM ET, cron `kavi-team-morning-digest`). The digest's full format —
including the mandatory Project Status Table — is specified in
`~/workspace/kavi-team/DIGEST-FORMAT.md`. The Sentinel sections below plug
into that format; the digest distinguishes six subsections, each naming the
failing layer exactly when something is wrong.

## Section format

### VIDEO
Playback-chain state: Layers 1–3 per-channel verdicts with evidence labels,
plus Layer 4 sign-off state.

- Example (current): "Layer 1 VERIFIED (deep-health 3/3, 06:12 ET). Layer 2
  INFERRED — script written, not yet deployed. Layer 3 NOT BUILT/BLOCKED
  (test user). Layer 4 BLOCKED (visual test). Overall: INFRASTRUCTURE ONLY."

### METADATA
Metadata Sentinel verdict: identity/EPG/logos/freshness rollup, counts
(channels/programs/logos-ok/EPG age), any WARN/FAIL with the failing check
and channel.

- Example: "PASS — 3 channels, 157 programs, 3/3 logos, EPG age 6h."

### EMBY
Emby-side health relevant to KaviTV: server reachability, session state from
Layer 3 runs, PlayMethod per channel, any tuner/mapping notes. Distinct from
VIDEO because Emby can fail while the relay is healthy.

### CLIENT
Layer 4 state: last human visual verification per channel (timestamp + who),
or "not yet performed."

### RECOVERY
Incidents in the last 24h: FAILED → recovery action → retest outcome
(RECOVERED or still FAILED), plus any escalations awaiting Seth. Bounded and
factual — no narrative.

### OVERALL
The health-model state ([04](04-health-model.md)): FULLY VERIFIED /
PLAYBACK VERIFIED / METADATA DEGRADED / METADATA VERIFIED / PLAYBACK
DEGRADED / INFRASTRUCTURE ONLY / FAILED — with the five dimension verdicts
that produce it.

## Rules

- Every subsection carries evidence labels; the digest never upgrades an
  INFERRED to a VERIFIED in wording ("stream looks fine" is banned; "stream
  integrity INFERRED from byte flow, Layer 2 not yet deployed" is required).
- When something fails, the digest names the layer, the check, the channel,
  and the evidence — "Layer 2 FAILED on experimental: 3 consecutive empty
  segments at 02:14 ET," not "there was an issue with a channel."
- Quiet days are one line per subsection. The digest does not manufacture
  drama; it reports state.
