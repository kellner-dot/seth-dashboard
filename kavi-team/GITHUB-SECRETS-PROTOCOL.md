# UNIFIED GITHUB + SECRETS PROTOCOL — FOR KAVI 1–6

*Issued 2026-10-05. Expansion of the Kavi Team Protocol. Recorded verbatim as
the canonical copy. Companion: `KAVI-TEAM-PROTOCOL.md`.*

DO NOT replace working infrastructure.
DO NOT create duplicate systems.
DO NOT weaken existing security controls.

Apply these rules to all Kavi 1–6.

==================================================

## 1. SYSTEM OF RECORD ROLES

Each system has a specific role:

- **AUTHORIZED DRIVE** = SECRET SOURCE OF TRUTH
- **GITHUB** = CODE / CONFIGURATION / WORKFLOW / DOCUMENTATION SOURCE OF TRUTH
- **RUNTIME SYSTEMS** = ACTUAL DEPLOYED/OPERATING STATE
- **CANONICAL KAVI TEAM STATE** = PROJECT / OWNERSHIP / STATUS / COORDINATION SOURCE OF TRUTH
- **GMAIL** = KAVI COMMUNICATION BUS

Do not confuse these roles.

A successful GitHub commit does not prove production is running that version.
A running production version does not prove the repository contains the current version.
An email does not override canonical state.
A credential existing in Drive does not authorize copying it elsewhere.

## 2. AUTHORIZED DRIVE = SECRET SOURCE OF TRUTH

Seth's authorized Drive is the authoritative source for stored operational
secrets and credential material. When an operational credential is legitimately
required:

AUTHORIZED DRIVE → LEGITIMATE RETRIEVAL → AUTHORIZED USE → TRANSIENT USE WHERE
PRACTICAL → SECURE CLEANUP

Covers: API keys, passwords, RVG credentials, Emby credentials, OAuth
credentials, tokens, private keys, other operational authentication material.

Never assume GitHub is the source of a secret merely because a workflow needs it.

## 3. SECRET HANDLING

Never place secret values in: GitHub repositories, source code, commits, pull
requests, GitHub Issues, GitHub Discussions, workflow output, Gmail,
Kavi-to-Kavi messages, canonical team state, project documentation,
screenshots, ordinary logs, diagnostic output.

Canonical state may record: `SECRET SOURCE: AUTHORIZED DRIVE`.
It may NOT record the secret value.

## 4. CREDENTIAL RETRIEVAL

1. Confirm the task is authorized. 2. Check the authorized Drive source.
3. Retrieve through the legitimate access path. 4. Use only for the authorized
task. 5. Keep transient whenever practical. 6. Prevent appearance in
output/logs. 7. Securely clean up temporary copies. 8. Record only non-secret
operational evidence.

Do NOT: guess/brute-force credentials; search unrelated machines; search
browser data; extract credentials from applications; hunt logs for secrets;
bypass access controls; weaken authentication; create unauthorized replacement
credentials.

## 5. IF DRIVE ACCESS IS UNAVAILABLE

STATUS: BLOCKED — AUTHORIZED SECRET UNAVAILABLE. Do not work around it.
Report: what system requires access, what credential type, why, what operation
is blocked. Do NOT reveal the credential or speculate about its value.

## 6. GITHUB SECURITY

Protect production/default branches with rulesets/branch protections. Where
appropriate require: pull requests, required status checks, successful
deployment checks, security checks, signed commits, restrictions on force
pushes and branch deletion. Do not weaken protections to make automation easier.

## 7. GITHUB ACTIONS LEAST PRIVILEGE

Minimum practical permissions per workflow; prefer explicit workflow
permissions. Read-only workflows must not receive broad write access. If write
is required: DOCUMENT WHY. On permission failure: identify the exact missing
permission, determine necessity, grant smallest appropriate — never broad access.

## 8. GITHUB WORKFLOW SECRETS

Use the approved GitHub secret-management mechanism or another authorized
secure mechanism. Do NOT copy a Drive secret into: repository files, workflow
YAML, scripts, READMEs, issues, commits. Drive possession does NOT authorize
GitHub copying. If the GitHub secret mechanism is not legitimately
provisioned: STATUS: BLOCKED. Do not expose the Drive credential to solve it.

## 9. OIDC / SHORT-LIVED AUTHENTICATION

Prefer short-lived identity (e.g. GitHub OIDC) over long-lived static
credentials where supported and materially better. Do not introduce OIDC for
complexity's sake. Preserve the existing legitimate RVG/Tailscale auth path
unless an authorized migration is approved.

## 10. DEPLOYMENT PIPELINE

CLAIM → CHANGE → VALIDATE → TEST → POLICY/REVIEW CHECK → DEPLOY → VERIFY →
DOCUMENT → UPDATE CANONICAL STATE. A successful Actions workflow does NOT equal
successful production deployment. After deployment, verify actual runtime
(for KaviTV/Emby: use the Playback Sentinel where applicable).

## 11. GITHUB ↔ PRODUCTION DRIFT

Monitor meaningful differences (commit/version, scripts, config, workflows,
deployment artifacts, scheduled tasks, service config). Classify: EXPECTED /
UNEXPECTED / UNKNOWN. Do not blindly overwrite production. Investigate first.

## 12. COMMIT DISCIPLINE

Significant commits identify what changed, why, project/task ID where
practical. Traceability: PROJECT → TASK → COMMIT → DEPLOYMENT → VERIFICATION.
Avoid meaningless commits. Never commit credentials even temporarily.

## 13. MULTI-KAVI REPOSITORY COORDINATION

Before modifying a repository: 1. Read canonical state. 2. Check ownership.
3. Claim project/task. 4. Check existing branches/work. 5. Avoid duplicating
another Kavi's work. On handoff: identify branch/commit, uncommitted changes,
dependencies, update canonical state, notify receiving Kavi. Never assume
another Kavi knows about uncommitted local changes.

## 14. CI / VALIDATION

Meaningful automated validation where appropriate: syntax, unit tests, config
validation, security checks, secret scanning, deployment validation, Sentinel
tests, KaviTV validation, documentation consistency. No fake checks to satisfy
branch protection.

## 15. THIRD-PARTY GITHUB ACTIONS

Before introducing: identify source, determine necessity, review permissions,
prefer established/official actions, pin versions, understand data access. Do
not introduce an action to avoid a simple local check.

## 16. PRODUCTION FAILURE

STOP ROLLOUT → CAPTURE EVIDENCE → IDENTIFY FAILURE → DETERMINE SAFE RESPONSE →
ROLLBACK IF AUTHORIZED AND SAFE → VERIFY RECOVERY → DOCUMENT → UPDATE
CANONICAL STATE. No blind redeploys. No automatic destructive recovery.

## 17. SECRET EXPOSURE INCIDENT

If a Drive-sourced credential appears in GitHub / Actions logs / Gmail / Kavi
messages / canonical state / docs / screenshots / app logs: STOP normal
propagation. Do not copy it elsewhere. Deleting the visible copy alone does
not resolve it. Treat as potential exposure incident. Preserve minimum
evidence without reproducing the secret. Rotation needs authorization unless
existing policy requires immediate automated action.

## 18. AUDIT GITHUB PERIODICALLY

Review: branch protection, rulesets, required checks, workflows, workflow
permissions, repository access, connected apps, deployment paths, stale
branches/workflows, unused Actions, security checks, secret handling,
GitHub/runtime drift. Record meaningful findings in canonical state. Create a
project for meaningful unresolved gaps.

## 19. CURRENT GIT BLOCKER

Git push remains: BLOCKED — LEGITIMATE GIT CREDENTIAL ACCESS UNAVAILABLE.
Do NOT hunt/extract/reuse/bypass credentials or weaken repo security. Keep the
staged commit plan intact. When legitimate access arrives: VALIDATE → PUSH →
VERIFY REMOTE STATE → VERIFY DEPLOYMENT → VERIFY RUNTIME → UPDATE CANONICAL STATE.

## 20. CURRENT KAVITV SENTINEL STATE

Playback Sentinel: AUTOMATED END-TO-END VERIFIED (infrastructure, real media
segments, TS sync, advancing bytes, Emby session, synthetic client pathway,
clean close, all three channels). Remaining separate layer: REAL HUMAN CLIENT
VISUAL/AUDIO PLAYBACK: PENDING. Do not mark the system failed for the pending
human check; do not mark the human layer verified for synthetic passes.
Maintain the evidence distinction.

## 21. AI-INDEPENDENCE

GitHub, Emby, KaviTV, backups, watchdogs, scheduled tasks, recovery tooling
must not depend on Kavi/Muse availability. Kavi/Muse is the
administrative/coordination layer, NOT the runtime dependency.

## 22. FINAL OPERATING MODEL

```
AUTHORIZED DRIVE  →  SECRETS
GITHUB            →  CODE / CONFIG / WORKFLOWS / DOCUMENTATION
RUNTIME           →  ACTUAL PRODUCTION STATE
CANONICAL STATE   →  PROJECTS / OWNERSHIP / VERIFICATION / COORDINATION
GMAIL             →  KAVI COMMUNICATION
KAVI 1–6          →  AUTONOMOUS ADMINISTRATION / MONITORING / IMPLEMENTATION / VERIFICATION
SETH              →  FINAL AUTHORITY FOR EXCEPTIONS
```

Maintain boundaries. Do not duplicate systems. Do not lose project state. Do
not expose secrets. Do not bypass authentication. Do not deploy unverified
changes. Do not confuse repository state with runtime state, communication
with authorization, or credential accessibility with authorization for every
purpose. Continue autonomous routine work within standing authorization.
