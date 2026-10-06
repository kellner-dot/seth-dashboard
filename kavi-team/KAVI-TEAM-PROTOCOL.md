# KAVI TEAM PROTOCOL — Coordination Across Independent Chats

**Companion to:** [KAVI-TEAM-STATE.md](KAVI-TEAM-STATE.md) (canonical state).
**Target repo location:** `kellner-dot/seth-dashboard/kavi-team/KAVI-TEAM-PROTOCOL.md`.

## The reality this protocol is built for

The six Kavis run in independent chats. A side chat does not automatically
have the context of the main chat or of another Kavi's chat. Conversational
memory is therefore NOT shared state, NOT authorization, and NOT the source
of truth.

What is shared: this state document, the repository, Drive, and kavi-mail.
Coordination happens through persistent, evidence-based records — not through
assuming another Kavi knows something.

## The coordination protocol

Before beginning a consequential task:

1. **Read the canonical state.** Open `KAVI-TEAM-STATE.md`. Check the Project
   Status Table: is the project listed, who owns it, what stage is it in?
2. **Check for active work.** If another Kavi owns it or is IN PROGRESS,
   coordinate (kavi-mail HANDOFF) rather than starting a competing
   implementation.
3. **Check authorization and security boundaries** (§8–§9 of the state doc).
   The more restrictive state wins until Seth says otherwise.
4. **Record ownership.** Update the Project Status Table: set Owner and Status
   (IN PROGRESS), Current Stage, and Next Action. Timestamp it.
5. **Perform the work** within the standing authorization.
6. **Verify the result** against acceptance criteria. VERIFIED requires a
   test, not a design doc.
7. **Update the canonical state.** Results, evidence, new timestamps, new
   projects discovered — all go in immediately.
8. **Release ownership / hand off.** Status → COMPLETE or VERIFIED (or back
   to BLOCKED/PAUSED with the blocker named); HANDOFF via kavi-mail if
   another Kavi continues it.

## Project Status Table — maintenance rules

- The table in `KAVI-TEAM-STATE.md` is mandatory and kept current. It lists
  every known project, not just active ones.
- Allowed statuses: NOT STARTED / PLANNED / DESIGNED / IN PROGRESS / BLOCKED /
  PARTIALLY COMPLETE / COMPLETE / VERIFIED / PAUSED / CANCELLED.
- COMPLETE ≠ VERIFIED. A project is VERIFIED only after its implementation
  has been tested against its acceptance criteria. Never mark VERIFIED
  because a design or document exists.
- Every row has: named Kavi owner or TEAM, current stage, last-verified
  timestamp, concrete next action, explicit blocker (or "None"), priority
  (CRITICAL / HIGH / MEDIUM / LOW).
- Newly discovered projects are added as soon as they are identified —
  a project must never disappear because it lived in one conversation.
- Update the table immediately when work is started, claimed, paused,
  handed off, blocked, completed, verified, or recovered.

## Project ownership / claim system

Before working on a substantial project, claim it in the state doc:

```
PROJECT: [PROJECT-ID]
TASK: [TASK-ID]
OWNER: [KAVI-X]
STATUS: IN_PROGRESS
CLAIMED: [timestamp]
NEXT_CHECKPOINT: [timestamp]
```

- Do not duplicate another Kavi's active work.
- If a claim goes stale (owner stops communicating/updating), mark it STALE
  and recover deliberately: `RECOVERED_FROM_STALE_CLAIM: KAVI-X`, documenting
  why recovery was necessary.
- Release ownership when the task completes or is handed off.

## Standard Kavi message format

Use for Kavi-to-Kavi operational mail (compatible with the kavi-mail tag
protocol — TYPE maps to tags: REQUEST→[ACTION], HANDOFF→[HANDOFF],
STATUS/RESULT→[FYI], ALERT→[URGENT]):

```
FROM: KAVI-X
TO: KAVI-Y / KAVI-TEAM
TYPE: REQUEST / ACK / HANDOFF / STATUS / ALERT / RESULT
PROJECT: [PROJECT-ID]
TASK: [TASK-ID]
STATUS: [STATUS]
OWNER: [KAVI-X]
COMPLETED: ...
EVIDENCE: (VERIFIED / OBSERVED / INFERRED / BLOCKED / FAILED / RECOVERED / NOT BUILT / QUEUED)
NEXT_ACTION: ...
BLOCKER: ...
CANONICAL_STATE_UPDATED: YES/NO
```

No credentials in Gmail, GitHub, docs, logs, or canonical state — ever.

## Anti-duplication and anti-loop rules

- Use project IDs, task IDs, message IDs, and parent-message references.
- If the same instruction/message arrives twice: recognize it as processed,
  do not repeat actions, report the existing result.
- No endless Kavi-to-Kavi loops. Normal flow: REQUEST → ACK → ACTION →
  RESULT, then stop unless a new actionable event exists.
- Do not send messages merely to prove activity; keep the mailbox readable.

## Operating loop (autonomous routine work)

AUDIT → CHECK CANONICAL STATE → CHECK OWNERSHIP → CLAIM → BACKUP IF
NECESSARY → IMPLEMENT → TEST → VERIFY → DOCUMENT → UPDATE CANONICAL STATE →
HANDOFF IF NECESSARY → RELEASE CLAIM.

Do not stop merely because something was designed. Do not call something
complete because a script exists. Do not call something verified without
evidence.

## Autonomous project discovery

Periodically audit the environment for: NOT STARTED / DESIGNED BUT NOT BUILT /
PARTIALLY IMPLEMENTED / BLOCKED projects, missing monitoring, missing
verification, missing backups, untested recovery, configuration drift,
undocumented systems, stale docs, SPOFs, missing alerts, weak handoffs,
missing ownership, missing acceptance criteria. Compare against canonical
state first; never create duplicate projects.

## Continuous improvement

When a weakness is found within standing authorization to safely fix:
identify → assess risk → confirm authorization → smallest safe change →
test → verify → document → update canonical state → notify the right Kavi.
If it needs more authorization, stop at the dependency and report it.

## AI-outage independence

AI/Kavi/Muse is an ADMINISTRATIVE layer, not a runtime dependency. Emby,
KaviTV, scheduled tasks, watchdogs, backups, EmergencyKit, and local
recovery must all keep working with no Kavi online. Identify and eliminate
unnecessary runtime dependencies on AI.

## Evidence rules

Use VERIFIED / OBSERVED / INFERRED / BLOCKED / FAILED / RECOVERED / NOT BUILT /
QUEUED on every important state entry, with timestamps where practical.
Never promote an observation or inference into a verified result.

## Conflict resolution

If two Kavis report conflicting information:

1. Do not silently choose one.
2. Prefer the most recent directly verified evidence.
3. Preserve the more restrictive security state until resolved.
4. Record the conflict in the state doc (§16).
5. Resolve with a new verification — not by trusting conversational memory.

## Cross-chat handoffs

- When a side chat finishes work, its result is written into the canonical
  state so another Kavi can pick it up without the original conversation.
- When starting work based on something another Kavi supposedly did, verify
  the actual system/repository state rather than trusting the claim alone.
- kavi-mail is the coordination channel: HANDOFF tags for transfers,
  ACTION tags for requests, FYI for reports. No secrets in kavi-mail, ever.

## Morning digest requirement

The morning digest includes the full Project Status Table, or — when the
table grows large — the complete table as an attached/linked canonical report
plus a concise summary of changes since the previous digest (status changes,
new projects, newly blocked/unblocked items). Format:
[DIGEST-FORMAT.md](DIGEST-FORMAT.md).

## This protocol applies equally to

Kavi 1.0, Kavi 2.0, Kavi 3.0, Kavi 4.0, Kavi 5.0, Kavi 6.0.
