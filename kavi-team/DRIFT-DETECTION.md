# Configuration-Drift Detection

**Status:** Spec + reference script created 2026-10-05 (workspace).
PC deployment QUEUED.
**Target repo location:** `kellner-dot/seth-dashboard/kavi-team/DRIFT-DETECTION.md`
(+ `drift-check.py`).

## Purpose

Detect when live configuration silently diverges from the last verified
baseline — Emby libraries, tuner/channel mappings, scheduled tasks, relay
config, storage layout — so drift surfaces as an alert, not as a mysterious
failure weeks later. Read-only: the detector never changes configuration.

## Baselines (already exist as docs)

- `emby-library-baseline-2026-10-05.md` — library paths.
- `kavitv-storage-architecture-2026-10-05.md` — storage roles.
- `emby-transcode-decision-tree-2026-10-05.md` — GPU/transcode canonical state.
- `KAVI-TEAM-STATE.md` §12 — configuration assumptions.
- KaviTV snapshot zip (Drive, 2026-10-05) — relay.py, generate.py, library.json.

## What the detector checks

| Check | Baseline source | Drift = |
|-------|-----------------|---------|
| Emby library paths | library baseline doc | path added/removed/changed |
| Emby channel number/name/ID (3 KaviTV) | state doc §12 | renumber/rename |
| Tuner URLs in Emby | state doc §12 | URL changed |
| Scheduled tasks present + enabled | 5 exported task XMLs | task missing/disabled/schedule changed |
| Relay config (port, version) | relay.py snapshot hash | file changed |
| Disk layout (C:/D:/T: present) | storage arch doc | drive missing |
| Emby server mode | interactive as sethr | service mode / different user |

## Detector behavior

- Runs weekly + after any incident recovery (drift often hides behind incidents).
- Compares live state to baselines; outputs DRIFT / NO DRIFT per check with
  before/after values.
- DRIFT on a stability-locked item (GPU, Emby mode, library paths) = HIGH
  alert; DRIFT elsewhere = recorded in digest.
- Never auto-remediates. Remediation is a human decision with the
  before/after evidence attached.

## Reference script

`drift-check.py` (stdlib only, read-only). On the PC it queries Emby's public
endpoints, inspects scheduled tasks via `schtasks`, and hashes config files.
Writes `drift-report.json` next to `sentinel-results.json`. PC deployment
queued behind Sentinel Layer 2/metadata work.
