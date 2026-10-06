# 13 — TeraBox Playback Performance Specification

**Status:** SPECIFICATION (designed 2026-10-05, Seth-ordered). Not yet implemented.
**Companion:** KB §11 (`kavi-team/EMBY-KNOWLEDGE-BASE.md`) — field guidance for the same stack.
**Objective:** Make cloud-hosted (T:) movies behave as reliably as possible during normal,
authorized playback.

## 1. Architecture grounding (non-negotiable)

T: is a **rclone file mount**, not a streaming service. Emby reads `T:\Movies` as ordinary
files. Consequences for this spec:

- There is **no stream URL** at the Emby↔T: boundary. URL expiry/refresh happens *inside*
  rclone's TeraBox API calls. Any spec language about "refreshing the stream URL" maps to
  rclone re-minting download URLs, never to an Emby action.
- There is **no manifest** at the Emby↔T: boundary. "Refresh the manifest" maps to
  rclone directory-cache invalidation (`vfs/refresh`) or remount, never to an HLS playlist
  fetch. (Emby generates HLS only when *transcoding*; the manifest there is Emby's own.)
- There is **no segment retry** primitive in Emby for file inputs. "Retry the segment"
  maps to rclone low-level retries on chunk fetch. If ffmpeg exhausts rclone's retries
  mid-transcode, the transcode fails — recovery must happen *below* Emby, not in it.
- Labels: **IMPLEMENTED** (running today), **DESIGNED** (specified here, not built),
  **ASPIRATIONAL** (directional, needs Seth's approval before build).

## 2. Priority 1 — Core reliability

### 2.1 Stream URL expiration and refresh — IMPLEMENTED (rclone) + DESIGNED (monitoring)
- **Objective:** Detect expired/invalid stream URLs, refresh automatically, retry playback
  without user intervention.
- **Mechanism:** rclone re-mints TeraBox download URLs per API call (IMPLEMENTED,
  inherent to the mount). What Emby sees is a file; what can actually expire is rclone's
  TeraBox *session* — surfacing as total mount failure, not a per-URL error.
- **Detection (DESIGNED):** Sentinel TeraBox probe — mount present, test-read latency,
  Alist responding, `vfs/stats` sane. On session-expiry signature (all reads fail while
  process is alive), escalate: re-authentication is a human step (TeraBox login), never
  an automated credential action.
- **Recovery order:** low-level retry → remount (watchdog, IMPLEMENTED) → human re-auth.

### 2.2 Stream preflight validation — IMPLEMENTED (partial) + DESIGNED
- **Objective:** Verify source exists, endpoint responds, first bytes obtainable *before*
  playback starts.
- **Mechanism:** Mount watchdog covers "T: alive" (IMPLEMENTED). Sentinel TeraBox probe
  (DESIGNED) adds: file existence, first-1MB timed read, Alist health — the full preflight
  gate. A failed preflight must produce a clean "source unavailable" *before* Emby starts
  a doomed transcode, not a mid-movie stall.

### 2.3 Segment-level recovery — IMPLEMENTED (rclone flags)
- **Objective:** Survive transient chunk failures without terminating playback.
- **Mechanism:** `--vfs-cache-mode full` + `--vfs-read-ahead 128M` + `--low-level-retries`
  + `--retries`/`--retries-sleep` + `--timeout`/`--contimeout` on the mount (IMPLEMENTED).
  Warm cache = reads never touch the cloud = transient cloud failures are invisible.
- **Limit (honest):** Once rclone's retries are exhausted, Emby's ffmpeg fails. There is
  no Emby-side "retry this byte range." Design for prevention (warm cache, read-ahead),
  not for a recovery that doesn't exist at the Emby layer.

### 2.4 Resolver and metadata caching — IMPLEMENTED (flags) + DESIGNED (policy)
- **Objective:** Never re-query TeraBox for the same metadata twice.
- **Mechanism:** `--dir-cache-time`, `--attr-timeout`, `--vfs-cache-max-age` (IMPLEMENTED).
- **Policy (DESIGNED):** Emby library scans of T: stay off-hours; no manual full T: scans
  during viewing hours. Directory-cache invalidation only via `vfs/refresh` on known
  changed paths, never a full flush.

### 2.5 Direct Play preference — DESIGNED (policy)
- **Objective:** Avoid unnecessary transcoding; Direct Play whenever the client supports
  the media; transcode only on genuine incompatibility.
- **Why it matters for T: specifically:** Transcoding reads the *whole* file through the
  mount (cloud latency per read) *and* writes segments to transcode-temp. Direct Play is
  one sequential read — the kindest access pattern for a cloud mount, and it removes the
  transcode-temp disk from the failure chain.
- **Limit (honest):** Direct Play still stalls if T: drops mid-stream. Smaller failure
  surface, not zero cloud dependency.

## 3. Priority 2 — Intelligent source selection

### 3.1 Source health scoring — DESIGNED
Track per source (T: mount, and any future sources):
- Startup latency (mount test-read time)
- Manifest response time → maps to: directory-listing latency (`vfs/refresh` timing)
- Segment success rate → maps to: chunk-fetch success rate (`vfs/stats` errors)
- Buffering frequency (from PlaybackReporting-correlated T: playbacks)
- Recent failures (probe history)
- Average throughput (sustained read speed)

**Use:** Prefer healthy sources automatically. In the current two-tier reality (local
D: vs cloud T:), this resolves to: **prefer the local copy whenever one exists.**

### 3.2 Authorized alternate-source fallback — ARCHITECTURAL RULE (standing)
- **Rule:** If a movie exists on D: (local) and T: (cloud), the local copy is
  authoritative. Emby multi-version covers presentation.
- **Fallback order:** local D: → T: cloud → clean "unavailable."
- **Honest scope:** Per-playback automatic source switching is NOT an Emby-native
  capability. This is a procedural rule + a future Sentinel capability, not a claim
  about current behavior. Standing rule unchanged: T: is best-effort, never a SPOF —
  never depend on it as the sole copy of anything Seth cares about.

### 3.3 Adaptive quality — IMPLEMENTED (Emby) + DESIGNED (T: ceiling)
- Emby's transcode bitrate ladder already adapts to measured throughput (IMPLEMENTED).
- **T:-specific (DESIGNED):** Cap the transcode ceiling for T:-sourced content to measured
  sustained cloud throughput — measure first, don't guess.
- Suggested ladder where the source exposes multiple qualities:
  **1080p → 720p → 480p → 360p.**

## 4. Priority 3 — Playback optimization

### 4.1 Playback telemetry — DESIGNED
Track per playback: time-to-first-frame, startup time, buffering events, segment failures,
stream failures, selected resolution, bitrate, URL refreshes (rclone re-mints), source
switches, transcoding events, completion/failure.
**Sources:** Emby PlaybackReporting plugin (installed) for playback events; `rclone rc
vfs/stats` for cache hit rate and error counters; Sentinel evidence logs for probe
results. Correlate the three — a buffering event means nothing until you know whether
the cache was warm.

### 4.2 Pre-warming — DESIGNED
When a movie is selected, run lightweight validation/resolution so Play starts fast:
`rclone rc vfs/refresh` on the file path, or a sequential pre-read to warm the VFS
cache. (The 128M read-ahead already warms implicitly once playback starts; explicit
pre-warm moves that cost from first-frame time to selection time.)

## 5. Recovery sequence (Sentinel behavior)

When a T:-sourced playback fails, attempt in this order — stop at the first step that
restores health, escalate only when all are exhausted:

1. **Retry the failed read** — rclone low-level retry (automatic, inside the mount).
2. **Refresh the directory/file cache** — `rclone rc vfs/refresh` on the path (maps to
   "refresh manifest").
3. **Re-mint the backend session** — remount via the watchdog path (maps to "refresh
   stream URL"). If the signature is session-expiry (all reads fail, process alive),
   this step requires human TeraBox re-auth — escalate, do not loop.
4. **Recheck the source** — full preflight (§2.2) against T: and Alist.
5. **Try another authorized source** — local D: copy if one exists (§3.2).
6. **Fall back in quality** — 1080p → 720p → 480p → 360p (§3.3).
7. **Report failure** — only after 1–6 are exhausted, with evidence from each step.

**Anti-flapping:** A source that fails step 4 twice in a row is marked unhealthy for
30 minutes (health scoring, §3.1) — don't burn the recovery sequence on a dead source.

## 6. Acceptance criteria

Any implementation of this spec is complete only when:
- Each Priority 1 item has a working mechanism *at the layer where it operates*
  (rclone flags verified in the live mount config, watchdog tasks verified in Task
  Scheduler, probe verified in Sentinel evidence logs).
- The recovery sequence (§5) is exercised end-to-end in a controlled test (simulated
  T: outage) and each step's evidence is captured.
- Playback of a fully-cached T: movie succeeds with the network path to TeraBox
  severed (proves cache independence).
- No step requires credentials the Sentinel doesn't already hold; TeraBox re-auth
  remains a human action and is never automated.
- Tested against the Playback Sentinel acceptance criteria (spec 10-implementation-plan)
  before being marked complete — synthetic pass alone is not acceptance.

## 7. Non-goals

- Replacing rclone with a custom TeraBox client.
- Automated TeraBox login/re-authentication (human-only, always).
- Moving the T: mount's cache off C: without Seth's explicit approval.
- Any change to movie files on C:/D:/T: (standing rule).
- Promising "as reliable as local" — the honest target is "as reliable as a
  well-managed cloud mount can be," with local copies authoritative.
