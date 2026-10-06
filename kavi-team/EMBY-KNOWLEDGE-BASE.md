# Emby Server Troubleshooting Knowledge Base

**Purpose:** Cumulative, field-tested Emby Server troubleshooting knowledge for the Kavi team.
Standing requirement (Seth, 2026-10-05): become Emby error/fix savants — every Emby failure gets
its exact error identified, the subsystem traced, docs + community researched, causes distinguished
(confirmed vs hypothesis), and the reusable diagnostic pattern preserved here.

**Standing rule:** When a new Emby error appears, check this KB *before* reinventing the investigation.

**Diagnostic pattern (apply to every error):**

```
ERROR → LIKELY LAYER → EVIDENCE TO COLLECT → CONFIRMATION TEST → SAFE FIX → VERIFICATION → ROLLBACK
```

**Claim labels used below:** CONFIRMED (official Emby docs/source), COMMUNITY-REPORTED (forum/GitHub, with URL),
INFERRED (our reasoning — never treat as confirmed).

**Applies to:** Emby Server 4.10.x on Windows unless noted.
**Last updated:** 2026-10-05

---

## 1. Live TV M3U Tuner Failures

### Error signatures (exact text)
- `Emby.Server.Implementations.LiveTv.TunerHosts.M3UTunerHost: Error opening tuner` followed by
  `MediaBrowser.Controller.LiveTv.LiveTvConflictException: M3U simultaneous stream limit has been reached.`
  (trace: `M3UTunerHost.GetChannelStream` → `BaseTunerHost.GetChannelStream`) — COMMUNITY-REPORTED with full
  server-log trace: https://github.com/jellyfin/jellyfin/issues/4817
- Client-visible: "Playback Error — No compatible streams are currently available" on Live TV after working
  fine for months; fix was delete + re-add the tuner device — COMMUNITY-REPORTED:
  https://emby.media/community/topic/42954-playback-error-no-compatible-streams-are-currently-available/

### Generating subsystem
`Emby.Server.Implementations.LiveTv.TunerHosts.M3UTunerHost` (tuner open) and
`Emby.Server.Implementations.LiveTv.LiveTvManager` ("Opening channel stream from Emby").

### What it means
Emby's LiveTV engine opened the tuner URL and either (a) the tuner's configured simultaneous-stream limit
was already consumed, or (b) the tuner host threw opening the channel stream. The LiveTvConflictException
path is *not* a source failure — it is Emby refusing to open another stream because its own counter says
the tuner is full.

### Known causes
- **CONFIRMED (code trace):** stale/orphaned live streams holding tuner slots. Emby tracks `currentLiveStreams`
  per tuner; a session that never closed (crashed client, killed ffmpeg, leaked session) keeps consuming a slot.
  Evidence in logs: `MediaSourceManager: Live stream "<guid>" consumer count is now 0` / `Closing live stream`
  lines are the *healthy* release path — their absence after a stop means the slot leaked.
- **COMMUNITY-REPORTED:** M3U tuner config "fumbled" internally — tuner reachable by browser at the same IP,
  yet Emby fails until the tuner device is deleted and re-added under Live TV → Tuner Devices.
- **COMMUNITY-REPORTED:** stuck paused LiveTV connections on Fire TV/Roku that cannot be stopped from the
  dashboard, causing "maximum streaming limit" errors for the same user:
  https://emby.media/community/index.php?/topic/133182-issue-with-some-connections-getting-stuck-and-hitting-stream-limit/
- **INFERRED:** synthetic/probe clients (Sentinel, health checks) that open PlaybackInfo sessions without
  closing them accumulate as phantom tuner consumers, eventually tripping the limit for real clients.

### Evidence to collect
- `GET /emby/Sessions?api_key=` — list all sessions; look for stale clients (e.g. probe/sentinel names) with
  no activity and LiveTV `NowPlayingItem` entries.
- Server log: `M3UTunerHost: Error opening tuner`, `LiveTvConflictException`, `LiveTvManager: Opening channel stream`.
- Dashboard → Live TV → tuner device → check "simultaneous stream limit" value.

### Confirmation test
Count active live streams in the log for the tuner vs its limit; try playback on a *different* channel on the
*same* tuner — if all channels on that tuner fail identically while other tuners/sources work, the tuner slot
counter (not the source) is the prime suspect.

### Safe fix + why it works
1. Stop the stale sessions (Dashboard → Active Devices → stop; if that fails, restart Emby Server — the
   counters are in-memory). Why: releases the leaked tuner slots.
2. If no stale sessions exist but the error persists: delete and re-add the M3U tuner device, then refresh
   guide data. Why: rebuilds Emby's persisted tuner/provider record, which community evidence shows can
   silently desync.
3. Set an explicit simultaneous-stream limit ≥ expected concurrent clients.

### Verification
New playback attempt opens a tuner without `LiveTvConflictException`; log shows
`LiveTvManager: Opening channel stream` → successful segment flow.

### Rollback
Re-adding the tuner changes channel IDs/mappings — back up Emby config (or the `livetv` data folder) first;
restoring the backup restores the old tuner record.

---

## 2. "No compatible streams are currently available"

### Error signatures
- Client popup: `Playback Error — No compatible streams are currently available. Please try again later or
  contact your system administrator for details.` — COMMUNITY-REPORTED (many threads, e.g.
  https://emby.media/community/topic/42954-playback-error-no-compatible-streams-are-currently-available/)
- Server-side it is *usually* the visible face of a deeper failure: tuner conflict (see §1), ffmpeg that
  never started (§5), or media that ffprobe could not identify.

### Generating subsystem
`Jellyfin.Api.Helpers.MediaInfoHelper` / `StreamBuilder.BuildVideoItem` decides PlayMethod per client profile;
when nothing is eligible (DirectPlay false, no DirectStream profile, transcode impossible or failed), the
client renders this message.

### What it means
The server could not construct *any* playable path for that client+item combination. It is a *symptom*, not a
root cause — the server log at the time of the `POST /Items/{id}/PlaybackInfo` request names the real cause.

### Known causes
- **CONFIRMED (log trace):** tuner limit reached on Live TV (§1) surfaces to PlaybackInfo as this error.
- **COMMUNITY-REPORTED:** ffmpeg broken/missing → `System.Exception: Error starting ffmpeg`; one TrueNAS case
  fixed by reinstalling ffmpeg (corrupt ffmpeg install):
  https://emby.media/community/index.php?/topic/68694-playback-error-no-compatible-streams-are-currently-available/page/3/
- **COMMUNITY-REPORTED:** wrong codec metadata handed to Emby (e.g. a proxy reporting source codec instead of
  the codec it actually outputs) → Emby configures the wrong decoder and ffmpeg exits before any frame:
  `Invalid NAL unit` lines then `Error starting ffmpeg`:
  https://github.com/firestaerter3/emby-xtream/releases/tag/v1.4.97-beta
- **COMMUNITY-REPORTED:** special characters in file names (`#`, `|`) can trigger it on some paths.
- **CONFIRMED (release notes):** sporadic "no compatible streams" on multi-version episodes from Continue
  Watching was an Emby bug fixed in 4.8.x (FileHorse changelog) — check server version before deep diagnosis.

### Evidence to collect
- The `POST /Items/{id}/PlaybackInfo` request in the server log and the lines immediately after it
  (`MediaInfoHelper: User policy...`, `StreamBuilder.BuildVideoItem(...) => (PlayMethod=...)`).
- If PlayMethod=Transcode: the matching `ffmpeg-transcode-{guid}.txt` log (§10).

### Confirmation test
Replay the same PlaybackInfo request and read the resulting PlayMethod/TranscodeReasons. If it says
Transcode but no ffmpeg-transcode log is created, the failure is in ffmpeg startup (§5), not stream choice.

### Safe fix + why it works
Fix the underlying cause (§1, §5, §7) rather than the message. For the "tuners desynced" variant: delete +
re-add the tuner device. Why it works: see §1.

### Verification / Rollback
Same channel plays; PlaybackInfo returns a concrete PlayMethod with a working media URL. Rollback = restore
config backup if tuner re-add changed mappings.

---

## 3. HTTP 302 Redirect Handling in Live TV Tuners and Direct Play Paths

### What it means
A tuner that answers the channel URL with `302 Found` pointing at the real stream (e.g. a bridge/proxy that
mints short-lived HLS URLs) is a *supported and common* pattern — COMMUNITY-REPORTED, documented by a
third-party Emby/Jellyfin bridge: https://github.com/cbodden/fbtv/blob/HEAD/docs/EMBY_SETUP.md

### Known behavior (community-documented, matches our KaviTV relay design)
- **Same host / same egress is the best topology for the default 302 redirect.**
  Quoted guidance: *"Prefer same machine or same public egress IP for Emby and the bridge."*
- **Remote Emby over Tailscale/VPN with the bridge elsewhere often breaks 302 HLS redirects "because the
  stream URL was minted for a different IP"** — the recommended alternatives are shared egress or having the
  bridge remux/proxy the stream itself (`STREAM_PROXY` mode).
- A `HEAD`/`curl -I` probe of the tuner URL returns 200 and does *not* mint a stream; only a real `GET`
  follows the 302 chain. (Implication for health checks: HEAD probes can pass while GET playback fails.)
- **INFERRED for our setup:** our relay 302s *back into Emby itself* (`/emby/Videos/{id}/master.m3u8?...&api_key=...`).
  That keeps everything on one host (good per the guidance above), but it means the chain is
  Emby LiveTV → relay → 302 → Emby HLS → ffmpeg probe of the media item. Any auth/session hiccup on that
  self-referential hop (e.g. api_key handling, localhost vs LAN address, PlaySessionId binding to the
  *LiveTV* session vs the *Videos* session) breaks playback while direct-relay probes still pass — exactly
  the "synthetic checks pass, real playback fails" discrepancy pattern.

### Evidence to collect
- `curl -v` the tuner URL from the *Emby host itself*: confirm 302, inspect the `Location:` target.
- Then `GET` the Location target from the Emby host: confirm the variant playlist returns 200.
- Server log: does Emby's LiveTV engine log following the redirect, or does it error before the HLS request?
- Compare the `api_key` behavior: does the key in the 302 survive Emby's own request pipeline?

### Confirmation test
Bypass test: point the M3U tuner channel URL (temporarily, on a *test* tuner entry — never the production
one) directly at the final HLS URL. If that plays while the 302 path fails, the redirect hop is implicated.

### Safe fix + why it works
- Prefer tuner URLs that resolve on the same host Emby runs on (matches community guidance).
- If the 302 target is IP-sensitive, ensure the minted URL uses an address Emby itself can reach
  (127.0.0.1 vs LAN IP vs Tailscale IP behave differently — see §9 network notes).

### Verification / Rollback
PlaybackInfo → master.m3u8 → media playlist → segments all return 200 in one continuous chain from the
Emby host's perspective. Rollback = revert the test tuner entry; production tuner untouched.

---

## 4. PlaybackInfo / PlaySessionId Session Failures; Stale Sessions Blocking Playback

### Error signatures
- `POST /Items/{id}/PlaybackInfo` → HTTP 500 with `LiveTvConflictException` in server log (§1).
- Sessions in `GET /emby/Sessions` that never disappear (probe/sentinel/old client names), including
  "paused" LiveTV sessions on Fire TV that the owner cannot stop from the dashboard — COMMUNITY-REPORTED:
  https://emby.media/community/index.php?/topic/133182-issue-with-some-connections-getting-stuck-and-hitting-stream-limit/
- `DELETE /Videos/ActiveEncodings` is the client-initiated "kill the transcode" call (used by Emby's own web
  client on seek) — COMMUNITY-REPORTED (reverse-engineered, Emby 4.10.x):
  https://github.com/cgillinger/emby-watchparty/blob/main/docs/Emby%20quirks%20we%20learned%20the%20hard%20way.md

### Generating subsystem
`SessionManager` (session lifecycle), `MediaSourceManager` (live stream open/close, consumer counting),
`MediaEncoding` transcode manager (ffmpeg process per PlaySessionId).

### What it means
Every playback creates a session keyed by PlaySessionId; LiveTV additionally opens a tuner stream counted
against the tuner's limit. If the session is never closed (client crash, network drop, probe that never
sends stop), the tuner slot and/or the ffmpeg process leak. Enough leaks → new playback fails for everyone.

### Key reverse-engineered behaviors (Emby 4.10.x) — COMMUNITY-REPORTED
- `AutoOpenLiveStream=true` on the PlaybackInfo POST pre-starts ffmpeg *before* the first segment request
  (saves 300–800 ms); without it ffmpeg starts lazily on first segment fetch.
- `EnableDirectPlay=false` / `EnableDirectStream=false` on PlaybackInfo are **advisory only** — they change
  the recommendation, not the actual HLS pipeline decision, which is made by the DynamicHlsService from the
  URL parameters. Worse: putting `EnableDirectStream=false` on the HLS URL itself yields **404 for every
  segment** (disables the copy path without enabling a transcode path).
- Concurrent operations sharing one PlaySessionId can race two ffmpeg processes writing to the same temp
  directory → corrupted/conflicting segments. Per-user (per-session) PlaySessionIds avoid this.

### Evidence to collect
- `GET /emby/Sessions` — enumerate; flag any session whose client is a probe/sentinel or whose
  `LastActivityDate` is far in the past.
- Dashboard → Active Devices; server log `SessionManager: Playback stopped reported by app ...`.
- `MediaSourceManager: Closing live stream` lines — present = clean release; absent = leaked.

### Confirmation test
Note session count, attempt playback, re-check: if the attempt fails and no *new* session appears (or a new
stale one appears without cleanup), session/tuner accounting is implicated.

### Safe fix + why it works
Stop stale sessions from Dashboard → Active Devices; restart Emby Server if the dashboard cannot kill them
(in-memory counters reset on restart). Why: the tuner-slot and transcode-slot accounting is in-memory, so a
restart is the deterministic reset. Killing stray ffmpeg processes (`taskkill /IM ffmpeg.exe` — verify PIDs
first) frees encoder slots.

### Verification / Rollback
Session list is clean; new playback creates exactly one session and one ffmpeg; stopping playback removes
both. Rollback: none needed (restart is non-destructive to config).

---

## 5. FFmpeg Transcode Startup Failures; ffprobe Stream Probing Failures

### Error signatures (exact text)
- `Error App: Error starting ffmpeg` + `*** Error Report ***` with
  `System.ComponentModel.Win32Exception (0x80004005): Permission denied`
  at `Interop.Sys.ForkAndExecProcess` ← `System.Diagnostics.Process.Start()` ←
  `Emby.Server.Implementations.Diagnostics.CommonProcess.Start()` ←
  `Emby.Server.MediaEncoding.Api.BaseStreamingService.<StartFfMpeg>` — COMMUNITY-REPORTED (Emby forum):
  https://github.com/mediabrowser/emby/issues/3030
  (Newer 4.10.x stack: `Emby.Server.MediaEncoding.Unified.Ffmpeg.FfRunException: Error starting ffmpeg`
  followed by the full ffmpeg command line — COMMUNITY-REPORTED:
  https://github.com/firestaerter3/emby-xtream/issues/25)
- `System.Exception: System.Exception: Error starting ffmpeg` at `BaseStreamingService.StartFfMpeg` ←
  `Hls.DynamicHlsService.GetDynamicSegment` — COMMUNITY-REPORTED:
  https://emby.media/community/index.php?/topic/75063-playback-stops-when-transcoding-is-completebuffer-is-full/&
- `Info App: ProcessRun 'StreamTranscode <id>' Process exited with code 137 - Failed` — exit 137 = process
  was SIGKILLed (OOM-killer on Linux / forced kill). COMMUNITY-REPORTED:
  https://emby.media/community/topic/136801-transcoding-issues/
- `System.Exception: System.Exception: No video encoder found for 'h264'` at `CodecValidation: FindVideoEncoder`
  — ffmpeg binary present but its capability detection returned empty encoder lists — COMMUNITY-REPORTED:
  https://emby.media/community/topic/66365-no-video-encoder-found-for-h264/
- Probe-level: `[mpegts @ ...] Could not detect TS packet size, defaulting to non-FEC/DVHS` then failure to
  read streams; `Invalid NAL unit` lines immediately before `Error starting ffmpeg` (wrong decoder configured
  for the actual bitstream) — COMMUNITY-REPORTED:
  https://github.com/firestaerter3/emby-xtream/releases/tag/v1.4.97-beta

### Generating subsystem
`Emby.Server.MediaEncoding.Api.BaseStreamingService.StartFfMpeg` (4.8–4.9 era) /
`Emby.Server.MediaEncoding.Unified.Ffmpeg` (4.10.x); ffmpeg binary at `<Emby-Server>\system\ffmpeg.exe`.

### What it means
Emby decided to transcode (or direct-stream) but the ffmpeg child process either never launched (permissions,
missing DLL, corrupt binary) or died immediately (bad input, wrong decoder, OOM). The client sees a generic
playback error; the *cause* is only in the server log + ffmpeg-transcode log.

### Known causes
- **CONFIRMED (Emby forum + GitHub issues):** OS-level launch failure — `Permission denied` on fork/exec
  (running from a translocated/blocked path on macOS; noexec mounts or wrong ownership on Linux; on Windows:
  AV blocking or the binary failing to load `MFPlat.DLL` — the Win10 **N-edition** case, fixed by installing
  the Media Feature Pack: https://emby.media/community/index.php?/topic/108610-fix-for-47060-broken-on-win-10-n-edition/)
- **COMMUNITY-REPORTED:** transcoding-temp not writable → `Error starting Ffmpeg` wrapping
  `System.UnauthorizedAccessException: Access to the path '...\transcoding-temp\<guid>' is denied` (§7).
- **COMMUNITY-REPORTED:** ffmpeg killed by OOM (exit 137) — check RAM during transcode.
- **COMMUNITY-REPORTED:** corrupt/wrong ffmpeg binary (TrueNAS case fixed by reinstalling ffmpeg).
- **COMMUNITY-REPORTED:** Emby told the wrong codec (proxy/plugin reporting source codec instead of output
  codec) → `Invalid NAL unit` → ffmpeg exits before first frame.
- **COMMUNITY-REPORTED:** using a non-Emby ffmpeg version with incompatible flags (e.g. `-segment_time_delta`
  range errors on old 4.x).

### Evidence to collect
- Server log `Error starting ffmpeg` + full `*** Error Report ***` (inner exception names the cause:
  `Win32Exception: Permission denied` vs `UnauthorizedAccessException` vs `FfRunException`).
- The matching `ffmpeg-transcode-{guid}.txt` log (§10) — read the *first 30 lines* (command line + input probe)
  and the *last 20 lines* (exit reason).
- Confirm `ffmpeg.exe` runs manually from `<Emby-Server>\system\` (missing-DLL GUI error test).

### Confirmation test
Reproduce the exact ffmpeg command line from the log by hand (copy from the log, run in a shell). If it
fails identically outside Emby, the problem is ffmpeg/input/environment — not Emby.

### Safe fix + why it works
- Permissions on transcoding-temp / programdata (§7). Why: Emby pre-creates the session temp dir before
  spawning ffmpeg; denial aborts the spawn.
- Reinstall/repair the Emby ffmpeg (or repair the Emby Server install) if the binary itself is corrupt.
  Why: `No video encoder found` / empty capability lists mean the binary can't do its job regardless of input.
- Install the Media Feature Pack on Windows N editions (missing `MFPlat.DLL`). Why: Emby's ffmpeg build
  links Media Foundation.
- Fix the *reported* codec at the source (proxy/plugin) if `Invalid NAL unit` precedes the failure.
  Why: Emby configures the decoder from reported metadata before any bytes arrive.

### Verification
New playback creates `ffmpeg-transcode-{guid}.txt`, the log shows `Input #0` with detected streams and
advancing `frame=`/`time=` lines; client receives segments.

### Rollback
ffmpeg binary replacement → keep a copy of the original `ffmpeg.exe`; config changes → config backup.

---

## 6. Hardware Acceleration Init Failures: AMD AMF, Intel Quick Sync / QSV (Windows)

### Error signatures (exact text)
- `[h264_amf @ 000002e8...] CreateComponent(AMFVideoEncoderVCE_AVC) failed with error 1` — AMF context opens,
  encoder component creation fails — COMMUNITY-REPORTED (Jellyfin forum, same ffmpeg/AMF stack as Emby):
  https://forum.jellyfin.org/t-hardware-transcoding-error-amd-gpu
- `[AVHWDeviceContext @ ...] Using device 1002:1638 (AMD Radeon™ Graphics).` — note *which* device was
  picked: on machines with both an AMD APU/iGPU and a discrete card, ffmpeg may bind the wrong one.
- `"Error": { "Number": -3, "Message": "Error initializing an MFX session: MFX_ERR_UNSUPPORTED" }` in the
  hardware detection log — COMMUNITY-REPORTED: https://emby.media/community/index.php?/topic/99667-hardware-acceleration-not-working-on-windows-10/
- Emby log "Processing Plan" table showing `WillDoInHardware: False` with reasons like `Not a hardware
  decoder` / `Not a hardware encoder` / `Software Codec` — COMMUNITY-REPORTED (same thread).

### Generating subsystem
Emby's hardware detection (`hardware detection log` in the logs folder) + ffmpeg `-init_hw_device`
(`amf`, `qsv`, `d3d11va`, `dxva2`) in the transcode command line.

### What it means
Emby probed the GPU at startup and either found no usable encoder or ffmpeg failed to initialize it at
transcode time. Result: silent fallback to software (high CPU) *or* transcode failure if the pipeline was
built assuming hardware.

### Known causes
- **COMMUNITY-REPORTED:** wrong GPU selected — APU/iGPU driver broken or legacy; fix is disable the unused
  iGPU in BIOS or install the correct legacy driver (RX 5600 XT + 5600G case).
- **CONFIRMED (official Emby support article, title/URL):** "Hardware acceleration fails with Remote Desktop
  (RDP) on Windows" — https://support.emby.media/support/solutions/articles/44001894172-hardware-acceleration-fails-with-remote-desktop-rdp-on-windows
  (INFERRED from title: RDP sessions change the Windows graphics device context; GPU-accelerated encode may
  fail or fall back while an RDP session is active. Body not re-verified 2026-10-05 — fetch failed.)
- **COMMUNITY-REPORTED:** driver mismatch — AMD Adrenalin vs the AMF runtime ffmpeg expects.
- **INFERRED:** Premiere license lapsed → hardware transcoding options silently unavailable (Emby requires
  Premiere for HW transcoding).

### Evidence to collect
- The hardware detection log (latest in logs folder) — check which devices/encoders were found.
- `ffmpeg-transcode-{guid}.txt` top lines: the `-init_hw_device` argument and any `[AVHWDeviceContext]` /
  `[h264_amf]` / `[h264_qsv]` errors.
- Emby Dashboard → Transcoding settings vs the *known-good* configuration (screenshot or export).

### Confirmation test
Force a transcode (e.g. lower the client's max bitrate) and watch the ffmpeg log: does it contain
`-init_hw_device` and succeed, fall back to `libx264`, or die at `CreateComponent`?

### Safe fix + why it works
- Select the correct GPU / disable the unused iGPU in BIOS (wrong-device case). Why: AMF/QSV bind the first
  enumerated device; a broken APU driver poisons init.
- Update GPU drivers from the vendor (not Windows Update). Why: AMF is a user-mode runtime shipped with the
  driver.
- Avoid active RDP sessions during HW-transcode diagnosis (per the official article above).
- As a *diagnostic* (not permanent) step: switch Transcoding → Hardware acceleration to "None" and retest —
  if playback works in software, the failure is isolated to the HW init path.

### Verification / Rollback
ffmpeg log shows the hardware encoder in use (`h264_amf`, `h264_qsv`) with advancing frames and low CPU.
Rollback = restore the previous Transcoding settings (screenshot/export beforehand).

---

## 7. transcoding-temp Problems: Permissions, Disk Space, Stale Files, Path Issues

### Error signatures (exact text)
- `Error FfmpegManager: ProcessRun '<guid>': Error starting Ffmpeg. WorkingFolder: C:\Users\<user>\AppData\Roaming\Emby-Server\system`
  with inner `System.UnauthorizedAccessException: System.UnauthorizedAccessException: Access to the path
  'C:\Users\<user>\AppData\Roaming\Emby-Server\programdata\transcoding-temp\<guid>' is denied.`
  — COMMUNITY-REPORTED (Emby forum, 4.8.10.0 on Windows): https://emby.media/community/topic/134831-livetv-translation-on-demand-subtitles-plugin-using-whisper/?tab=comments
- `[ segment @ ... ] Opening '/.../transcoding-temp/<guid>.m3u8.tmp' for writing` in a *healthy* log — the
  absence of segment-writing lines in a transcode log means ffmpeg died before writing.

### Generating subsystem
`Emby.Server.MediaEncoding` (creates `<guid>` subfolder per session under transcoding-temp, writes `.m3u8`
playlist + `.ts` segments there); default path `C:\Users\<user>\AppData\Roaming\Emby-Server\programdata\transcoding-temp`
on Windows (configurable in Dashboard → Transcoding).

### What it means
ffmpeg cannot write its output. Emby pre-creates the session folder; if the service account lacks write
access (or the disk is full), the transcode never starts and every transcode-dependent playback fails —
often all at once, which mimics a "server down" symptom.

### Known causes
- **CONFIRMED (log trace):** ACL/ownership on transcoding-temp denies the Emby process write access
  (`UnauthorizedAccessException`).
- **COMMUNITY-REPORTED:** disk full — one user found ~16 GB of orphaned transcode files filling a 60 GB OS
  SSD; Emby had "offloaded" the temp location but stale files accumulated anyway.
- **INFERRED:** stale `<guid>` subfolders from crashed sessions accumulate; Emby normally cleans them on
  session close, but leaked sessions (§4) leave them behind.
- **INFERRED:** temp path pointing at a network/cloud drive (or a drive that disconnects, e.g. T:) —
  latency/disconnects break segment writes mid-stream.

### Evidence to collect
- Free space on the temp drive; size and age of `transcoding-temp\*` subfolders (stale = old timestamps,
  no matching live session).
- Effective permissions: does the Emby process identity have Modify on transcoding-temp?
- Dashboard → Transcoding → Transcoding temporary path value vs the actual folder.

### Confirmation test
Manually create + delete a file in transcoding-temp *as the Emby service account* (or check with
`icacls`). If that fails, permissions are confirmed before touching anything else.

### Safe fix + why it works
1. Fix ACLs so the Emby identity has Modify on transcoding-temp (inheritance on). Why: removes the
   `UnauthorizedAccessException` at the exact failing call.
2. Delete only *stale* session subfolders (no matching entry in `/emby/Sessions`, old mtime) — never the
   whole folder while the server runs. Why: frees disk without disturbing active transcodes.
3. If disk is chronically tight, move the temp path to a larger local drive (Dashboard → Transcoding).
   Why: transcode output is write-heavy and temporary — it belongs on fast local storage, never on a
   cloud-mounted drive.

### Verification
New transcode creates its `<guid>` folder and writes segments; `ffmpeg-transcode` log shows advancing output.

### Rollback
Record the old temp path before changing it; restore if playback worsens.

---

## 8. HLS (.m3u8) Playlist / Manifest Errors

### Error signatures / patterns
- Client stalls or errors while the server log shows the master playlist served fine — the *media* playlist
  or segments then 404/500. Reverse-engineered Emby 4.10.x behavior: putting `EnableDirectStream=false` on
  the HLS URL itself makes Emby return **404 for every segment** — COMMUNITY-REPORTED:
  https://github.com/cgillinger/emby-watchparty/blob/main/docs/Emby%20quirks%20we%20learned%20the%20hard%20way.md
- `#EXTINF` durations that don't match actual segment content (stream-copy of VBR sources with wide
  keyframe intervals) → players mis-seek, stall, or restart — COMMUNITY-REPORTED (same doc).
- `Error processing request` for `/emby/videos/{id}/live.m3u8?...&PlaySessionId=...` when ffmpeg can't serve
  the segment (see §5) — COMMUNITY-REPORTED: https://forum.openmediavault.org/index.php?thread/10769-emby-can-t-play-anything-error-starting-ffmpeg-access-denied/
- Mid-stream HLS failures in newer Jellyfin expose `X-Playback-Error-Code` response header on failed
  manifest/segment responses (Jellyfin-side evolution; Emby 4.10.x behavior unverified — INFERRED as a
  diagnostic avenue, not a confirmed Emby feature).

### Generating subsystem
`Emby.Server.MediaEncoding.Api.Hls.DynamicHlsService` (master/media playlists, `GetDynamicSegment`).

### What it means
The playlist layer is healthy only if ffmpeg is producing segments. Most "playlist errors" are really
"ffmpeg isn't producing segments" (§5) or "the session the playlist belongs to is gone" (§4).

### Known causes
- ffmpeg dead/stalled → segments never written → 404/500 on segment fetch.
- Session torn down (transcode killed, tuner closed) while the client still holds the playlist URL.
- Stream-copy path with mismatched keyframes → player-side failure despite 200s everywhere.

### Evidence to collect
- Fetch `master.m3u8`, then the media playlist, then segment 0 manually with the same query string —
  record the HTTP status of *each* hop (this is exactly the Sentinel's synthetic chain).
- In the ffmpeg log: `Opening '....m3u8.tmp' for writing` and `SegmentComplete` lines = healthy production.

### Confirmation test
If master.m3u8 = 200 but segment fetch = 404/500, the session/ffmpeg behind it is dead — check
`/emby/Sessions` and the ffmpeg log before blaming the playlist format.

### Safe fix + why it works
Restart the playback session (new PlaySessionId → new ffmpeg → new temp dir). For chronic stream-copy
seek/stall issues on VBR sources, `EnableAutoStreamCopy=false` on the HLS URL forces a real re-encode with
uniform keyframes — COMMUNITY-REPORTED fix with measured rationale (uniform segments, reliable seeking).

### Verification / Rollback
All three hops return 200 and segment bytes advance across successive fetches. Rollback: revert URL flags.

---

## 9. Client-Visible Errors: "Playback failure / server error" and "Playback error"

### What they mean (INFERRED from subsystem behavior — Emby does not publish a client-message→cause table)
These are *generic* client dialogs. The client shows them when the server-side chain fails at any point
*after* the client asked for playback:
- PlaybackInfo returned 500 (tuner conflict §1, ffmpeg start failure §5, unhandled exception).
- master.m3u8/media playlist/segment requests returned 4xx/5xx (§8).
- The stream stalled (no new segments) and the client's timeout fired.
- Session/auth rejected mid-play (api_key invalid, user permissions changed).

"server error" wording correlates with HTTP 5xx from Emby; plain "Playback error" is the fallback for
timeouts, 4xx, and player-side decode failures. Treat both as "go read the server log at the exact
timestamp" — the client message alone never identifies the layer.

### Server-side conditions that produce them (mapped)
| Client sees | Check first |
|---|---|
| "Playback failure / server error" on Live TV, all channels | §1 tuner limit, §5 ffmpeg start, §7 temp perms |
| "Playback error" on one channel only | §3 tuner URL for that channel, source availability |
| Error immediately on play | PlaybackInfo 500 → §1/§5 |
| Error after a few seconds of black screen | ffmpeg started but died → §5/§6, read ffmpeg log tail |
| Error only on remote/Tailscale clients | §3 (302 minted for wrong IP), transcode bitrate vs uplink |

### Evidence to collect
- Exact client message + exact timestamp + which client (web/Fire TV/etc.).
- Server log ±60 s around the timestamp; the `POST PlaybackInfo` and any `ErrorReport`.
- The ffmpeg-transcode log whose start time matches (filenames contain the session guid; correlate via the
  PlaySessionId in the request URLs).

---

## 10. Emby Server Log + ffmpeg Log Correlation: Which Lines Identify Which Subsystem

Log locations (Windows): `C:\Users\<user>\AppData\Roaming\Emby-Server\logs\` (+ `programdata\logs` on some installs).
Key files: `embyserver.txt` (current), `embyserver-<n>.txt` (rotated), `ffmpeg-transcode-<guid>.txt` (per transcode),
`ffmpeg-directstream-<guid>.txt`, hardware detection log.

| Log line pattern | Subsystem | Meaning |
|---|---|---|
| `Emby.Server.Implementations.LiveTv.TunerHosts.M3UTunerHost: Error opening tuner` + `LiveTvConflictException` | LiveTV tuner | Tuner slot limit hit or tuner open threw (§1) |
| `LiveTvManager: Opening channel stream from Emby, external channel Id:` | LiveTV manager | A tune was attempted — start of the chain |
| `M3UTunerHost: Streaming Channel m3u_...` | LiveTV tuner | Tuner accepted the channel |
| `M3UTunerHost: Closing "LiveStream"` / `MediaSourceManager: Closing live stream "<id>"` | LiveTV/session | Clean teardown — healthy |
| `MediaSourceManager: Live stream "<id>" consumer count is now 0` | Session mgmt | Last consumer released; tuner slot freed |
| `Jellyfin.Api.Helpers.MediaInfoHelper: User policy for "<user>". EnablePlaybackRemuxing...` | PlaybackInfo | Playback request received; policy shown |
| `StreamBuilder.BuildVideoItem(...) => ( PlayMethod=Transcode, TranscodeReason=... )` | Playback decision | Why Emby chose transcode/direct play/stream |
| `App: ProcessRun 'StreamTranscode <id>'` | Transcode mgr | ffmpeg lifecycle (start/stop/exit code) |
| `Process exited with code 137 - Failed` | Transcode mgr | ffmpeg was killed (OOM/forced) |
| `Error App: Error starting ffmpeg` + `*** Error Report ***` | Transcode mgr | ffmpeg never launched — read inner exception |
| `FfmpegManager: ProcessRun ... Error starting Ffmpeg` + `UnauthorizedAccessException ... transcoding-temp` | Transcode mgr | Temp-dir permissions (§7) |
| `AppendExtraLogData - Read graph file: ...ffmpeg-transcode-<guid>_1graph.txt` / `Unable read graph output file` | Transcode mgr | Post-mortem attachment; the "unable" warning is benign |
| `Server: http/1.1 Response 500 ... Time: 25457ms` | HTTP server | Request failed after ~25 s (typical transcode-timeout shape) |
| `SessionManager: Playback stopped reported by app "<client>"` | Session mgr | Client-initiated stop — healthy |
| `CodecValidation: FindVideoEncoder - Media: h264, UseHardwareCodecs: True` → `No video encoder found for 'h264'` | Codec validation | ffmpeg capability detection broken |
| `[h264_amf @ ...] CreateComponent(AMFVideoEncoderVCE_AVC) failed` | ffmpeg/HW | AMF init failed — wrong GPU or driver (§6) |
| `Error initializing an MFX session: MFX_ERR_UNSUPPORTED` (hw detection log) | HW detection | QSV/MFX unavailable on this device |
| `>>> Processing Plan` / `WillDoInHardware` table | Transcode planner | Per-stream HW vs software decision + reason |

**Correlation procedure:** take the client's failure timestamp → find the `PlaybackInfo` POST in `embyserver.txt`
→ follow the PlaySessionId/guid into the matching `ffmpeg-transcode-<guid>.txt` → read the ffmpeg log's first
30 lines (command + input probe) and last 20 lines (exit cause). If no ffmpeg log exists for a Transcode
decision, the failure is *before* ffmpeg (§1/§4/§7).

---

## Diagnostic Decision Tree: Multi-Channel Live TV Playback Failure

Shared-dependency-first ordering. Stop at the first layer that fails; do not skip ahead.

```
ALL channels fail at once?
├─ YES → shared dependency. Order:
│   1. EMBY CORE: Is Emby Server itself up? GET /emby/System/Info/Public → 200?
│      NO → Emby process down/wedged → check service, restart (capture logs first).
│   2. LIVE TV / TUNER: GET /emby/Sessions → stale sessions holding tuner slots?
│      Server log: M3UTunerHost "Error opening tuner" / LiveTvConflictException?
│      YES → clear stale sessions (§4); if persistent, delete+re-add tuner (§1).
│   3. RELAY / NETWORK: tuner URL from Emby host: 302? Location reachable? GET final URL → 200?
│      NO → relay down or 302 target broken (§3).
│   4. TRANSCODE: does PlaybackInfo choose Transcode? Does ffmpeg-transcode-<guid>.txt exist?
│      NO log → §5 "Error starting ffmpeg" / §7 temp perms.
│      Log exists but dies → read tail: AMF/QSV init (§6), OOM 137, Invalid NAL unit (wrong codec §5).
│   5. SOURCE: only if 1–4 pass — is the underlying media item itself playable?
│      (Direct-probe the item Emby points at, e.g. ffprobe the HLS URL.)
│   6. CLIENT: only if server chain is fully healthy — client-specific (cache, app version, network path).
│      Note §3: remote/VPN clients vs same-host paths behave differently with 302s.
└─ NO (one channel fails) → channel-specific: its tuner URL, its source item, its mapping.
```

**The "synthetic passes, real playback fails" discrepancy** (seen 2026-10-05): synthetic checks that hit
the relay directly bypass Emby's LiveTV engine, tuner-slot accounting, PlaySessionId lifecycle, and the
302-back-into-Emby hop. When synthetics pass but Emby clients fail, suspect layers 2–4 above *first* —
especially stale sessions consuming tuner slots (§1/§4) and the self-referential 302 hop (§3).

---

## Sources

- Emby community — tuner limit / no compatible streams: https://emby.media/community/topic/42954-playback-error-no-compatible-streams-are-currently-available/
- Emby community — stuck LiveTV sessions hitting stream limit: https://emby.media/community/index.php?/topic/133182-issue-with-some-connections-getting-stuck-and-hitting-stream-limit/
- Jellyfin issue #4817 — M3UTunerHost `LiveTvConflictException` trace: https://github.com/jellyfin/jellyfin/issues/4817
- fbtv EMBY_SETUP.md — 302 redirect topology guidance: https://github.com/cbodden/fbtv/blob/HEAD/docs/EMBY_SETUP.md
- emby-watchparty "Emby quirks" (Emby 4.10.x reverse-engineered HLS behavior): https://github.com/cgillinger/emby-watchparty/blob/main/docs/Emby%20quirks%20we%20learned%20the%20hard%20way.md
- Emby community — transcoding-temp UnauthorizedAccessException: https://emby.media/community/topic/134831-livetv-translation-on-demand-subtitles-plugin-using-whisper/?tab=comments
- Emby community — transcode issues / exit 137: https://emby.media/community/topic/136801-transcoding-issues/
- Emby community — Win10 N edition MFPlat.DLL: https://emby.media/community/index.php?/topic/108610-fix-for-47060-broken-on-win-10-n-edition/
- Emby community — playback stops / ffmpeg error report shape: https://emby.media/community/index.php?/topic/75063-playback-stops-when-transcoding-is-completebuffer-is-full/&
- Jellyfin forum — AMD AMF CreateComponent failure: https://forum.jellyfin.org/t-hardware-transcoding-error-amd-gpu
- Emby community — HW accel / MFX_ERR_UNSUPPORTED: https://emby.media/community/index.php?/topic/99667-hardware-acceleration-not-working-on-windows-10/
- Official Emby support — HW accel fails with RDP on Windows (title/URL; body not re-verified): https://support.emby.media/support/solutions/articles/44001894172-hardware-acceleration-fails-with-remote-desktop-rdp-on-windows
- emby-xtream issue #25 — 4.10.x `FfRunException: Error starting ffmpeg` shape: https://github.com/firestaerter3/emby-xtream/issues/25
- emby-xtream release notes — wrong reported codec → Invalid NAL unit: https://github.com/firestaerter3/emby-xtream/releases/tag/v1.4.97-beta
- Emby community — no video encoder found: https://emby.media/community/topic/66365-no-video-encoder-found-for-h264/
