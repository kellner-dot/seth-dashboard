# Unified Evidence Model

Every Sentinel result, status note, and digest line carries exactly one evidence
label. The label says how we know, not just what we claim.

## Labels

### VERIFIED
Directly tested or confirmed with recorded evidence in this system.

- Example: "`/api/deep-health` returned real media bytes on all 3 channels at
  2026-10-05 15:15 EDT" — we ran the check and recorded the bytes.
- Use only when a test actually executed and passed, with its evidence record
  present ([07](07-diagnostics-evidence.md)).

### OBSERVED
Seen or reported, but not independently verified by a Sentinel test.

- Example: "Seth reported the Horror channel played in the Emby web client."
  We did not run a test; we are recording his report.
- Observations are useful and actionable, but they are not VERIFIED.

### INFERRED
A reasonable conclusion drawn from available evidence, stated as an inference.

- Example: "Layer 1 passes and bytes are advancing, so the stream is *probably*
  playable — INFERRED, pending Layer 2."
- Inferences must be labeled as such and must never be promoted to VERIFIED
  without the corresponding test.

### BLOCKED
Cannot proceed until an external dependency or human action is supplied.

- Example: "Layer 3 — BLOCKED: test-user creation needs Emby admin API key or
  Seth creating the user via Dashboard."
- A BLOCKED item names its unblocker explicitly.

### FAILED
A test actually ran and did not pass. Always paired with the failure reason
and the failing layer.

- Example: "Layer 2 horror: FAILED — 3 consecutive empty segments at
  2026-10-05 19:02 EDT."

### RECOVERED
A failure occurred, a recovery action was taken, and a retest passed.

- Example: "Relay restart at 19:05 EDT; deep-health retest PASS — RECOVERED."
- RECOVERED requires the retest. A restart without a passing retest is not
  recovered; it is FAILED with a recovery attempted.

### NOT BUILT
Designed but not implemented. Distinct from BLOCKED: nothing external is
missing, the work simply has not been done.

- Example: "Layer 3 tester — NOT BUILT (design complete in
  [05](05-emby-integration.md))."

### QUEUED
Acknowledged work, ordered behind other work or a standing constraint.

- Example: "UbuWeb metadata production changes — QUEUED behind stability lock."

## Rules

1. **Never promote.** An OBSERVED or INFERRED result must never be written,
   displayed, or reported as VERIFIED. If the dashboard or digest cannot tell
   the difference, the dashboard or digest is wrong — fix it, not the label.
2. **One label per claim.** "Relay healthy (VERIFIED); stream playable
   (INFERRED)" — not "everything looks good."
3. **FAILED needs a layer.** Every failure names the layer and the check that
   failed, so recovery targets the right component ([09](09-recovery-runbook.md)).
4. **RECOVERED needs a retest.** Recovery is verified by the same test that
   failed, re-run after the action.
5. **BLOCKED names the unblocker.** "Blocked" alone is not a status; "blocked
   on X, owned by Y" is.
6. **NOT BUILT vs BLOCKED.** Do not mark a component BLOCKED when it is merely
   unimplemented, and do not mark it NOT BUILT when an external dependency is
   the actual holdup. Layer 3 is both NOT BUILT *and* BLOCKED (no test user);
   record both, with the dependency first.

## Label usage in the morning digest

The digest's VIDEO / METADATA / EMBY / CLIENT / RECOVERY / OVERALL sections
([11](11-daily-reporting.md)) each carry the label of the underlying evidence,
e.g. "VIDEO: Layer 1 VERIFIED, Layer 2 INFERRED (not yet deployed)".
