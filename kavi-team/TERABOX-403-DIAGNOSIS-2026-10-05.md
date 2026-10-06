# Live Incident Diagnosis: TeraBox 403 "expire time out error"

**Date:** 2026-10-05 ~22:30 EDT
**Status:** DIAGNOSED (root cause hypothesis), NOT FIXED
**Severity:** High — multiple movies unplayable from T:

## Evidence Preserved

### Timeline of failures (from C:\Users\sethr\kavitv\logs\rclone-t.log)
| Time (EDT) | File | Error |
|------------|------|-------|
| 11:43:40 | The.Fast.Runner.2001...CD2-SCHWEiK.avi | i/o timeout (transient network) |
| 15:51:22 | The.Monkey.2025.1080p.WEBRip.x264.AAC.mp4 | HTTP 403 |
| 21:00 (448 errors) | Hokum.2026.1080p.WEBRip.x264.AAC-[YTS.BZ].mp4 | HTTP 403 |
| 22:13:34–22:15:12 | Hokum.2026.1080p.WEBRip.x264.AAC-[YTS.BZ].mp4 | 403 "expire time out error" (error_code 31360), ~98s of retries |
| 22:15:40–22:15:43 | The.Fast.Runner.2001...CD2-SCHWEiK.avi | 403 "expire time out error", 11 failures in 3s, then "too many errors 11/10" |
| 22:25 (test) | A Clockwork Orange...-clearlogo.png (0.2MB) | SUCCESS (backend download worked) |

### Error signature
```
vfs cache: failed to download: vfs reader: failed to write to cache file:
HTTP error 403 (403 Forbidden) returned body: "{\"error_code\":31360,
\"error_msg\":\"expire time out error\",...}"
```

### Mount state (unchanged, verified 22:20)
- Process: rclone-terabox.exe PID 17088, running
- VFS cache: 114 files, readable (tested 4KB read: SUCCESS)
- T: mount reads for cached files: SUCCESS (4.8s for 4KB — slow but working)
- Backend small-file download: SUCCESS (0.2MB PNG at 22:25)

## Scope Determination

**NOT file-specific:** Three different movies failed (The Monkey, Hokum, Fast Runner) with identical 403 errors.

**NOT mount-wide failure:** Cached reads work. Small backend downloads work.

**NOT backend-wide outage:** Backend successfully served a 0.2MB file at 22:25.

**PATTERN: Large files fail, small files succeed.** All failures are movies (700MB–2GB+). The successful test was 0.2MB.

## Time-Dependency

Errors escalated through the day: 5 (02:00) → 5 (11:00) → 100 (15:00) → 160 (20:00) → 448 (21:00) → 482 (22:00). This is not a sudden outage — it's a progressive degradation.

The Fast Runner failure (11 attempts in 3 seconds) indicates the URL was dead on arrival, not that it expired mid-download.

## Root Cause Hypothesis

**TeraBox download URLs (dlinks) are expiring before rclone can use them for large files.**

Two sub-hypotheses:
1. **Stale URL reuse:** rclone mints a dlink when the file is first opened, caches it, and reuses it for subsequent chunk fetches. If the dlink has a short lifetime, later chunks fail with "expire time out."
2. **Mid-download expiry:** The dlink is valid when minted but expires during the long download of a large file at ~1.9 MB/s.

The 3-second/11-failure pattern favors hypothesis #1 (stale reuse) — rclone isn't even getting far enough for mid-download expiry.

**Why small files work:** A 0.2MB file downloads in <1 second, completing before any URL expiry. Large files require sustained chunk fetching over minutes, exposing the expiry.

## Cache Insulation: WORKING

Already-cached content plays fine. The VFS cache is successfully insulating playback from TeraBox for cached files. The failure only affects uncached portions requiring backend fetches.

## What This Is NOT

- NOT a credential/cookie failure (would give auth errors, not "expire time out")
- NOT a mount crash (process alive, cached reads work)
- NOT an Emby problem (failure is at rclone→TeraBox layer)
- NOT a network outage (small files download successfully)

## Minimal Fix Candidates (NOT APPLIED — for controlled testing)

1. Investigate rclone-terabox backend dlink caching behavior — does it re-mint per chunk or reuse?
2. Test whether smaller chunk sizes reduce exposure (each chunk completes faster).
3. Check TeraBox dlink lifetime documentation.
4. Consider backend-specific refresh triggers.

## Controlled Test Plan (when authorized)

1. Select a small uncached test file (not a movie Seth wants to watch).
2. Attempt download, observe whether 403 occurs.
3. If 403 occurs, capture the exact timing (how long after file open?).
4. Test with a fresh mount (remount) to see if dlink behavior resets.
5. Document results before changing any flags.

## Decision Tree Outcome

Per the directive: "If uncached files fail but cached files work → Investigate TeraBox URL lifetime and rclone's remote-read behavior."

**Verdict:** Backend-wide (for large files), URL-lifetime-related, NOT file-specific, NOT mount failure. Proceed to minimal-fix investigation, NOT general optimization.
