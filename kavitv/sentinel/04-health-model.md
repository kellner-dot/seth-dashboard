# Final Health Model

## The five dimensions

The Sentinel tracks five independent dimensions. Each gets its own verdict;
no dimension's verdict is derived from another's.

| Dimension | Question it answers | Decided by |
|-----------|---------------------|------------|
| Relay healthy | Is the relay serving real media bytes? | Layer 1 (deep-health) |
| Stream healthy | Is the stream actually playable? | Layer 2 (segment integrity) |
| Metadata healthy | Are identity, EPG, logos, mappings correct and fresh? | Metadata Sentinel |
| Emby integration healthy | Can Emby tune/session/play via the normal pathway? | Layer 3 (test user) |
| Client playback verified | Does a real client render picture and sound? | Layer 4 (human) |

## The cardinal rule

**The system must never report "KaviTV is working" solely because the
relay/API is green.**

"Relay healthy" is a statement about the relay. "KaviTV is working" is a claim
about the whole chain. The dashboard and digest are forbidden from collapsing
the former into the latter.

## Overall states

| State | Meaning | When to use |
|-------|---------|-------------|
| FULLY VERIFIED | Video, Emby playback, and metadata all pass with VERIFIED evidence | Layers 1–3 PASS (VERIFIED), Layer 4 signed off, metadata PASS |
| PLAYBACK VERIFIED / METADATA DEGRADED | Video chain works; metadata has a problem | Layers 1–3 PASS; metadata FAIL or WARN |
| METADATA VERIFIED / PLAYBACK DEGRADED | Guide data healthy; playback is not | Metadata PASS; any of Layers 1–3 FAIL |
| INFRASTRUCTURE ONLY | Lower-level checks pass; Emby/client not verified | Layer 1 PASS; Layer 2/3 not passing or not built; never present as "working" |
| FAILED | A layer test actually failed | Any layer FAILED with recorded reason |

### State-transition rules

- Layer 1 PASS alone → at most INFRASTRUCTURE ONLY. Never higher.
- Metadata FAIL while Layers 1–3 PASS → PLAYBACK VERIFIED / METADATA DEGRADED,
  with the metadata failure named (which check, which channel).
- Layer 2 or 3 FAIL while metadata PASS → METADATA VERIFIED / PLAYBACK DEGRADED,
  with the failing layer named.
- A NOT BUILT or BLOCKED layer caps the overall state: it can be noted as the
  reason the state is not higher (e.g. "INFRASTRUCTURE ONLY — Layer 2 not yet
  deployed, Layer 3 blocked on test user").
- FAILED clears only via RECOVERED (failing test re-run and passing), or via a
  documented determination that the failure was a test artifact (recorded as
  INFERRED with reasoning, never silently).

## Worked examples

- Deep-health green on 3/3, Layer 2 not deployed, metadata passing, no Emby
  test yet → **INFRASTRUCTURE ONLY** (relay VERIFIED; stream INFERRED;
  Emby/Client NOT BUILT/BLOCKED). This is the honest state of the system as of
  2026-10-05.
- All layers passing but logo check 404s on one channel → **PLAYBACK VERIFIED /
  METADATA DEGRADED** (logo failure named).
- XMLTV unparseable after a bad export; relay still serving bytes → **PLAYBACK
  VERIFIED / METADATA DEGRADED**, plus metadata CRITICAL alert if program
  counts collapsed.
- Emby tune fails with relay healthy → **METADATA VERIFIED / PLAYBACK
  DEGRADED** (failure isolated to Emby layer; relay evidence attached to show
  the relay is not the cause).

## Display requirements

Every surface that shows an overall state (dashboard, digest, alerts) must also
show the five dimension verdicts with their evidence labels. The overall state
is a summary; the dimensions are the truth.
