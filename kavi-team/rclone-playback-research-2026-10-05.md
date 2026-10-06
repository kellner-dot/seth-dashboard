# Savant Research Report: rclone Cloud-Mount Media Playback Optimization

**Date:** 2026-10-05 | **Researcher:** Kavi 4.0 (subagent) | **For:** TeraBox/rclone T: playback implementation
**Scope searched:** rclone forum (forum.rclone.org), rclone GitHub issues, Reddit-indexed results, Emby community, Unraid forums (3.4k-reply rclone mega-thread), LowEndTalk, DEV.to, GitHub configs (animosity22, izaac, mainertoo, haradascyb, decypharr), Alist+Emby projects. Discord communities not accessible; direct Reddit hits limited.

---

## 1. Executive summary — the 5 things that matter most

1. **TeraBox free download speed (~1.7–1.9 MB/s) is the hard ceiling.** Per the unofficial TeraBox backend docs, multithreaded and single-threaded downloads run the same speed on free accounts (~1.7–1.9 MB/s; ~8 MB/s premium). A 1080p movie at 10–15 Mbps needs 1.25–1.9 MB/s *sustained* — right at the free limit. This means high-bitrate content is fundamentally bandwidth-marginal on a free account, and the VFS cache + read-ahead is what makes playback viable at all (burst ahead during low-bitrate scenes, coast through peaks). **Measure sustained TeraBox throughput first; it bounds everything else.**
2. **`--buffer-size` is per open file handle — the #1 OOM/footgun.** Multiple independent sources confirm: buffer-size multiplies by concurrent open files. 256M × a handful of streams OOM-killed a 1GiB-limited container (mainertoo, 2026-09). The 2020 rclone forum advice still holds: "the bigger the buffer, the more buffering you will have" — large buffers get dropped on close and the work is wasted. With `--vfs-cache-mode full` already caching to disk, a large in-memory buffer buys little. **Consensus: 16–32M, not 256M+.**
3. **Emby's library scan/ffprobe can download entire files.** An Emby community member proved (2021) that with thumbnail generation OFF, Emby's ffprobe during scan still pulled *complete copies* of all 6 test files into the rclone cache. Emby seeks through the whole file during media analysis. **Mitigation: long `--vfs-cache-max-age` (keep analyzed files cached), schedule scans off-hours, disable trickplay/chapter-image generation on cloud libraries** (a 2026 Jellyfin homelab audit found trickplay tasks churning a 20GB cache every morning and evicting the evening's viewing).
4. **There is a known rclone bug where a transient backend outage causes cached files to read as 0 bytes** (rclone/rclone#9530, v1.73.x, still open). When the remote is momentarily unreachable, the VFS layer treats "couldn't reach remote" identically to "remote deleted" and discards clean cached items. For TeraBox (cookie-auth, unofficial backend), session blips are the exact trigger. **Design the Sentinel recovery path around this: on backend blip, do NOT trust cache state until the backend is confirmed reachable.**
5. **The 10x alternative: bypass the mount for playback entirely.** `bpking1/embyexternalurl` (emby2Alist) uses nginx+njs to intercept Emby playback URLs and 302-redirect to Alist-generated direct links. The user already runs Alist. This collapses TeraBox→Alist→rclone→Emby into TeraBox→client. Worth evaluating as the long-term architecture; the rclone mount stays for library scans/metadata.

---

## 2. Key findings (with sources)

### VFS / read-path tuning
- **F1. `--vfs-read-chunk-size 128M` (default) is the community sweet spot; don't go below 64M.** rclone does HTTP range requests, doubling chunk size to reduce API calls on sequential reads. (rclone forum, wavlinky, 2020-08-01 — https://forum.rclone.org/t/some-help-with-rclone-mount-for-plex-buffering-everywhere/18201?page=2)
- **F2. Growing chunk size helps high-latency backends:** `--vfs-read-chunk-size 32M --vfs-read-chunk-size-limit 2G` lets sequential playback ramp up instead of issuing many small ranged reads. (izaac/nixos-config, 2026-09-06 — https://github.com/izaac/nixos-config/commit/c2c2e78d255dd3247c3f1a543b3a123d6d09c8a8)
- **F3. `--vfs-read-ahead` + `--buffer-size` interplay:** One tester found playback started *immediately* with `--vfs-cache-mode off --vfs-read-ahead 16Mi --vfs-read-chunk-size 256Mi --buffer-size 1Gi`, while a small read-ahead left 30s startup delay. Counter-advice from a veteran: "remove buffer-size altogether and just use 1G read ahead." (rclone forum, 2022 — https://forum.rclone.org/t/option-vfs-read-ahead-has-no-effect/32259)
- **F4. Measured numbers (2026-09):** untuned warm delivered ~1.2 MB/s vs raw 17 MB/s single-stream on the same backend; adding `--buffer-size 128M` + `--vfs-read-ahead 256M` + `--transfers 8` + large growing chunk size restored backend-speed fills. Cost documented: buffer is per open file (N×128M RAM). (mthines/sync-tray — https://github.com/mthines/sync-tray/commit/5c7f524b86704ca309f81aad6f6f4ea9f01faaa2)
- **F5. `--vfs-cache-mode full` "takes rclone out of the mix" once the file is cached** — buffering frequency dropped significantly for 4K remuxes; remaining buffering was diagnosed as pure bandwidth (player-side tiny buffers). A ~95 Mb/s movie showed the expected read-ahead spike at start. (rclone forum, 2020-12 — https://forum.rclone.org/t/sudden-buffering-when-streaming-high-bitrate-4k-content-on-plex/21073)

### Metadata / directory caching
- **F6. `--dir-cache-time` 72h–160h is standard for media libraries; the 5m default causes re-fetch storms.** A 6300-entry library cost ~13 sequential API round trips per listing, re-fetched every 5 min during scans (~34% sustained I/O). Fix: `--dir-cache-time 72h` + raise `--attr-timeout` from 1s (Plex/Emby stat every file). (izaac/nixos-config, 2026-09)
- **F7. Pair with `rclone rc vfs/refresh recursive=true` ("priming") after mount** to cache the file/folder structure up front for much faster reads; re-run after changes. Especially valuable when the backend has no change notification. (rclone forum Windows Plex user, 2020 — https://forum.rclone.org/t/plex-playing-buffering-stoppage-rclone-mount-issues/16037?page=2)
- **F8. `--no-modtime` "can speed things up"** (fewer metadata round trips). `--vfs-fast-fingerprint` used in production Plex mounts to speed change detection. (rclone mount help output; forum.rclone.org/t/union-rclone-mount-last-modified-timestamp-plex/47609)

### Reliability / failure behavior
- **F9. BUG (open): transient backend outage → cached files discarded → 0-byte reads.** `--vfs-cache-mode full`, clean cached item removed as "stale (remote deleted)" when the remote is merely *unreachable*; next read returns `n=0, EOF`. Backend-agnostic, in the VFS layer (`vfs/vfscache/item.go` `_checkObject`). Observed v1.73.x. (rclone/rclone#9530 — https://github.com/rclone/rclone/issues/9530)
- **F10. Never run two rclone processes sharing one VFS cache dir with overlapping remotes** — documented corruption risk; give each its own `--cache-dir`. (rclone docs via forum.rclone.org/t/vfs-cache-overlap/44002)
- **F11. Stale mounts don't self-heal:** dead FUSE mount ("transport endpoint is not connected") blocks remount ("directory already mounted"); fix = lazy unmount before mount (`fusermount3 -uz` / `umount -l` fallback) in the mount supervisor. (mainertoo/kubernetes-lab, 2026-09 — https://github.com/mainertoo/kubernetes-lab/commit/f4a5457b9ca43f8cc008e8734539399d262a6567)
- **F12. Config/credential changes require a remount** — rclone reloads rclone.conf but the running mount keeps using old credentials → persistent I/O errors until restart. (rclone/rclone#9441 — https://github.com/rclone/rclone/issues/9441)
- **F13. Retry/timeout defaults are generous:** `--low-level-retries 10`, `--retries 3`, `--timeout 5m`, `--contimeout 1m`. On flaky links, *lower* timeouts so failures surface in seconds not minutes. (dev.to, 2026 — https://dev.to/john_182319291/rclone-mount-vs-rclone-bisync-after-dropbox-the-real-latency-ram-and-conflict-numbers-1jlk)
- **F14. A mount fails loudly into the application:** dropped link mid-read surfaces as EIO to Emby/ffmpeg; if the FUSE process dies you get "transport endpoint is not connected" until remount. (same source as F13)

### Emby-specific
- **F15. Emby ffprobe pulls whole files during scans** (see §1.3). Even with thumbnails off and hash-match off, 6/6 test files were fully downloaded to cache; ffprobe timed out waiting on the file provider. (Emby community, 2021 — https://emby.media/community/index.php?/topic/90380-minimize-media-analysis-rclonegdrive/)
- **F16. Trickplay/intro-skip tasks churn the VFS cache.** 14-day audit: trickplay ran 6h every morning pulling 506–521 Mbit/s, filling a 20GB cache and evicting the evening's viewing; fix = trickplay weekly, intro-skipper 2 threads, `--vfs-cache-min-free-space` as eviction guard, `vfs/stats` + `core/stats` scraped to Telegraf. (haradascyb/groscailloux-homelab, 2026-09 — https://github.com/haradascyb/groscailloux-homelab/commit/f86d165eb2999b8513e48b6ff2b65433fbf4eaf3)
- **F17. An Emby-on-Windows rclone user reports no buffering with a *minimal* config:** `--vfs-cache-mode=minimal --dir-cache-time=5m --read-only --allow-other` + latest WinFsp. Simpler than the Plex maximalist configs. (jojothehumanmonkey/asdffdsa, rclone forum, 2020-04 — https://forum.rclone.org/t/rclone-cache-vs-vfs-for-plex-and-gdrive-on-windows/15612)

### TeraBox-specific
- **F18. Unofficial cookie-auth backend; no official API.** All TeraBox rclone backends are third-party forks (rclone-extra, bclone); cookie live period ~1 year; auth breaks = full mount failure until human re-auth. (gulp79/rclone-extra docs — https://github.com/gulp79/rclone-extra/blob/HEAD/docs/content/terabox.md)
- **F19. Download ~1.7–1.9 MB/s free / ~8 MB/s premium; multithread == single-thread speed.** Upload ~15 MB/s both tiers. 4GB max file (free) / 128GB (premium). If uploads stall, try `--timeout=15s`; some regions need the alternate `nephobox.com` domain. (same source)
- **F20. The user's actual path is TeraBox → Alist (WebDAV :5244) → rclone → T: → Emby** — two network hops before Emby. Alist is the component that converts TeraBox into direct links; the emby2Alist project (F21) exploits exactly this.
- **F21. 10x alternative — emby2Alist:** nginx + njs intercepts Emby playback URLs and redirects to Alist direct links; tested with OneDrive/Google Drive/Aliyun Drive; does not modify Emby or rclone configs. (bpking1/embyexternalurl — https://github.com/bpking1/embyexternalurl/blob/HEAD/emby2Alist/README.md)

### Windows / WinFsp
- **F22. `--max-read-ahead` is NOT supported on Windows** (kernel read-ahead capped at 128Ki there) — `--vfs-read-ahead` (rclone-level) is the knob that matters on Windows. (rclone mount help)
- **F23. `--network-mode` (Windows-only):** mount as network drive vs fixed disk. Some apps behave better with one or the other; Emby should be tested both ways. (rclone mount help)
- **F24. Windows Plex+rclone users run for years with `--buffer-size 256M --dir-cache-time 1000h --read-only --timeout 1h`** + priming via `vfs/refresh`. Read-only mount for playback; separate read/write mount only for organizing. (rclone forum, 2020 — https://forum.rclone.org/t/plex-playing-buffering-stoppage-rclone-mount-issues/16037?page=2)
- **F25. Keep WinFsp current** — old WinFsp versions are a known source of mount weirdness on Windows. (F17 source)

---

## 3. Recommended mount flags for media playback (with WHY)

Baseline philosophy (cross-checked across ≥2 sources each): **cache-mode full, small buffer, long dir cache, generous read-ahead, explicit timeouts, primed on start.** Tune against measured TeraBox throughput (§5), not by maximizing values.

| Flag | Suggested value | Why (problem it solves) |
|---|---|---|
| `--vfs-cache-mode full` | full | Reads served from local disk once cached; "takes rclone out of the mix" for repeat viewing (F5). Already in use. |
| `--buffer-size` | `32M` (not 256M+) | Per-open-file RAM; 256M×N streams OOMs (F11). With cache-mode full, big buffers buy little (F11, F1-2020). Current setup should be checked — if it's large, this is the first change. |
| `--vfs-read-ahead` | `256M`–`1G` | Prefetches ahead of the read position at backend speed; hides TeraBox latency and smooths bitrate peaks (F3, F4). Unraid guide uses 1G (forums.unraid.net, p135). |
| `--vfs-read-chunk-size` | `128M` (default) | Fewer, larger range requests; don't go below 64M (F1). |
| `--vfs-read-chunk-size-limit` | `off` or `2G` | Lets chunks grow for long sequential reads (fewer round trips) (F2). |
| `--dir-cache-time` | `72h`–`160h` | Stops re-listing storms during Emby scans (F6). |
| `--attr-timeout` | match dir-cache-time (e.g. `72h`) | Emby stats every file on scan; 1s default = constant re-stat (F6). |
| `--no-modtime` | set | Skips modtime round trips; media libraries don't need them (F8). |
| `--vfs-fast-fingerprint` | set | Faster change detection for large libraries (F8). |
| `--poll-interval` | `0` (disable) or `60s` | TeraBox/Alist has no change notification; polling a dead endpoint wastes cycles. With long dir-cache-time, use explicit `vfs/refresh` instead (F7). |
| `--vfs-cache-max-age` | `336h` (already) / `168h`+ | Keep analyzed/cached movies warm; Emby's ffprobe downloads whole files (F15) — evicting them means re-downloading on every scan. Already 336h; keep. |
| `--vfs-cache-max-size` | `100G` (already) | Already set. Pair with `--vfs-cache-min-free-space` (e.g. 20G on C:) so cache eviction never fills the disk (F16). |
| `--timeout` / `--contimeout` | `30s`/`15s` (tune down from 5m/1m) | Fail fast on blips so the watchdog/remount path engages in seconds, not minutes (F13). |
| `--low-level-retries` | `10` (default OK) | Absorbs transient chunk failures inside rclone (F13). |
| `--retries` / `--retries-sleep` | `3` / `10s` | Top-level retry behavior. |
| `--transfers` | `4`–`8` | Parallel chunk fetchers; 8 restored backend-speed fills in measurements (F4). |
| `--read-only` | set (for the playback mount) | Playback never writes; eliminates whole classes of cache/writeback issues (F24). |
| `--rc --rc-no-auth --rc-addr 127.0.0.1:5572` | set | Enables `vfs/refresh`, `vfs/stats` for priming + Sentinel telemetry (F7, F16). Loopback-only. |
| `--vfs-cache-poll-interval` | `5m` | How often the cache is scanned for stale objects. |

**On mount start (prime):** `rclone rc vfs/refresh recursive=true --fast-list` — caches the whole tree up front (F7).

---

## 4. Anti-patterns / what to avoid (with failure evidence)

- **A1. Giant `--buffer-size` (256M–1G).** Evidence: OOMKill at 1GiB with a handful of streams; "the bigger the buffer, the more buffering you will have" — buffers are dropped on file close, work wasted. Use 16–32M. (F11; forum.rclone.org 2020)
- **A2. `--drive-chunk-size` on a mount.** It only affects uploads (copy/move/sync), does nothing for reads — cargo-culted from upload guides into mount commands. (forum.rclone.org 2020, wavlinky)
- **A3. `--tpslimit` / `--tpslimit-burst` tweaks to "go faster."** Causes random errors; defaults already match provider limits. (same)
- **A4. Two rclone processes sharing one `--cache-dir` with overlapping remotes.** Documented corruption risk. (F10)
- **A5. Emby trickplay / chapter-thumbnail / intro-detection tasks against the cloud library on defaults.** They sequentially read whole files and churn the VFS cache, evicting the movies you actually watch. Schedule weekly/off-hours or disable for T: libraries. (F16)
- **A6. Assuming the cache is valid after a backend blip.** rclone#9530: unreachable remote = cached files discarded as "deleted" → 0-byte reads. Any "resume" logic must re-verify backend reachability first. (F9)
- **A7. Blindly copying "max everything" configs.** The mthines measurement (F4) shows tuning must be validated against *your* backend's actual throughput; TeraBox free at ~1.9 MB/s behaves nothing like Google Drive at 1 Gbit.
- **A8. `--allow-non-empty` on the mountpoint.** Masks stale mounts (mounting over a dead mount hides the problem). (forum.rclone.org 2020, wavlinky)

---

## 5. TeraBox-specific gotchas

- **G1. The ~1.9 MB/s free ceiling is the whole game.** 1080p ≤8 Mbps (~1 MB/s) is comfortable; 1080p remux 15–25 Mbps (2–3 MB/s) EXCEEDS sustained free throughput — only the VFS cache + read-ahead (burst during low-bitrate scenes) makes it playable. 4K remux on free TeraBox is not realistically sustainable uncached. **Recommendation: measure with `rclone copy` of a 1GB test file; set Emby's remote-bitrate cap from the measured number, not from hope.**
- **G2. Cookie auth = human re-auth on expiry.** ~1-year cookie life; when it dies the mount fails totally (not gracefully). The Sentinel TeraBox probe must distinguish "cookie dead" (needs Seth) from "transient blip" (auto-recover). No automation can or should re-auth. (F18)
- **G3. Multithread doesn't help TeraBox.** Measured identical speeds for `--multi-thread-streams 1` vs multithread — don't expect `--transfers`/`--multi-thread-streams` to multiply TeraBox throughput the way they do on S3/GDrive. (F19)
- **G4. Two-hop path (TeraBox→Alist→rclone).** Every byte crosses localhost WebDAV between Alist and rclone. Failure/telemetry must cover Alist (127.0.0.1:5244) as its own layer — an Alist stall looks identical to a TeraBox stall from rclone's side. (F20)
- **G5. Upload limits irrelevant for playback, but the 4GB free file cap matters** for what can even be stored. (F19)

---

## 6. Windows / WinFsp-specific notes

- **W1. Use `--vfs-read-ahead`, not `--max-read-ahead`** — the latter is not supported on Windows. (F22)
- **W2. Test `--network-mode` vs fixed-disk presentation** for Emby — some Windows apps enumerate/behave differently on network drives (no official verdict found; needs testing).
- **W3. Keep WinFsp updated** — stale WinFsp is a recurring background cause of mount weirdness. (F25)
- **W4. No `--daemon` on Windows** — the mount runs attached; the existing scheduled-task supervisor pattern (SYSTEM task + auto-restart) is the correct Windows substitute. Already in use.
- **W5. `--allow-other` is a no-op concept on Windows** (no Unix uid/gid); don't cargo-cult Linux mount lines. The SYSTEM-run task already sidesteps permission issues.
- **W6. Read-only playback mount + separate RW mount** is the proven Windows pattern (F24): daily playback never writes, so `--read-only` removes writeback/cache-dirty failure modes.

---

## 7. Emby-specific considerations (vs Plex)

- **E1. Emby's media analysis is heavier than Plex's for cloud mounts:** ffprobe seeks pull entire files into cache even with thumbnails off (F15). Keep `--vfs-cache-max-age` long and scans off-hours.
- **E2. Intro detection / trickplay / chapter images** are the cache-churners (F16). For the T: library: disable or schedule weekly.
- **E3. Emby transcodes read the whole file through the mount** — Direct Play (one sequential read) is strictly kinder to a cloud mount than transcoding (full-file read + segment writes). This corroborates the spec's Direct Play preference from an independent angle.
- **E4. The emby2Alist redirect (F21) is Emby/Jellyfin-specific** — Plex has no equivalent hook. It's the single biggest architectural lever available *because* the stack is Emby+Alist.

---

## 8. Open questions needing testing

1. **Measured TeraBox throughput** from this PC (free or premium account?): the single number that bounds all bitrate decisions. Test: `rclone copy tb:Movies/<1GB file> NUL` timed.
2. **`--buffer-size` current value** on the live mount — if it's 256M+, reducing to 32M is the cheapest win available.
3. **`--network-mode` on/off** for Emby library + playback behavior on Windows.
4. **Does `--vfs-read-ahead 1G` measurably beat 128M** on TeraBox's ~1.9 MB/s link, or does it just waste the first 8 minutes of buffering? (At 1.9 MB/s, 1G read-ahead = ~9 min to fill.)
5. **emby2Alist feasibility**: does the nginx+njs redirect work with this Emby version (4.10.x) and TeraBox direct links (which may themselves be short-lived)? If yes, it's the 10x.
6. **rclone version on the PC** — rclone#9530 (0-byte reads on blip) observed on v1.73.x; confirm version and whether the fix has landed.
7. **Cache-churn audit**: is anything (Emby scheduled tasks, trickplay) currently churning `C:\rclone-cache\`? Check task history + `vfs/stats`.

---

## 9. What I couldn't verify

- **Direct Reddit threads**: `site:reddit.com` searches returned nothing usable; Reddit knowledge here is secondhand via indexed summaries. r/rclone, r/Plex, r/DataHoarder likely hold relevant threads but weren't directly retrievable.
- **Discord communities**: not accessible to research.
- **rclone.org official docs**: flag defaults cited above come from community citations (dev.to latency article, mount `--help` output mirrors) — cross-checked across ≥2 community sources, but I did not pull the official docs pages directly.
- **Alist→rclone WebDAV throughput overhead**: no published measurements found for the double-hop; needs local measurement.
- **Whether TeraBox direct links (via Alist) support HTTP range requests**: required for both rclone chunk reads (works today, so yes at the Alist layer) and for any emby2Alist seeking (unverified).

---

## 10. Suggested next actions for the parent agent

1. Measure TeraBox throughput (Q1) — 5-minute test, bounds everything.
2. Audit the live mount command for `--buffer-size` and other flags (Q2).
3. Apply the §3 flag set (minus anything already set) as a *staged* change: one variable at a time against the playback baseline, per the directive.
4. Evaluate emby2Alist (Q5) as the strategic alternative before over-investing in mount tuning.
5. Record results in the research-trail format per the standing rule.
