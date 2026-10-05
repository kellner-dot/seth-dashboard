# Fire TV Stick 4K Select — Playback Tuning Guide

Target: Fire TV Stick 4K Select (2025), AFTCA002, Vega OS. 1 GB RAM.
Goal: best HLS stream quality without stutters on this stick.
Researched 2026-10-05. Confidence: [O] official · [C] community-verified · [P] plausible.

---

## 1. Hardware limits (MediaTek MT8698 MCM)

[O] https://www.cnx-software.com/2025/10/03/linux-based-vega-os-replaces-android-based-fire-os-in-amazon-fire-tv-stick-4k-select/ (2025-10-03)
[O] https://developer.amazon.com/docs/fire-tv/device-specifications-fire-tv-streaming-media-player.html

- CPU: 4× Cortex-A55 @ 1.7 GHz, **32-bit ABI** (armv7 builds only)
- GPU: Mali G310v2 @ 500 MHz
- RAM: **1 GB LPDDR4** — the binding constraint on everything below
- Storage: 8 GB eMMC · Wi-Fi 5 (2×2 MIMO) · BT 5.0

### VPU hardware decoder ceilings [O]

| Codec | Max | Bitrate cap | HDR |
|---|---|---|---|
| AV1 | 4K@60 | 100 Mbps | HDR10/HDR10+/HLG, 8+10-bit |
| HEVC H.265 | 4K@60 | 35 Mbps | HDR10/HDR10+/HLG, 8+10-bit |
| AVC H.264 | 4K@60 (also 1080p@60 / 720p@60) | 30 Mbps | — |
| VP9 | 4K@60 | 30 Mbps | HDR10/HLG, 8+10-bit |
| VP8 | 1080p30 | — | — |
| MPEG-2 | 1080p60 | — | — |
| MPEG-4 | 1080p30 | — | — |

### What is NOT there
- **No Dolby Vision** [O] (aftvnews, Amazon specs) — don't author for it.
- **No Dolby audio decoding at all — passthrough only** [O] (Amazon specs list
  only "HDMI Audio pass-through for Dolby Digital/Digital+/Atmos/DTS…").
  [C] A Fire TV Stick measured with w3cmedia `decodingInfo` reports **no Dolby
  support** (jonathanlemes/jellyfin-vega-os, `src/api/deviceProfile.ts`:
  "claiming it caused the server to hand back a Dolby Digital Plus file for
  direct play that the device then [couldn't play]"). **Request AAC/MP3 stereo
  from the server; never direct-play AC3/E-AC3.**
- Decodable audio: AAC LC/HE-AAC/HE-AACv2/xHE-AAC (≤8ch, ≤48 kHz), MP3
  (≤48 kHz), FLAC (≤48 kHz stereo), Vorbis, Opus (≤8ch), PCM/WAVE [O].

### Practical consequences
- The stick *can* decode 4K, but on 1 GB RAM the app should **cap ABR at
  1080p**. [C] astra-tv clamps `abrMaxWidth/Height` to **1919×1079**
  (`src/w3cmedia/shakaplayer/ShakaPlayer.ts:615`).
- [C] jellyfin-vega-os requests **≤20 Mbps** in its Jellyfin device profile
  and targets 1080p.

---

## 2. HLS recipe (server/relay side)

For the KaviTV relay (or any HLS origin feeding this stick):

- **Container: fMP4, not MPEG-TS** for the MSE path. [C] "Jellyfin otherwise
  emits MPEG-TS segments, which cannot be appended to a `SourceBuffer`. Asking
  explicitly [`SegmentContainer=mp4`] is what makes the manifest carry an
  `EXT-X-MAP` initialisation segment and `.mp4` fragments."
  (jellyfin-vega-os README). Use TS only for the WebView `<video>` path.
- **Segment duration: 4 s for live TV, 6 s for VOD.** 4 s = faster tune-in
  and quicker stall recovery on live channels; 6 s = less playlist churn.
  **Keyframe interval must equal the segment duration** or segments won't
  start on clean keyframes and the player stutters [C]
  (devdasher/hls-converter-cli HLS tuning table, 2026-10).
- **ABR ladder (1080p target):** 1080p@8 Mbps · 720p@4 Mbps · 480p@1.5 Mbps ·
  270p@0.8 Mbps. Cap top rendition at 1080p on this device.
- **Audio:** AAC-LC stereo 128–192 kbps. Never AC3/E-AC3 (see §1).
- **Subtitles:** external SRT/WebVTT. [C] Server burn-in permanently latches
  forced video transcode in some clients (astra-tv review §"subtitle burn-in
  latches"); image-based subs force video conversion.

---

## 3. Buffer budget — the 50 MB rule

[C] AmbientFlare/astra-tv, `src/services/playbackHealth/bufferBudget.ts`
(2026-09). This is the most important number in this document:

> Shaka's buffer goals are seconds, which makes them blind to bitrate: a 10 s
> goal is 2.9 MB of a 2.3 Mbps episode and **31 MB of a 25 Mbps 4K movie**.
> On a 1 GB device that difference decides whether the media buffer is
> comfortable or the largest allocation in the process.

- **MEDIA_BUFFER_BUDGET_BYTES = 50 MB** fixed for the whole media buffer.
- Split: **60% forward / 25% behind**; rebuffer = 40% of forward goal.
- `bufferingGoal = clamp(30 MB / bytesPerSec, 8, 20)` seconds
- `rebufferingGoal = clamp(bufferingGoal × 0.4, 4, 7)` seconds
- `bufferBehind = clamp(12.5 MB / bytesPerSec, 8, 15)` seconds
- Unknown bitrate → conservative default **10 / 4 / 10**.
- **Never leave Shaka's 30 s `bufferBehind` default**: at 25 Mbps it retains
  ~90 MB behind the playhead and "its eviction pass is the leading suspect
  for the full-buffer collapses" seen on this class of device.

### Worked example — KaviTV (H.264 1080p @ 8 Mbps ≈ 1 MB/s)
- bufferingGoal = 30 MB ÷ 1 MB/s = 30 → **clamped to 20 s**
- rebufferingGoal = 20 × 0.4 = 8 → **clamped to 7 s**
- bufferBehind = 12.5 MB ÷ 1 MB/s = **12.5 s**
- Total ≈ 39.5 s ≈ **~40 MB** — comfortable inside the budget.

### hls.js equivalents (if using the WebView `<video>` + hls.js path)
Defaults are desktop-sized; bring them down [O]
(github.com/video-dev/hls.js/blob/master/docs/API.md):
- `maxBufferLength: 30` → **20** (seconds)
- `maxBufferSize: 60 MB` → **40–50 MB**
- `backBufferLength: Infinity` → **60** (seconds)
- `maxBufferHole: 0.1`, `nudgeMaxRetry: 3` — keep.

### jellyfin-vega-os hand-rolled pump [C]
(`src/player/hlsVideoPlayer.ts` — the other proven Vega MSE implementation)
- **BUFFER_AHEAD_SECONDS = 30**, **BUFFER_BEHIND_SECONDS = 60**,
  pump every **250 ms**. Behind-data evicted lazily via `SourceBuffer.remove`.
- "A two-hour film would otherwise buffer far past what the device can hold,
  and `appendBuffer` starts failing with a quota error."

---

## 4. w3cmedia MSE gotchas (Vega-specific)

From jonathanlemes/jellyfin-vega-os [C] and the astra-tv 2026-09-04
playback-architecture review [C]
(github.com/ambientflare/astra-tv/blob/HEAD/docs/playback-architecture-review-2026-09-04.md):

1. **`set_src_uri` with a raw URL is rejected on Vega OS 1.2** — before any
   decoding is attempted. You MUST fetch manifest → parse → fetch segments
   as ArrayBuffers → `sourceBuffer.appendBuffer()`. No exceptions.
2. **Serialize appends.** MSE rejects `appendBuffer`/`remove` while a previous
   op is updating. Queue everything behind `updateend`; never let evictions
   jump ahead of appends (appendQueue.ts pattern).
3. **NEVER swallow `appendBuffer` exceptions.** [C] astra-tv's wrapper caught
   native exceptions and converted them to a void rejection — including
   `QuotaExceededError`. Shaka 4.8.5's real handler catches that exception,
   rejects the queued op and advances; suppressing it leaves Shaka waiting
   for an `updateend` that never comes → **unexplained permanent buffer
   stall**. Let the exception propagate.
4. **Use `AppendMode.segments`** for fMP4: Jellyfin writes absolute decode
   times (segment 500 of a 6 s playlist ≈ 3000 s), so fragments land at true
   positions with no offset math.
5. **Vega demuxer DTS quirk:** [C] "Vega's MP4 demuxer can pass overlapping
   decode timestamps from adjacent fMP4 fragments through to the hardware
   decoder." Fix: **sequence mode** (places each fragment directly after the
   previous, avoiding repeated/backward DTS at boundaries). In segments mode,
   set **ignoreManifestTimestampsInSegmentsMode** — Jellyfin's fMP4 media
   timestamps are more trustworthy than Shaka's duration-derived correction
   on Vega.
6. **Never tear down the buffer on seek.** `SourceBuffer` handles disjoint
   ranges; removing the range under the playhead strands the decoder.
   Pattern: assign `currentTime` → repoint fetch loop at the covering
   segment → epoch-counter invalidates in-flight fetches → element resumes
   itself. Fresh `MediaSource` per load (reusing one keeps the old timeline).
7. **Probe with `decodingInfo` at startup** for concrete configs
   (resolution+bitrate+framerate), not codecs in the abstract. Fall back to
   a conservative profile (H.264/AAC) if the platform won't answer.
8. **Watchdog discipline** (astra-tv review): distinguish starvation,
   timestamp gaps, pause, seek, and decoder failure — don't treat them as
   one "buffering" state. A playback-session controller should own one
   ordered transition queue and a cancellation token; native release must
   never wait on server telemetry.

---

## 5. Thermal notes

- Signs of thermal throttling on sticks: UI lag after ~1 hr, Wi-Fi drops
  (heat interferes with the Wi-Fi chip), visual artifacts/freezing on
  high-bitrate 4K, unexpected reboots [C]
  (medium.com/@info.ultracastiptv, 2026-01-02; XDA forums).
- **Use the HDMI extender** in the box — the gap between the hot TV panel
  and the stick is the single biggest cooling factor [C].
- No public MT8698 thermal trip points found [P] — treat sustained 4K +
  software decode as the danger zone; hardware decode (VPU) runs far
  cooler than CPU decode, another reason to keep everything on the
  hardware path (fMP4 + supported codecs, no transcoding on-device).
- Vega exposes `memoryWarning` via the app-state manager — free caches
  immediately when it fires (genius guide §9).

---

## 6. Validated baselines (what's proven to work)

- [C] astra-tv: **HEVC HLS, MPEG-TS, segments mode** — one-hour sync and
  seek/resume acceptance on hardware. H.264/fMP4 from zero in segments
  mode; fMP4 resumed above zero in **sequence mode** (1.2.1 timestamp fix).
- [C] jellyfin-vega-os: fMP4 HLS via hand-rolled MSE pump, 30 s ahead /
  60 s behind, tested on 32-bit Vega OS 1.2 stick.
- [C] looizao/jellyfin-vega-tailnet: H.264/AAC playback verified through
  embedded tailnet in Chromium; recommends starting tests at **1080p or
  lower H.264 + AAC**, lowering quality on relayed/slow links.

---

## Top 10 findings (one-liners)

1. The MT8698 VPU decodes AV1/HEVC/VP9 at 4K@60 (35–100 Mbps) and H.264 at 4K@60/30 Mbps — but there is **no Dolby Vision and no Dolby audio decoding at all** (passthrough only); `decodingInfo` on-device confirms zero Dolby support.
2. **50 MB is the media-buffer budget** on this 1 GB stick (astra-tv): 60% forward / 25% behind, computed from bitrate — never use Shaka's 30 s `bufferBehind` default (~90 MB at 25 Mbps, suspected in full-buffer collapses).
3. For KaviTV's 8 Mbps H.264: **20 s forward / 7 s rebuffer / 12.5 s behind ≈ 40 MB** — the concrete target.
4. Cap ABR at **1080p** (1919×1079) even though the chip does 4K — a memory decision, not a decode decision.
5. Vega 1.2 **rejects raw media URLs** — the only path is fetch-manifest → fetch segments → `appendBuffer`; use **fMP4** (MPEG-TS can't go into a SourceBuffer).
6. **Never swallow `appendBuffer` exceptions**: hiding `QuotaExceededError` from Shaka causes permanent unexplained stalls — the #1 Vega playback bug found in the wild.
7. **Sequence mode** fixes Vega's demuxer passing overlapping DTS from adjacent fMP4 fragments to the hardware decoder; in segments mode, trust Jellyfin's media timestamps over Shaka's correction.
8. HLS recipe: **4 s segments (live) / 6 s (VOD), keyframe interval = segment duration**, AAC-LC stereo, external SRT subs — and never tear down the buffer on seek.
9. Heat is a playback bug: throttling + Wi-Fi interference cause buffering after ~1 hr — **use the HDMI extender**, keep decode on the VPU (hardware path runs cooler).
10. Request **AAC stereo from the server and ≤20 Mbps**; never direct-play AC3/E-AC3 — the server will happily hand you a file the stick can't decode.
