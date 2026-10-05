# TeraBox T: Mount — Savant Optimization (2026-10-05)

## The chain

```
TeraBox cloud (throttled, signed URLs)
  → AList (TeraBox driver, WebDAV server)
    → rclone webdav remote → VFS mount → T:
      → Emby Server / KaviTV relay (:8100) → Fire TV
```

Every byte of every movie traverses all five hops. The gremlins
(buffering, "Signal is aborted without reason") can originate at any hop.

## Current setup assessment

| Setting | Current | Verdict |
|---|---|---|
| `--vfs-cache-mode` | `full` | ✅ Correct for Emby (seeks need it) |
| `--cache-dir` / max-size | `D:\rclone-cache`, 100G | ✅ Good; rewatch = free |
| `--vfs-cache-max-age` | 2 weeks | ✅ Fine |
| `--buffer-size` | **512M** | ❌ Dangerous — see below |
| `--vfs-read-ahead` | **1G** | ❌ Counterproductive — see below |
| `--vfs-read-chunk-size` | (default 128M, doubling) | ⚠️ Too aggressive for a throttled backend |
| `--dir-cache-time` | (default 5m) | ⚠️ Churns the TeraBox API on every scan |
| AList WebDAV policy | (unknown — likely 302 default) | ❌ Prime suspect — see below |
| `--network-mode` | (unknown) | ⚠️ Worth testing per rclone docs |

## Suspect #1: AList WebDAV 302 redirects → expiring signed URLs

AList's WebDAV policy has three modes ([O] alistgo/docs, 2026-09):
- **302 redirect** (default): rclone follows the redirect to TeraBox's
  *real* download URL — a signed, expiring, header-sensitive link.
- **use proxy URL**: redirect to a proxy URL.
- **native proxy**: AList streams the bytes itself — "best compatibility".

TeraBox's direct links are hostile: the CDN answers flat `403` to
requests carrying browser cookies beside the token, `dlink` must be
fetched on a clean session, and sending `dp-logid` triggers
`code 460020 need verify` ([C] mth25059-commits/videoextractbot,
verified against live TeraBox API 2026-09-04). A community doc confirms
the failure mode exactly: rclone on a 302 WebDAV gets
`IO error: vfs reader: failed to write to cache file: 403 Forbidden`
because "WebDAV doesn't support redirects" ([C] versionjun, 2026-05).

**When the signed URL dies mid-stream, Emby sees the read abort —
"Signal is aborted without reason."** This matches the symptom precisely.

**Fix:** in AList → TeraBox storage settings → **WebDAV policy =
native proxy**. All bytes then flow AList→rclone over localhost: no
expiring signatures, no 403s, no header games. Cost is nil (same PC).

## Suspect #2: 512M buffer × N handles vs a throttled backend

rclone docs ([O] rclone.org): "`--buffer-size` … The maximum memory used
by rclone for buffering can be up to `--buffer-size * open files`."
Emby library scans + playback + the KaviTV relay open many handles
concurrently. 512M × N is gigabytes of RAM for data that arrives at
~1 Mbps anyway. A production media setup dropped 256M → **32M** after
an OOM-kill wedged their whole stack, noting "with
`--vfs-cache-mode=full` already caching to disk, a large in-memory
buffer buys little" ([C] mainertoo/kubernetes-lab, 2026-09-18).

**Fix:** `--buffer-size 64M`. The disk cache (full mode) does the real work.

## Suspect #3: 1G read-ahead on a ~1 Mbps link

`--vfs-read-ahead` is disk-buffered (safe), but 1 GB of aggressive
prefetch on a throttled link means: every seek discards up to 1 GB of
fetched-then-abandoned data, burning the daily throttle quota for
nothing. Community media mounts use 32M–128M ([C] whispersofj/rawrz
2026-09: 32M chunks + 32M read-ahead; [C] kamdeme k-rclone skill:
128M read-ahead).

**Fix:** `--vfs-read-ahead 128M`.

## Suspect #4: chunk doubling vs throttling

Default `--vfs-read-chunk-size 128M` *doubles every read* with no limit —
after a few reads rclone requests multi-GB ranges. On a throttled
backend, one slow chunk stalls everything behind it.

**Fix:** `--vfs-read-chunk-size 32M --vfs-read-chunk-size-limit 1G`
(ramps gracefully; [C] izaac/nixos-config 2026-09 uses 32M/2G).

## The TeraBox throttle reality

- Free tier: **~1 Mbps downloads**, one file at a time ([O] cloudwards
  2026; [C] makeuseof: "about 1 Mbps").
- Shaping is **per CDN host, not per account** — parallel streams to
  the same host don't help; a second cookie only buys failover when
  rate-limited (`errno 400210`), not speed ([C] videoextractbot,
  2026-09-04).
- The "throttle resets overnight" behavior Seth observed matches a
  daily quota.
- Implication: **the mount cannot out-tune physics.** The strategy is
  (a) never waste a byte (small buffer/read-ahead/chunks), (b) cache
  aggressively (the 100G disk cache is the real performance layer —
  second play of anything is local), (c) pre-warm the cache for
  tonight's KaviTV schedule (copy scheduled titles to local D: like
  was done for *The Monkey*).

## Recommended mount command

```bat
rclone mount alist: T: ^
  --vfs-cache-mode full ^
  --cache-dir D:\rclone-cache ^
  --vfs-cache-max-size 100G ^
  --vfs-cache-max-age 336h ^
  --buffer-size 64M ^
  --vfs-read-ahead 128M ^
  --vfs-read-chunk-size 32M ^
  --vfs-read-chunk-size-limit 1G ^
  --dir-cache-time 72h ^
  --attr-timeout 1m ^
  --vfs-fast-fingerprint ^
  --tpslimit 10 ^
  --network-mode ^
  --log-file C:\Users\sethr\kavitv\logs\rclone-t.log ^
  --log-level NOTICE
```

Rationale deltas vs current: buffer 512M→64M (OOM safety, [O] docs),
read-ahead 1G→128M (stop burning quota, [C] community), chunks
128M-doubling→32M/1G cap (throttle-friendly, [C]), dir-cache 5m→72h
(stops API churn on scans; library is static-ish, [C] izaac),
attr-timeout 1s→1m (fewer kernel callbacks, [O] docs),
`--vfs-fast-fingerprint` (faster cache validation, [O] docs),
`--tpslimit 10` (gentle on TeraBox API, [C] dockserver),
`--network-mode` (rclone docs: try this for "unexpected program
errors, freezes" on Windows — Emby freezes qualify, [O]).

AList change (separate, in the AList admin UI): TeraBox storage →
**WebDAV policy = native proxy** ([O] alistgo/docs).

## Windows / WinFsp notes

- rclone docs ([O]): if the mount shows "unexpected program errors,
  freezes," mount as a **network drive** (`--network-mode`) instead of
  a fixed disk — Windows treats the two differently (Explorer won't
  thumbnail network drives, fewer aggressive reads).
- Drives mounted as Administrator are invisible to non-elevated apps
  (and vice versa) — mount as the same user Emby runs as, or SYSTEM
  via scheduled task ([O] rclone docs).
- `--vfs-cache-mode full` needs **sparse-file support** — NTFS is
  fine; don't put the cache on exFAT/FAT32 ([O] rclone docs).

## Verification steps

1. Check AList → TeraBox storage → WebDAV policy. If 302, switch to
   native proxy and remount.
2. Apply the new flags via the watchdog script
   (`C:\Users\sethr\kavitv\terabox-watchdog-v2.ps1`), remount.
3. `rclone rc vfs/stats` (enable `--rc` loopback) — watch for cache
   hits on replays.
4. Stream a known-good title in Emby; tail the rclone log for
   `403`, `vfs reader: failed`, or retry storms.
5. Overnight: confirm the throttle-reset pattern is quota, not mount
   failure (watchdog log timestamps vs playback failures).

## Sources

- [O] https://rclone.org/commands/rclone_mount/ (VFS buffering/caching/
  chunked-reading/Windows sections)
- [O] https://github.com/alistgo/docs/blob/HEAD/docs/guide/drivers/common.md
  (WebDAV policy: 302 / proxy URL / native proxy)
- [O] https://www.cloudwards.net/review/terabox/ (free-tier throttling)
- [C] https://github.com/mth25059-commits/videoextractbot (TeraBox CDN
  shaping, 403/session rules, errno 400210 — verified 2026-09-04)
- [C] https://github.com/mainertoo/kubernetes-lab/commit/f4a5457b9ca43f8cc008e8734539399d262a6
  (buffer 256M→32M after OOM, 2026-09-18)
- [C] https://github.com/izaac/nixos-config/commit/c2c2e78d255dd3247c3f1a543b3a123d6d09c8a8
  (32M chunks, 72h dir-cache, 2026-09-06)
- [C] https://github.com/whispersofj/rawrz/blob/HEAD/docs/stack/services/nzbdav-rclone.md
  (production media mount: 32M chunks/read-ahead, 2026-09)
- [C] https://github.com/kamdeme/agents/blob/HEAD/skills/k-rclone/SKILL.md
  (1000h dir-cache, 128M read-ahead, 2026-05)
- [C] https://github.com/versionjun/versionjun.github.io (WebDAV 302 →
  403 fix via Referer header or native proxy, 2026-05)
- [C] https://www.makeuseof.com/terabyte-cloud-storage-terrible-experience/
  (~1 Mbps free downloads)
