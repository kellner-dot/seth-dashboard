# GATE-A1 RVD Coordination — from kavi2 to all

**Date:** 2026-10-08 17:30 EDT
**From:** kavi2 (Kavi 2.0)
**Subject:** GATE-A1 (RVD user-session exec) — deployment coordination required

## Status
Seth has AUTHORIZED GATE-A1 implementation (2026-10-08 ~17:25 EDT).
Spec: `kellner-dot/kavibot` phase2/accessibility/GATE-A1-USER-SESSION-EXEC.md

## What A1 needs from RVD
One new execution mode on the existing `/exec` endpoint:
- Optional `"session": "user"` field in the POST JSON
- When present, launch the command via WTSQueryUserToken + CreateProcessAsUser
  in the active console session (winsta0\default), as the interactive user
  at medium integrity — NOT SYSTEM
- Same transport, same X-RVD-Token auth, same response envelope
- Fail closed: no console session → error, never fall back to Session 0
- Kill-switch: `$EnableUserSessionExec` config flag (default true when implemented)

## Standing rule
Per AGENTS.md: RVD agent changes must be coordinated — never deploy
agent/client independently. I am NOT deploying this unilaterally.

## What's ready
- KaviBOT-side: `transport.exec_usersession` L2 action class registered
  (phase2/authorize/policy.json); `a11y.py` accepts `session` parameter
  (defaults to "system" — safe before agent supports it)
- Agent modification spec: phase2/accessibility/GATE-A1-AGENT-MODIFICATION.md
- Technique validated: WTSQueryUserToken succeeds from Session-0 SYSTEM
  (console session 1 active, token acquired 2026-10-08)

## What's needed
The RVD agent maintainer: review GATE-A1-USER-SESSION-EXEC.md and
GATE-A1-AGENT-MODIFICATION.md, then coordinate a deployment window.
KaviBOT-side is safe to deploy before/after (unknown `session` field
is ignored by pre-A1 agents).

## What A1 does NOT do (explicit)
- No elevation, no privilege broadening (child is medium integrity)
- No L3/L4 changes, no standing grants (B1 is separate, NOT authorized)
- No new transport, endpoint, or auth mechanism
- a11y_dump.py unchanged

— kavi2
