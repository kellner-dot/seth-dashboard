# Autonomous Recovery Matrix

**Status:** DESIGNED 2026-10-05. Extends `sentinel/09-recovery-runbook.md`
with the full failure → diagnosis → action matrix.
**Target repo location:** `kellner-dot/seth-dashboard/kavi-team/RECOVERY-MATRIX.md`.

## How to read

Each row: observed failure → how to diagnose (evidence first) → the
authorized automatic action (if any) → bound → what happens when the bound
is hit. Philosophy: detect → capture evidence → identify failing layer →
back up if necessary → authorized reversible correction only → test →
verify → document → continue. Never blindly restart.

## Matrix

| # | Failure observed | Diagnose (evidence) | Automatic action | Bound | On bound hit |
|---|------------------|---------------------|------------------|-------|--------------|
| R1 | Relay process down (:8100 refused) | Task state? Port bound by other process? | Restart "KaviTV-relay" task | 3/hour | Hold FAILED, escalate |
| R2 | `/api/health` not ok | Response body vs connection error | R1 if process fault | 3/hour | Escalate |
| R3 | deep-health FAIL all channels, relay up | ffmpeg processes alive? Source media reachable? | One relay restart | 1/cycle | Escalate (likely ffmpeg/source) |
| R4 | deep-health FAIL one channel | Other channels green → channel-specific | No auto-restart; inspect channel source/schedule | — | Escalate with per-channel evidence |
| R5 | Layer 2 segment failures, L1 green | Segment error class (empty/malformed/stall) | One relay restart if no narrower cause | 1/cycle | Escalate |
| R6 | Schedule horizon < 2 days | `generate.py` output state | Regenerate schedule | 1/cycle | Escalate |
| R7 | XMLTV unparseable / counts collapsed, streams fine | Last export time; parse error | One bounded `export_iptv.py` re-run (NOT YET IMPLEMENTED) | 1/hour | Escalate — do NOT loop exporter |
| R8 | Counts collapsed right after fresh export | Before/after snapshots | NONE — source data suspect | — | Escalate immediately |
| R9 | Emby tune/session FAIL, relay green | Layer 1 PASS + Layer 3 FAIL = Emby-side | NONE (no Emby writes) | — | Escalate with correlation |
| R10 | Dangling Emby test session | Session list after test | Close own session (NOT YET IMPLEMENTED) | Every run | Log and continue |
| R11 | Disk C:/D:/T: <10% free | Watchdog disk check | NONE (alert only) | — | WARNING alert |
| R12 | Disk <5% free | Watchdog disk check | NONE (alert only) | — | CRITICAL alert |
| R13 | T: mount dropped | rclone/Alist probe | NONE (TeraBox watchdog v4 owns remounts) | — | Note best-effort; no KaviTV impact by design |
| R14 | Flapping (rapid PASS/FAIL) | Consecutive-result history | NONE — suppress alert spam, record flapping | — | Escalate as flapping condition |

## What is never automatic

Emby restarts or library/tuner/user changes · credential operations ·
firewall/Tailscale/network changes · file deletion or media moves ·
anything irreversible without Seth's explicit approval.

## Re-test rule

Every automatic action is followed by re-running the exact failed check.
RECOVERED is recorded only on a passing retest. A restart without a passing
retest is "recovery attempted," not recovered.
