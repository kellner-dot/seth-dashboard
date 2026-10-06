# Emby Backup & Restore — Design

**Status:** DEPLOYED 2026-10-05 19:14 EDT (file-level + KaviTV snapshot).
**Priority:** HIGH (Seth's priority #4 — done).
**Constraint (Seth's order):** NO live restore tests without his explicit
authorization. Live restore testing waits for his go-ahead.

**Target repo location:** `kellner-dot/seth-dashboard/kavi-team/EMBY-BACKUP-DESIGN.md`.

## Deployed (2026-10-05 19:14 EDT, both first-run VERIFIED)

| Job | Schedule | What | First run |
|-----|----------|------|-----------|
| `Emby-Config-Backup` (SYSTEM) | Sun 05:30 | library/users/auth/activity/playback DBs + config + plugins + livetv channel listings (~216MB); skips recordings (125GB), cache (91GB), metadata images (re-fetchable) | OK — 77 files |
| `KaviTV-Weekly-Snapshot` (SYSTEM) | Sun 04:30 | Zip of `C:\Users\sethr\kavitv\`, `*.key` secrets stripped, keeps last 8 | OK — 0.8MB, 0 .key files |

Scripts live in `C:\Users\sethr\kavitv\` (`emby-config-backup.ps1`,
`kavitv-snapshot.ps1`) and in the workspace (`kavi-team/`).
Backups land in `C:\Users\sethr\kavitv\backups\` (never an Emby-scanned folder).

## Current state

- Emby Server 4.10.1.0 runs interactively as sethr (Session 1). No scheduled
  config backup exists — this is a known SPOF from the AI-outage audit.
- RVG restore procedure exists for the RVG agent (not Emby); live test
  deferred (backup older than live).

## What's worth backing up

| Item | Location (typical) | Why |
|------|--------------------|-----|
| Emby program data (`library.db`, config, users) | `%AppData%\Emby-Server\programdata` | Server identity, libraries, users, watch state |
| KaviTV runtime | `C:\Users\sethr\kavitv\` | Relay, watchdog, sentinel, schedules, logs |
| Scheduled-task definitions | 5 exported XMLs (already in Drive kavi-history) | Recovery without AI |
| EmergencyKit | `C:\Tools\EmergencyKit\` | Already PC-local by design |

## Backup design (no Emby downtime)

1. **Emby Backup & Restore plugin** (Premiere-active): scheduled server-side
   backup, DB-versioned. Preferred path — no service stop needed.
2. **File-level copy** as fallback: robocopy `programdata` to a backup
   location (never T: as primary — best-effort cloud; local D: or external).
   Emby's SQLite `library.db` copies cleanly when the server is idle; for
   guaranteed consistency, stop Emby first (requires Seth's window).
3. **KaviTV snapshot**: zip `C:\Users\sethr\kavitv\` (code + config + logs
   manifest, no secrets) → Drive kavi-history, recurring weekly.
   (One snapshot exists: 2026-10-05.)
4. **Cadence**: Emby plugin daily; file-level weekly; KaviTV snapshot weekly.

## Restore procedure (DOCUMENTED ONLY — no live test without Seth)

1. Stop Emby Server.
2. Restore `programdata` from the chosen backup generation.
3. Start Emby; verify libraries, users, and KaviTV tuners resolve.
4. If the DB version mismatches the installed Emby build, use the plugin's
   migration path — never hand-edit `library.db`.
5. Rollback: keep the pre-restore `programdata` renamed aside until the
   restored instance is verified.

## What this does NOT do

- No live restore test on production (Seth's explicit prohibition).
- No backup of media files themselves (C:/D:/T: movies are source-of-truth
  on their own drives; the standing rule forbids moving them).
- No credentials in backup manifests or docs.

## Next actions

| Action | Owner | Needs |
|--------|-------|-------|
| Install/configure Emby Backup & Restore plugin schedule | Seth or Kavi 4 (non-disruptive) | 5 min in Emby Dashboard |
| File-level robocopy job as SYSTEM task | Kavi 4 | Design done here; deploy when approved |
| Weekly KaviTV snapshot cadence | Kavi 4 | Cron on this account |
| Live restore test | — | Seth's explicit authorization |
