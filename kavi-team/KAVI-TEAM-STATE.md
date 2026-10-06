# KAVI TEAM STATE — Canonical Shared Operational State

**Purpose:** the single authoritative operational state for Kavi 1.0, 2.0, 3.0,
4.0, 5.0, and 6.0. Independent chats do not share conversational memory; they
share this document.

**Critical rule:** conversation memory is NOT authorization and is NOT the
source of truth. A claim in one side chat does not become fact or authorization
in another. When information may have changed, consult this document first,
then verify against the actual system.

**Target repo location:** `kellner-dot/seth-dashboard/kavi-team/KAVI-TEAM-STATE.md`
(mirrored to Drive `kavi-history/`).
**Maintainer:** whichever Kavi last verified a section updates it.
**Coordination protocol:** [KAVI-TEAM-PROTOCOL.md](KAVI-TEAM-PROTOCOL.md).

Every entry carries an evidence label: VERIFIED / OBSERVED / INFERRED /
BLOCKED / FAILED / RECOVERED / NOT BUILT / QUEUED, plus a timestamp where
practical. Never promote an observation or inference into a verified result.

---

## PROJECT STATUS TABLE (mandatory — kept current)

Every known project, not just active ones. Status values allowed:
NOT STARTED / PLANNED / DESIGNED / IN PROGRESS / BLOCKED / PARTIALLY COMPLETE /
COMPLETE / VERIFIED / PAUSED / CANCELLED.

COMPLETE means the work is done. VERIFIED means the implementation was tested
against its acceptance criteria — design/docs alone never earn VERIFIED.
Update this table immediately when a Kavi starts, pauses, hands off,
completes, or verifies a project. Newly discovered projects are added here
as soon as they are identified.

| Project | Status | Owner | Current Stage | Last Verified | Next Action | Blocker | Priority |
|---------|--------|-------|---------------|---------------|-------------|---------|----------|
| KaviTV relay v0.1.0 (302 design) | VERIFIED | Kavi 4 | In service; rollback kept. CORRECTED 19:15 EDT: no v2.1 exists, no /api/deep-health | 2026-10-05 | Monitor via watchdog + Sentinel | None | HIGH |
| KaviTV watchdog v2 | VERIFIED | Kavi 4 | In service (5-min SYSTEM task) | 2026-10-05 | None — steady state | None | HIGH |
| KaviTV channel logos | VERIFIED | Kavi 4 | 3/3 correct, hash-verified; do not touch unless regression | 2026-10-05 | None | None | MEDIUM |
| Sentinel Layer 1 (infra) | VERIFIED | Kavi 4 | v0.1.0 302→playlist byte-change checks, 5-min SYSTEM task | 2026-10-05 19:15 EDT | None — steady state | None | HIGH |
| Sentinel Layer 2 (stream integrity) | VERIFIED | Kavi 4 | In-sentinel: TS sync, advancing hashes, zero-byte/stall detectors | 2026-10-05 19:15 EDT | None — steady state | None | HIGH |
| Sentinel metadata checks | VERIFIED | Kavi 4 | Paths correct; smoke test PASS (5/5 dimensions, 157 programs); daily 05:00 SYSTEM task | 2026-10-05 19:25 EDT | None — steady state | None | HIGH |
| Sentinel Layer 3 (Emby/synthetic playback) | VERIFIED (automated) | Kavi 4 | PlaybackInfo→session-keyed HLS→segments→progress→close; 3/3 "verified end-to-end"; server-key auth; test user QUEUED as optional hardening | 2026-10-05 19:15 EDT | None | None | HIGH |
| Sentinel Layer 4 (visual) | PENDING HUMAN CHECK | Seth | By design manual; automated VERIFIED — pending is not a failure | — | Seth's visual test when he chooses | None | MEDIUM |
| Sentinel aggregation/dashboard/digest | PARTIAL | Kavi 4 | Aggregation + dashboard VERIFIED (JSONL evidence, live HTML); digest integration DESIGNED | 2026-10-05 19:15 EDT | Digest integration | None | MEDIUM |
| Canonical team state (this doc) | IN PROGRESS | Kavi 4 | Draft + protocol + table + audit complete; commit staged (`kavi-team/COMMIT-PLAN.md`) | 2026-10-05 19:45 EDT | Push to repo + Drive (needs working git push path) | No git credentials on kavi4 VM | CRITICAL |
| Kavi 1–6 environment audit (11 areas) | COMPLETE | Kavi 4 | Findings compiled, prioritized, work begun (`kavi-team/AUDIT-2026-10-05.md`) | 2026-10-05 19:30 EDT | Publish canonical state (CRITICAL next) | None | HIGH |
| AI-outage readiness program | VERIFIED | Kavi 4 | Toolkit ALL GREEN on PC; docs in Drive | 2026-10-05 | Recurring snapshot cadence (see below) | None | HIGH |
| Emby config scheduled backup | VERIFIED | KAVI-4 | Deployed 2026-10-05 19:14 EDT: weekly SYSTEM task `Emby-Config-Backup` (Sun 05:30) backs up library/users/auth DBs + config + plugins + livetv listings (~216MB, skips recordings/cache); first run OK (77 files). NO live restore tests (Seth's prohibition) | 2026-10-05 | Optional: Emby-native plugin schedule (5 min in Dashboard) | 0 | HIGH |
| KaviTV off-PC snapshot recurring | VERIFIED | KAVI-4 | Deployed 2026-10-05 19:14 EDT: weekly SYSTEM task `KaviTV-Weekly-Snapshot` (Sun 04:30); first run OK (0.8MB zip, 0 .key files — secrets excluded) | 2026-10-05 | None | 0 | MEDIUM |
| GPU comparison | VERIFIED | Kavi 4 | iGPU retained, Seth-confirmed; closed | 2026-10-05 | None | None | LOW |
| UbuWeb metadata | PAUSED | TEAM | Queued behind stability lock | 2026-10-05 | Resume after lock lifts | Stability lock | MEDIUM |
| TeraBox verify/relink/deletes | IN PROGRESS | Kavi 3.0 | Per kavi5.0 18:41 report | 2026-10-05 18:41 EDT | Continue workstream | None | MEDIUM |
| TeraBox 6 oversized movies | BLOCKED | Seth | Awaiting NTFS-convert decision | 2026-10-05 | Seth decides | Seth's decision | LOW |
| RouteNote activation | BLOCKED | Kavi 5.0 | Watching for activation | 2026-10-05 18:41 EDT | — | Seth's login + cover-art choice | MEDIUM |
| SoundOn appeals | IN PROGRESS | Kavi 5.0 | Appeals unanswered; strategy: drop Digital Deity, proceed with 7 | 2026-10-05 18:41 EDT | Watch for replies | None | MEDIUM |
| Disability hearing prep | IN PROGRESS | Kavi 4 | Day 4/5 answers awaited; hearing Nov 12, prep call Oct 22 | 2026-10-05 | Coaching feedback on answers | Seth's answers | HIGH |
| Emby Premiere | VERIFIED | TEAM | Auto-renews; flag only on failure — no action | 2026-10-05 | None | None | LOW |
| Morning digest cron | IN PROGRESS | Kavi 4 | 22-section format + full project table + evidence labels verified in job body; delivery corrected to main chat 2026-10-05; first run 2026-10-06 08:36 EDT | 2026-10-05 | Verify first run | None | HIGH |
| kavi-mail 6h working reports | VERIFIED | TEAM | Cron live | 2026-09-30 | None — steady state | None | MEDIUM |
| kavi-mail live watch (15-min) | VERIFIED | Kavi 4 | Cron live, silent when nothing new | 2026-09-30 | None — steady state | None | MEDIUM |
| Marketplace watch (4x/day) | VERIFIED | Kavi 4 | Crons live | 2026-09-30 | None — steady state | None | LOW |
| RVG v1.5 upgrade | BLOCKED | Seth | Deliverable handed over 09-27; awaiting install + first-launch test | 2026-09-27 | Seth installs | Seth's install | MEDIUM |
| RVG multi-device admin platform | PAUSED | Kavi 4 | Connectivity-check workflow added; frozen pending GitHub App permissions | 2026-10-05 | Resume after permission grant | GitHub App lacks Actions/Admin/Secrets | MEDIUM |
| rvgctl operational test | BLOCKED | Kavi 4 | Plan at /tmp/RVG-TEST-PLAN.md | 2026-10-05 | — | Seth's go-ahead | LOW |
| RVG restore procedure | DESIGNED | Kavi 4 | Procedure ready; live test deferred (backup older than live) | 2026-10-05 | Automated restore testing (audit area 3) | None | HIGH |
| GitHub App permission expansion | BLOCKED | Kavi 4 | Feature request filed with Muse team | 2026-10-05 | Wait | Muse team action | LOW |
| BlueBubbles Apple Silicon swap | BLOCKED | Seth | Awaiting user action | 2026-10-05 | — | Seth | LOW |
| Music production (TheArtfulDodger) | IN PROGRESS | Seth | Album in progress | 2026-10-05 | Per Seth's direction | None | LOW |
| Adult channels and VOD | IN PROGRESS | Kavi 4 | Ongoing project | 2026-10-05 | Per side-chat direction | None | LOW |
| Kavi-mail live updates | IN PROGRESS | Kavi 4 | Cron live | 2026-09-30 | Due 2026-10-08 review | None | MEDIUM |
| Windham County records request | IN PROGRESS | Kavi 4 | Polite follow-up still owed | 2026-10-05 | Send follow-up | None | MEDIUM |
| Valley Vista records form | BLOCKED | Seth | Needs DOB/date/signature | 2026-10-05 | Seth completes | Seth | MEDIUM |
| Fire Stick project | PAUSED | TEAM | Vega OS — sideload impossible | 2026-09-27 | None | Platform limitation | LOW |
| iCloud → Gmail forwarding | PLANNED | Seth | 30-second task on the Mac | 2026-10-05 | Seth does it | Seth | LOW |
| Trakt authorize | PLANNED | Seth | His click | 2026-10-05 | Seth does it | Seth | LOW |
| Waveform Free 14 + sound-kit | BLOCKED | Seth | Awaiting install | 2026-09-27 | Seth installs | Seth | LOW |
| Emby regression test suite | NOT STARTED | TEAM | Audit area 7 | 2026-10-05 | Design after Layer 3 unblocks | Test user (Seth) | MEDIUM |
| Config-drift detection | VERIFIED | KAVI-4 | Deployed 2026-10-05: `C:\Users\sethr\kavitv\drift-check.py` + weekly SYSTEM task `KaviTV-Drift-Check` (Sun 06:00, first run 10/11); baseline 2026-10-05 23:11 UTC: NO DRIFT (relay v0.1.0 healthy, tasks present, C:/D:/T: present, relay hash recorded) | 2026-10-05 19:30 EDT | Monitor drift.log | 0 | MEDIUM |
| Credential/access inventory | COMPLETE | TEAM | Template created, no secret values (`kavi-team/CREDENTIAL-INVENTORY.md`) | 2026-10-05 19:30 EDT | Quarterly review | None | MEDIUM |
| AI-outage independence drill (live) | NOT STARTED | TEAM | Audit area 10; tabletop done | 2026-10-05 | Plan live drill | Seth's participation window | HIGH |
| Unified local ops dashboard | NOT STARTED | TEAM | Audit area 6; watchdog dashboard exists | 2026-10-05 | Design unified view | None | MEDIUM |
| Infrastructure/dependency map | COMPLETE | Kavi 4 | Unified map compiled (`kavi-team/DEPENDENCY-MAP.md`) | 2026-10-05 19:30 EDT | Keep current on changes | None | MEDIUM |
| Autonomous recovery matrix | COMPLETE | Kavi 4 | Matrix built (`kavi-team/RECOVERY-MATRIX.md`); actions R7/R10 await implementation | 2026-10-05 19:30 EDT | Implement R7/R10 | None | MEDIUM |
| Digest day-over-day enhancement | NOT STARTED | Kavi 4 | Audit area 11; digest cron not yet run | 2026-10-05 | Add after first digest runs | None | MEDIUM |
| Automated backup restore testing | PAUSED/NOT AUTHORIZED | TEAM | Procedure exists; live restore tests explicitly NOT AUTHORIZED by Seth (2026-10-05 ~21:48 EDT). Backup SPOF closed at backup-capability level; restore capability NOT verified until an authorized test occurs | 2026-10-05 | Await Seth's authorization | Seth's authorization | HIGH |

---

## 1. Current system state

| System | State | Evidence | Last verified |
|--------|-------|----------|---------------|
| KaviTV relay v0.1.0 (:8100) | VERIFIED healthy | /api/health ok; 302-redirect design; /api/deep-health does NOT exist (earlier "v2.1" claim retracted 2026-10-05) | 2026-10-05 19:00 EDT |
| KaviTV watchdog v2 | VERIFIED running | SYSTEM task every 5 min | 2026-10-05 |
| KaviTV sentinel (`kavitv-sentinel.py`) | VERIFIED deployed + passing | 4 SYSTEM tasks (Infra 5min / Emby 30min / Full daily 04:00 / Metadata daily 05:00); 3/3 channels "verified end-to-end" with segment evidence | 2026-10-05 19:05 EDT |
| Emby Server 4.10.1.0 | VERIFIED healthy, interactive Session 1 as sethr | API + incident recovery | 2026-10-05 15:58 EDT |
| Emby Premiere | OBSERVED active (auto-renews; flag only on failure) | Seth's revision 2026-10-05 | 2026-10-05 |
| Production GPU | VERIFIED iGPU | RX 7600 experiment rolled back, Seth-confirmed | 2026-10-05 |
| TeraBox / rclone mount (T:) | OBSERVED healthy | kavi5.0 report 18:41 ET 2026-10-05 | 2026-10-05 18:41 EDT |
| Alist (127.0.0.1:5244) | OBSERVED alive | kavi5.0 report 18:41 ET | 2026-10-05 18:41 EDT |
| RVG agent v1.20.0 | VERIFIED responding | tailnet probe via :3130 proxy | 2026-10-05 |
| Tailscale tailnet | VERIFIED connected | PC 100.124.240.93 reachable | 2026-10-05 |
| EmergencyKit (`C:\Tools\EmergencyKit\`) | VERIFIED deployed, health ALL GREEN | 11 scripts syntax-verified | 2026-10-05 |
| KaviGuard | OBSERVED running v1.4.2 | engine auto-pulled 09-30 | 2026-09-30 |

## 2. Current project state

| Project | State | Owner |
|---------|-------|-------|
| KaviTV Playback Sentinel | VERIFIED (automated layers) — 3/3 channels "verified end-to-end" 2026-10-05 ~18:55–18:57 EDT; human visual PENDING (not FAILED) | Kavi 4 |
| Canonical team state (this doc) | IN PROGRESS | Kavi 4 |
| Kavi 1–6 environment audit (11 areas) | IN PROGRESS | Kavi 4 |
| AI-outage readiness program | COMPLETE (toolkit verified, docs in Drive) | Kavi 4 |
| TeraBox verify/relink/deletes | IN PROGRESS | Kavi 3.0 (per kavi5.0 18:41 report) |
| RouteNote activation | BLOCKED on Seth (login + cover art) | Kavi 5.0 watching |
| SoundOn appeals | IN PROGRESS (awaiting replies; strategy: drop Digital Deity, proceed with 7) | Kavi 5.0 |
| UbuWeb metadata | QUEUED behind stability lock | — |
| Disability hearing prep | IN PROGRESS (Day 4/5 answers awaited; hearing Nov 12) | Kavi 4 |

## 3. Completed work (2026-10-05 unless noted)

- KaviTV relay: live v0.1.0 with 302-redirect design (verified by direct probe
  2026-10-05 ~19:00 EDT). CORRECTION: earlier "v2.1 cutover / deep-health
  VERIFIED" claims came from a compacted summary, not live state — retracted.
  `/api/deep-health` does not exist on the live relay.
- KaviTV sentinel deployed and verified: `kavitv-sentinel.py` on PC with 4
  SYSTEM scheduled tasks (Infra 5min / Emby 30min / Full daily 04:00 /
  Metadata daily 05:00). Full test 2026-10-05 ~18:55-18:58 EDT: 3/3 channels
  "KaviTV verified end-to-end." (4 segments/channel, TS sync, advancing
  bytes, session alive, PlayMethod=Transcode). Evidence: `logs/sentinel/*.jsonl`.
  Metadata check fixed (paths + tolerant parser) and VERIFIED (all PASS).
- Watchdog v2 deployed (bounded restart 3/hr, schedule horizon, Emby health, disk monitoring, status.json + dashboard.html). VERIFIED.
- Channel logos: 3/3 correct individual logos in Emby, hash-verified; exporter patched (PC + repo). VERIFIED. Do not touch unless regression.
- AI-outage readiness: 11 emergency docs (Drive), 11-script toolkit on PC (ALL GREEN), audit + REPORT.md, KaviTV snapshot to Drive, 5 scheduled-task XMLs exported. COMPLETE.
- GPU comparison: iGPU retained, RX 7600 rolled back, Seth-confirmed. COMPLETE.
- Emby incident 15:56–15:58 EDT: RECOVERED (Session 0 → scheduled-task relaunch → Session 1 healthy).
- Sentinel specification: 14 canonical docs written (`sentinel/`). COMPLETE 2026-10-05 ~19:00 EDT; STATUS.md reconciled ~19:15 EDT (relay v0.1.0 correction, Layer 3 unblocked).
- Sentinel implementation: DEPLOYED + VERIFIED 2026-10-05 ~19:15 EDT (3 tasks, 3/3 "verified end-to-end", dashboard live).
- GitHub KaviTV docs gaps closed (README.md + relay-deploy.md pushed). VERIFIED.

## 4. Pending work

- ~~Deploy `sentinel-layer2.py` to PC (chunked upload; RVG exec 400 on large payload).~~ SUPERSEDED — stream-integrity checks live inside deployed `kavitv-sentinel.py`.
- Fix `sentinel-metadata.py` paths (`C:\Users\sethr\workspace\seth-dashboard\kavitv\`). Owner: Kavi 4. DONE 2026-10-05 ~19:30 EDT (paths already correct on PC; smoke test 5/5 PASS; scheduled daily 05:00).
- Sentinel digest integration (spec complete, not built). Owner: Kavi 4.
- Emby config backup: no scheduled backup exists (SPOF). QUEUED.
- KaviTV off-PC snapshot cadence: one snapshot 2026-10-05; recurring not scheduled. QUEUED.
- Commit `sentinel/` + `kavi-team/` docs to repo. Owner: Kavi 4.
- NTFS convert of D: (6 oversized movies stranded, FAT32) — Seth's decision. QUEUED.
- Valley Vista records form (DOB/date/signature). Owner: Seth.

## 5. Blocked work

| Item | Blocked on | Owner of unblocker |
|------|-----------|-------------------|
| Sentinel test user (Option B, optional hardening) | Seth's approval (credential creation — do not create unilaterally) | Seth |
| Sentinel Layer 4 (visual test) | PENDING human check — Seth's manual Emby client test when he chooses (not a failure, not blocking) | Seth |
| RouteNote activation | Seth's login (robot checkbox) + cover-art decision | Seth |
| Emby Premiere renewal | Auto-renews; flag only on failure — NO ACTION | — |
| First formal rvgctl operational test | Seth's go-ahead on `/tmp/RVG-TEST-PLAN.md` | Seth |
| TeraBox 6 oversized movies | NTFS-convert decision | Seth |

## 6. Current incidents

(none open as of 2026-10-05 19:00 EDT)

## 7. Recovery events

- 2026-10-05 15:56–15:58 EDT: Emby interruption during authorized GPU-test restart → RECOVERED via scheduled-task relaunch into Session 1. Recovery procedure logged in `emby-transcode-decision-tree-2026-10-05.md`.
- 2026-10-05: KaviTV playback investigation. CORRECTION: earlier notes claimed a
  "v2.1 cutover"; direct probe 2026-10-05 ~19:00 EDT confirmed the live relay
  is v0.1.0 with the 302-redirect design, which Emby's LiveTV stack handles
  natively. No cutover occurred; the claim is retracted.
- 2026-10-05 19:03 EDT: Sentinel infra FAIL on all 3 channels ("playlist bytes static across 6s") → diagnosed as flaky check (6s window ≈ 6s HLS segment duration), NOT a stream failure. Fixed by widening to 15s; retest 19:08 EDT: 3/3 PASS. No relay restart was needed (evidence pointed at the check, not the stream).

## 8. Standing authorizations

**STANDING TEAM AUTHORIZATION (Seth's direct messages, main chat, 2026-10-05
~15:45 and ~16:02–16:03 EDT — VERIFIED, supersedes prior restrictions):**
Kavi 1.0, 2.0, 3.0, 4.0, 5.0, 6.0 operate as Seth's coordinated autonomous
admin team for existing systems/devices/projects/repos/storage/automation/docs,
using each agent's legitimate capabilities.

Standing scope: diagnostics, monitoring, maintenance, remote admin via
RVG/Tailscale, deploy/debug/test software, Emby/KaviTV, schedules/watchdogs,
TeraBox/rclone, RVG tooling, hardware testing, GitHub/Drive/docs, outage
toolkit, approved metadata workflows, troubleshooting, non-destructive config,
backups before changes, test+rollback.

Operating loop: detect → communicate → diagnose → back up → fix → test →
document → report.

Note: kavi5.0's 18:41 ET 2026-10-05 working report still lists this as
"awaiting Seth's direct word." It is recorded here as VERIFIED from Seth's
direct main-chat messages (~16:02–16:03 EDT). Any Kavi consulting this document
should treat the authorization as active.

## 9. Security boundaries (HARD — still in force)

- No auth/ACL bypass (Emby, Tailscale, or otherwise).
- No credential exposure or creation (except the single authorized Emby
  test user, when Seth approves).
- No unrelated network changes; no Tailscale ACL/tag/permission changes
  without Seth's explicit approval.
- No destructive/irreversible operations without explicit approval.
- No purchases, billing, or financial commitments.
- No credential or security-policy changes.
- Never move, delete, reorganize, or rename movie files on C:/D:/T:.
- Never log passwords, API keys, tokens, cookies, or session secrets.
- kavi-mail carries no secrets, ever.

## 10. Active experiments

- (none — RX 7600 GPU experiment closed/rolled back 2026-10-05.)

## 11. Decisions already made

- iGPU retained as production GPU; RX 7600 test closed (Seth-confirmed 2026-10-05).
- Emby stays interactive (never switch to service mode). AMF working; transcode-temp stays on C:.
- T: is TeraBox cloud (best-effort); never a single point of failure; C: authoritative for KaviTV runtime.
- Sentinel Layer 3 uses the existing server API key (verified sufficient 2026-10-05); Option B dedicated non-admin test user is QUEUED as optional least-privilege hardening, needs Seth's approval (credential-creation boundary).
- Stability lock in force: no production changes beyond Sentinel build-out.
- Emby Premiere: no action required (auto-renews).
- Tailscale machine key: leave as-is.
- kavi6 is dead; Kavi 4 absorbed kavi6's work (KaviTV relay + RouteNote thread) — per Seth via kavi4 2026-10-05 (recorded; kavi5.0 noted not ratified — see conflict note §16).
- SoundOn strategy: drop Digital Deity, proceed with 7 (Seth's own call).

## 12. Current configuration assumptions

- Relay: `C:\Users\sethr\kavitv\relay.py` v2.1, port 8100, SYSTEM task "KaviTV-relay".
- Tuner URLs: `http://10.0.0.98:8100/kavitv/live/<slug>.m3u8` (unchanged).
- M3U/XMLTV source: `C:\Users\sethr\workspace\seth-dashboard\kavitv\` (+ repo + Pages).
- Emby: 4.10.1.0, interactive as sethr, iGPU, AMF h264_amf.
- Channels: horror=470348, experimental=470349, independent=470350; 157 programs.
- Schedules: 7-day window, auto-regen when <2 days remain.
- Watchdog: `kavitv-watchdog.ps1` every 5 min as SYSTEM; status.json local + `T:\KaviTV\`.

## 13. Known limitations

- No Kavi has a network route that assumes another Kavi's context; side chats are independent.
- Emby API returns 401 without auth; no admin API key on file.
- RVG exec has payload limits (400 on large uploads — use chunked transfer).
- /tmp and /dev/shm wipe on VM replacement; tokens re-downloaded from Drive each session.
- TeraBox mount is cloud-backed: latency + transient drops expected.
- GitHub App `meta-muse-ai` lacks Actions/Administration/Secrets (feature request filed).

## 14. Important dependencies

- KaviTV runtime depends on: PC power/on, relay task, Emby interactive session. Does NOT depend on T: or any Kavi being online.
- Sentinel Layer 3 depends on: test-user creation (Seth).
- Morning digest depends on: kavi4 cron `kavi-team-morning-digest` (first run 2026-10-06 ~8:30 AM ET).
- kavi-mail 6h working reports depend on: each Kavi's cron.
- AI-outage toolkit depends on: PC-local scripts only (by design).

## 15. Who is currently working on what

### Active claims

```
PROJECT: KAVI-TEAM-CANONICAL-STATE
TASK: PROTOCOL-EXPANSION-AND-PUBLISH
OWNER: KAVI-4
STATUS: IN_PROGRESS
CLAIMED: 2026-10-05 19:00 EDT
NEXT_CHECKPOINT: 2026-10-06 morning digest
```

```
PROJECT: EMBY-BACKUP-DEPLOYMENT
TASK: BACKUP-JOBS-DEPLOY
OWNER: KAVI-4
STATUS: COMPLETE
CLAIMED: 2026-10-05 19:12 EDT
COMPLETED: 2026-10-05 19:14 EDT
EVIDENCE: `Emby-Config-Backup` + `KaviTV-Weekly-Snapshot` weekly SYSTEM tasks created; first runs OK (77 files / 216MB; 0.8MB zip, 0 .key files). Design doc updated to DEPLOYED.
```

```
PROJECT: BACKUP-RESTORE
TASK: EMBY-SCHEDULED-BACKUP + KAVITV-RECURRING-SNAPSHOT + RESTORE-TEST-DESIGN
OWNER: KAVI-4
STATUS: CLAIMED — assessment in progress
CLAIMED: 2026-10-05 ~19:40 EDT
NEXT_CHECKPOINT: 2026-10-06 morning digest
```
Prior claim (released):
```
PROJECT: KAVITV-SENTINEL
TASK: LAYER2-DEPLOY + METADATA-FIX
OWNER: KAVI-4
STATUS: COMPLETE — LAYER2 superseded (in-sentinel); metadata VERIFIED + scheduled daily 05:00
CLAIMED: 2026-10-05 19:00 EDT
RELEASED: 2026-10-05 ~19:30 EDT
```

| Kavi | Current work | As of |
|------|--------------|-------|
| Kavi 4 | Sentinel deployed + verified (automated); metadata path fix (next); team state maintained | 2026-10-05 19:15 EDT |
| Kavi 4 | BACKUP-RESTORE project claimed 2026-10-05 ~19:40 EDT (Emby scheduled backup SPOF + KaviTV recurring snapshot + restore-test design) | 2026-10-05 19:40 EDT |
| Kavi 5.0 | TeraBox monitoring; RouteNote/SoundOn watch; Emby Premiere watch | 2026-10-05 18:41 EDT (working report) |
| Kavi 3.0 | TeraBox verify/relink/deletes (per kavi5.0 report) | 2026-10-05 18:41 EDT |
| Kavi 1.0 | No current task on record | — |
| Kavi 2.0 | No current task on record | — |
| Kavi 6.0 | Dead; work absorbed by Kavi 4 | 2026-10-05 |

## 16. Conflicts on record

- **RVG authorization scope:** kavi4 recorded Seth's "All me" (~16:02 EDT) as
  standing authorization for Kavi 1–6; kavi5.0 (18:41 ET report) treats it as
  unverified pending Seth's direct word. Resolution: this document records it
  as VERIFIED from Seth's direct main-chat messages. kavi5.0 should consult
  this document rather than re-litigating. Restrictive state preserved in §9
  regardless.
- **kavi6 work absorption:** kavi4 absorbed kavi6's work per Seth; kavi5.0
  noted "not ratified." Recorded in §11 as decided; revisit only with new
  evidence.

## 18. Seth's ACK / authorization (2026-10-05 ~19:05 EDT)

## 19. Canonical position (Seth, 2026-10-05 ~21:48 EDT — milestone accepted)

- Emby Config Backup: VERIFIED — weekly Sunday 05:30, successful first run.
- KaviTV Weekly Snapshot: VERIFIED — weekly Sunday 04:30, secrets stripped,
  0 ".key" files confirmed.
- Drift Detection: VERIFIED — weekly, baseline NO DRIFT.
- Team HANDOFF: COMPLETE.
- GitHub push: BLOCKED — no legitimate Git credentials available; the
  no-hunting/no-workaround rule stands.
- Live restore test: PAUSED/NOT AUTHORIZED — do not perform.
- Layer 4 visual/audio KaviTV test: PENDING HUMAN CHECK.
- The backup SPOF is closed at the backup-capability level. Restore capability
  is NOT fully verified until an authorized restore test is eventually
  performed — do not claim it.
- Verified backup and monitoring systems are to be left stable; no unnecessary
  changes to completed systems. Work moves to the next highest-priority
  authorized project.

Seth acknowledged the implementation update as the current working state and
recognized as VERIFIED: canonical team state, 50-project table, team protocol,
claim/lock + stale-claim recovery, REQUEST→ACK→ACTION→RESULT, anti-loop
rules, 22-section digest, 11-area audit, dependency map, recovery matrix,
credential inventory, drift detection, Sentinel Layer 1, RVG authorization
conflict resolution.

**Binding orders:**
- Sentinel overall state held at **INFRASTRUCTURE ONLY** — do not promote
  higher until the required evidence exists (his acceptance of the evidence bar).
- Priorities: (1) Layer 2 stream-integrity implementation, (2) metadata-path
  fix, (3) continue Sentinel within the evidence model, (4) strengthen Emby
  backup/restore, (5) Emby integration testing when legitimate access exists.
- PROHIBITED without his authorization: live restore tests, privileged/test
  credential creation, live recovery drills.
- Git push stays BLOCKED without legitimate credentials; do not hunt for them.
- RVG team authorization is authoritative; do not re-litigate.
- No secrets in Gmail/GitHub/logs/docs/canonical state/Kavi messages.
- If blocked, preserve the blocker and move to the next highest-priority
  authorized project; do not stop the operation.

## 17. Links / references

- Unified GitHub + Secrets Protocol (2026-10-05, Kavi 1–6): `kavi-team/GITHUB-SECRETS-PROTOCOL.md` — system-of-record roles, secret handling, credential retrieval, GitHub security/Actions/secrets, deployment pipeline, drift classification, commit discipline, exposure incidents, git blocker status.
- Known EXPECTED drift (protocol §11): workspace holds newer files than GitHub (`kavitv-sentinel.py`, `sentinel/` docs, `kavi-team/` docs) — push BLOCKED on legitimate git credential access (§19). Staged plan: `kavi-team/COMMIT-PLAN.md`. Do not work around.
- Sentinel canonical spec: `goals/kavitv-emby-logo/files/sentinel/` (README + 12 docs + STATUS.md)
- Repo: `kellner-dot/seth-dashboard` → `kavitv/` (relay.py, generate.py, export_iptv.py, kavitv.m3u/xml, README.md, relay-deploy.md)
- Drive: `AI-OUTAGE-EMERGENCY-DOCS`; `kavi-history/` (snapshots, KAVI4-TAILNET-STATE.md, KAVI-RULES.md)
- Outage program: `goals/ai-outage-readiness/` (docs/, toolkit/, audit/, REPORT.md)
- KaviTV goal: `goals/kavitv-streaming-channels-and-emby-integration/`
- Storage arch: `goals/kavitv-emby-logo/files/kavitv-storage-architecture-2026-10-05.md`
- Emby baseline: `goals/kavitv-emby-logo/files/emby-library-baseline-2026-10-05.md`
- Transcode/GPU: `goals/kavitv-emby-logo/files/emby-transcode-decision-tree-2026-10-05.md`
- kavi-mail protocol: `~/workspace/user/files/kavi-mail-protocol-v2.0.md`
