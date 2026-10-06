# Morning Digest — Format Specification

**Producer:** cron `kavi-team-morning-digest` (~8:36 AM ET daily).
**Rule:** ONE authoritative digest from canonical state. Never six competing
versions.
**Target repo location:** `kellner-dot/seth-dashboard/kavi-team/DIGEST-FORMAT.md`.

## Required sections (in order)

1. OVERALL STATUS
2. OVERNIGHT EVENTS
3. COMPLETED WORK
4. IN-PROGRESS WORK
5. BLOCKED WORK
6. FAILURES
7. RECOVERIES
8. INFRASTRUCTURE
9. RVG / TAILSCALE
10. EMBY
11. KAVITV
12. KAVITV PLAYBACK — Sentinel Layers 1–4 per channel with evidence labels;
    name the exact failing layer when something is wrong
13. KAVITV METADATA — identity, EPG, logos, freshness, channel/program counts
14. STORAGE / TERABOX / RCLONE
15. BACKUPS / RECOVERY
16. SECURITY
17. CONFIGURATION DRIFT
18. NEWLY DISCOVERED PROJECTS
19. PROJECT STATUS TABLE — the full table from `KAVI-TEAM-STATE.md`; if very
    large, attach/link the canonical table plus a concise change summary
    (status transitions, new/paused/blocked/unblocked/verified projects)
20. HUMAN ACTION REQUIRED — ONLY items genuinely requiring Seth (his clicks,
    credentials, judgment, financial/legal). Nothing else.
21. NEXT 24 HOURS

## Rules

- Format: DONE / IN PROGRESS / BLOCKED / HUMAN ACTION REQUIRED.
- Evidence labels on every claim (VERIFIED / OBSERVED / INFERRED / BLOCKED /
  FAILED / RECOVERED / NOT BUILT / QUEUED). Never upgrade an INFERRED to a
  VERIFIED in wording.
- Quiet days are brief. The digest reports state; it does not manufacture drama.
- Autonomous routine email is fine where already connected; no invented
  approvals, no financial/legal commitments, no credential disclosure.
- Source of truth is the canonical state, not kavi-mail claims. An email
  saying "done" is not proof of completion.
