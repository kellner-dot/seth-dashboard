# Infrastructure / Dependency Map

**Status:** PARTIALLY COMPLETE — compiled 2026-10-05 from existing audits
(`rvg-path-audit`, `kavitv-storage-architecture`, `emby-transcode-decision-tree`).
**Target repo location:** `kellner-dot/seth-dashboard/kavi-team/DEPENDENCY-MAP.md`.

## Host: Seth's PC

| Service | Address | Depends on | If it fails |
|---------|---------|-----------|-------------|
| Emby Server 4.10.1.0 | :8096, interactive as sethr, Session 1 | iGPU/AMF, transcode-temp on C:, library paths C:/D:/T: | All playback stops; KaviTV tuners dead |
| KaviTV relay v2.1 | :8100, SYSTEM task "KaviTV-relay" | ffmpeg, schedule files in `C:\Users\sethr\kavitv\` | Tuner URLs 400/empty; Emby Live TV dark |
| KaviTV watchdog v2 | SYSTEM task every 5 min | relay :8100, Emby :8096 (public info), disk APIs | No auto-restart, no status.json |
| Alist | 127.0.0.1:5244, "Alist Server" task | — | rclone `tb:` remote breaks → T: drops |
| rclone mount (T:) | TeraBox cloud via Alist WebDAV | Alist, network, TeraBox session | T: paths vanish; Emby libraries on T: go dark (best-effort by design) |
| RVG agent v1.20.0 | 127.0.0.1:8899, Windows service | — | Remote admin path down |
| BiglyBT | — | T:\Movies (downloads), upload cap 100 KB/s | Downloads stall |
| KaviGuard v1.4.2 | — | Defender APIs | No malware watchdog |
| EmergencyKit | `C:\Tools\EmergencyKit\` | Nothing (PC-local by design) | — |

## Network

| Path | Detail |
|------|--------|
| Tailnet | 100.64.0.0/10; PC = 100.124.240.93 |
| Tailnet proxy (from Kavi VMs) | port **3130** (not 3128); TCP only |
| Emby remote | Xfinity port forward TCP 8096 → 10.0.0.98; WoL UDP 9 |
| RDP | tailnet-only, never funneled |

## Storage

| Drive | Role | Authority |
|-------|------|-----------|
| C: | KaviTV runtime (relay, watchdog, config, timeline, logs); transcode-temp | Authoritative for KaviTV |
| D: | Local movie storage | Authoritative |
| T: | TeraBox cloud (rclone VFS full cache 100GB) — existing media + KaviTV schedule area | Best-effort; never SPOF |

Standing rule: never move/delete/reorganize/rename movie files on C:/D:/T:.

## External dependencies

| Dependency | Used for | AI-outage risk |
|-----------|----------|----------------|
| GitHub (kellner-dot/*) | Code, Pages (M3U/XMLTV/logos), Actions | Code frozen locally if down; Pages cached |
| Google Drive | Emergency docs, kavi-history snapshots, tokens | Docs mirrored nowhere else — SPOF for docs |
| Emby Premiere (auto-renew) | HW transcode, tone mapping | CPU-transcode cliff on lapse |
| TeraBox session (Facebook) | T: mount | Re-auth needs Seth's click |
| Tailscale control plane | Tailnet membership | Machine key expiry drops PC off tailnet |

## Automation (this account's crons)

kavi-team-morning-digest (~8:30 AM ET) · kavi-mail-live-watch (15 min) ·
kavi4-working-report-6h · gmail-legal-medical-watch (weekday 9:30 AM) ·
marketplace 4x/day · Friday digest · Jets check · hearing-prep daily ·
Oct 15 / Oct 22 reminders.

## Single points of failure (from outage audit)

The PC itself · KaviTV code only on PC (snapshot 2026-10-05, recurring not
scheduled) · Emby config has no scheduled backup · TeraBox FB re-auth needs
Seth · Seth is sole operator.
