# ffmpeg HLS Relay Tuning — KaviTV (2026-10-05)

Savant research for the KaviTV relay (port 8100, SETHS-PC): stable
long-running HLS from sometimes-flaky Emby/cloud inputs to a 1 GB
Fire TV Stick 4K Select. The relay already ships an H.264 timestamp fix
via `-output_ts_offset` — this doc explains why that's right, what the
cleaner alternatives are, and the full hardened command set.

## 0. The closest real-world analog

`lolimmlost/jellyfin-virtual-tv` (active, updated ~2026-09-25) runs the
*same architecture as KaviTV*: Jellyfin transcoding endpoint as input →
ffmpeg → scheduled channels. Its command is the reference design:

```bash
ffmpeg -fflags +igndts+genpts+discardcorrupt \
  -f concat -safe 0 -protocol_whitelist file,http,https,tcp,tls \
  -probesize 1048576 -analyzeduration 2000000 \
  -i concat.txt \
  -map 0:v:0 -map 0:a:0 \
  -c:v libx264 -preset veryfast -tune zerolatency \
  -profile:v high -level 4.1 -pix_fmt yuv420p \
  -g 60 -keyint_min 60 -sc_threshold 0 \
  -b:v 6000k -maxrate 8000k -bufsize 12000k \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -t <batchDurationSec> \
  -output_ts_offset <ptsOffsetSec> \
  -f mpegts -mpegts_flags resend_headers -flush_packets 1 \
  pipe:1
```

Its HLS variant swaps the tail for:
`-f hls -hls_time 6 -hls_list_size 0 -hls_flags append_list+omit_endlist+program_date_time`
[Source: https://github.com/lolimmlost/jellyfin-virtual-tv/blob/HEAD/CONTEXT.md — C, 2026-09]

## 1. Recommended command templates

### Template A — remux path (input is already H.264 + AAC)

Use when the Emby stream is H.264 video + AAC/MP3 audio. Zero quality
loss, near-zero CPU, near-instant start. This should be the DEFAULT.

```bash
ffmpeg -hide_banner -loglevel warning -nostdin \
  -fflags +genpts+discardcorrupt \
  -err_detect aggressive \
  -reconnect 1 -reconnect_at_eof 1 -reconnect_streamed 1 \
  -reconnect_delay_max 15 \
  -timeout 15000000 \
  -i "<emby_stream_url>" \
  -map 0:v:0 -map 0:a:0 \
  -c:v copy -bsf:v h264_mp4toannexb \
  -c:a aac -b:a 128k -ar 48000 -ac 2 \
  -output_ts_offset <offset_sec> \
  -f hls \
  -hls_time 4 \
  -hls_list_size 12 \
  -hls_flags independent_segments+delete_segments+omit_endlist+temp_file \
  -hls_delete_threshold 2 \
  -hls_segment_type mpegts \
  -hls_segment_filename "<dir>/seg_%05d.ts" \
  "<dir>/playlist.m3u8"
```

Notes:
- `-bsf:v h264_mp4toannexb` is MANDATORY on H.264-copy → MPEG-TS paths.
  Without it the TS segments carry MP4-style NALUs and players choke.
  [Source: roto31/exstreamtv ffmpeg constants — C, 2026-03]
- Audio is re-encoded to AAC even on the remux path: cheap, and it
  sidesteps the whole class of "decoded PTS gaps at segment boundaries"
  audio glitches seen with copied AAC/ADTS. [Source:
  dispatcharr/dispatcharr#1422 — C, 2026-07]
- `temp_file`: a segment is only complete when the `.tmp` suffix is
  gone — readers key off the rename, never serve a partial segment.
  [Source: szebest/taitube-platform SKILL.md — C, 2026-09]

### Template B — transcode path (input is NOT H.264/AAC)

Use when the source is HEVC, MPEG-2, VP9, or the audio isn't AAC/MP3.

```bash
ffmpeg -hide_banner -loglevel warning -nostdin \
  -fflags +genpts+discardcorrupt \
  -err_detect aggressive \
  -reconnect 1 -reconnect_at_eof 1 -reconnect_streamed 1 \
  -reconnect_delay_max 15 \
  -timeout 15000000 \
  -i "<emby_stream_url>" \
  -map 0:v:0 -map 0:a:0 \
  -c:v libx264 -preset veryfast -tune zerolatency \
  -profile:v high -level 4.1 -pix_fmt yuv420p \
  -g 120 -keyint_min 120 -sc_threshold 0 \
  -b:v 6000k -maxrate 8000k -bufsize 12000k \
  -c:a aac -b:a 128k -ar 48000 -ac 2 \
  -output_ts_offset <offset_sec> \
  -f hls \
  -hls_time 4 \
  -hls_list_size 12 \
  -hls_flags independent_segments+delete_segments+omit_endlist+temp_file \
  -hls_delete_threshold 2 \
  -hls_segment_type mpegts \
  -hls_segment_filename "<dir>/seg_%05d.ts" \
  "<dir>/playlist.m3u8"
```

- `-g 120` = 2 s GOP at 30 fps… wait, no: for 4 s segments at 30 fps
  the GOP must DIVIDE the segment duration. Use `-g 120` (4 s @ 30fps)
  for 4 s segments, or `-g 60` for 2 s segments. The rule: **GOP =
  fps × hls_time**, and `-keyint_min` = same, `-sc_threshold 0` kills
  scene-cut keyframes that would break alignment. [Source:
  rendi-api/ffmpeg-llm streaming.md — C, 2026-07]
- For belt-and-braces keyframe forcing (VFR or odd sources), add:
  `-force_key_frames "expr:gte(t,n_forced*4)"` (4 = hls_time).
  [Source: szebest/taitube-platform — C, 2026-09]
- `-tune zerolatency` disables lookahead/RC-delay — correct for live.
  `-preset veryfast` is the live sweet spot (faster burns CPU for
  little gain; slower adds latency).

### Which template? The ladder decision

```
ffprobe the Emby stream
  ├─ video = h264 AND audio ∈ {aac, mp3}  →  Template A (remux)
  ├─ video = h264, audio = ac3/eac3/dts   →  Template A, but -c:a aac
  │   (the stick can't decode AC3 — never direct-play it)
  └─ anything else                        →  Template B (transcode)
```

Probe once per channel tune, cache the decision for the session. The
relay already knows the Emby item — one `ffprobe -v error -show_streams`
at tune time is cheap.

## 2. Timestamp handling — why `-output_ts_offset` is right

**The problem.** Every time ffmpeg (re)connects to the input — channel
tune, Emby hiccup, cloud stall — the input PTS restarts at or near 0.
Without correction the player sees the timeline jump back to t=0:
freeze, "Signal is aborted", or a full rebuffer. [Source:
m0ntana/ffmpeg_dynamic_hls README — C]

**What `-output_ts_offset` does.** It adds a constant offset (seconds)
to every output timestamp, so the HLS timeline keeps climbing
monotonically across restarts instead of resetting. The relay computes
`<offset_sec>` = the last emitted PTS when restarting a channel's
ffmpeg, and the new process continues the timeline. No bogus
`#EXT-X-DISCONTINUITY` needed. [Source: gtsteffaniak/go-ffmpeg
docs/hls.md — C, 2026-09: "output_ts_offset for continuous timeline
without bogus #EXT-X-DISCONTINUITY"]

**Cleaner alternatives — and why they're worse here:**
- `-copyinkf`: forces ffmpeg not to skip non-key frames at a seek
  point. Useful for per-segment invocations, irrelevant for a
  continuous `-f hls` job. [Source: m0ntana/ffmpeg_dynamic_hls — C]
- `-avoid_negative_ts make_zero`: rebases to zero — the OPPOSITE of
  what a long-running live timeline wants. Also conflicts with
  `+genpts`. [Source: thangho98/velox ffmpeg-hls-reference.md — C,
  2026-08]
- `-use_wallclock_as_timestamps 1`: regenerates timestamps from the
  wall clock. Kills A/V sync subtleties and breaks PTS-based seeking;
  only for hopelessly broken sources. [P — documented flag, use as
  last resort]
- Post-encode `tfdt` rewrite (go-ffmpeg's approach): correct but
  requires a second pass over every segment — overkill when
  `-output_ts_offset` already works. [Source: gtsteffaniak/go-ffmpeg
  — C]

**Verdict: keep `-output_ts_offset`.** It's the community-standard fix
for exactly this architecture (jellyfin-virtual-tv uses it for the same
reason). The one refinement: persist the last-emitted PTS per channel
so a relay restart (not just a channel restart) also continues the
timeline instead of resetting it.

**The `+igndts` caveat.** The community-standard input flags are
`+genpts+discardcorrupt+igndts`, but there is a documented failure
mode: on H.264 with B-frames, `+igndts` throws away DTS, and during a
timestamp discontinuity the encoder/muxer can produce a broken video
timeline while audio continues — video freezes, audio plays on.
[Source: m3u-editor#1363 analysis; stream-profile bug report — C,
2026] Template A/B above deliberately use `+genpts+discardcorrupt`
WITHOUT `+igndts`. If corrupt-DTS inputs appear, add `+igndts` back
per-channel as an escape hatch, not the default.

## 3. Keyframe alignment

HLS segments can only start on keyframes. If the GOP doesn't divide
`hls_time`, segments drift: `EXT-X-TARGETDURATION` climbs, players
stutter on rendition switches, and seek latency balloons (one report:
7 s seek → instant after fixing GOP = segment duration).
[Source: dev.to/rtagl — C, 2026-09]

Rules:
- Transcode path: `-g <fps×hls_time> -keyint_min <same> -sc_threshold 0`.
- Remux path: you inherit the source's GOP. If the source GOP is
  longer than `hls_time`, segments get longer than target — acceptable
  for live TV (Emby's transcodes are usually 2–4 s GOPs). If it's
  pathological (>10 s), fall back to Template B to force alignment.
- `independent_segments` in `hls_flags` declares every segment starts
  on a keyframe — required for clean player behavior.

## 4. Error resilience — surviving flaky inputs

The input chain (TeraBox → AList → rclone → Emby → relay) WILL hiccup.
The ffmpeg job must not die with it.

```bash
# Input-side (already in templates above)
-reconnect 1 -reconnect_at_eof 1 -reconnect_streamed 1 \
-reconnect_delay_max 15 \
-timeout 15000000 \
-fflags +genpts+discardcorrupt \
-err_detect aggressive \
```

- The `-reconnect*` family makes ffmpeg retry HTTP input drops
  instead of exiting. `-reconnect_delay_max 15` caps the backoff.
  [Source: vnnkl/macreplay HLS_IMPLEMENTATION.md — C]
- `+discardcorrupt` drops packets already flagged broken before they
  reach the decoder. `-err_detect aggressive` (not `explode` — explode
  makes errors FATAL) keeps decoding through damage with concealment.
  [Source: live-miracles/restream-srs commit 75f1625 — C, 2026-07;
  madebyjamstudios/kodiak engine-hardening.md — C]
- **Memory watchdog (relay-side, not ffmpeg):** a corrupted input once
  made an ffmpeg process leak unboundedly until the kernel OOM-killer
  took the whole stack down. Run a supervisor that reads RSS and
  kills+restarts any ffmpeg over ~500 MB — keeps YOUR retry logic in
  control instead of the OOM-killer. [Source: live-miracles/restream-srs
  — C, 2026-07-10 incident]
- **Playlist hygiene:** `delete_segments` + `hls_delete_threshold 2`
  keeps disk bounded (the relay must never fill its disk with old
  segments). `omit_endlist` keeps the playlist live-appendable.
  [Source: tkgstrator/kototv SKILL.md — C: "Forgetting
  -hls_flags delete_segments → tmpfs fills up, the box OOMs"]
- **DVR window:** `hls_time × hls_list_size` = 4 s × 12 = 48 s of
  rewind buffer. Enough to ride out a reconnect without the player
  falling off the live edge; small enough to keep tune-in fast.
- **SIGTERM handling:** the supervisor must SIGTERM (not SIGKILL)
  ffmpeg so the HLS muxer finalizes the current segment. Zombie
  ffmpeg processes are the #1 operational bug in HLS relay projects.
  [Source: tkgstrator/kototv — C]

## 5. Low-latency reality check

**ffmpeg cannot emit LL-HLS.** Verified against ffmpeg 8.1.2: the `hls`
muxer has zero partial-segment options (`hls_part_time`,
`EXT-X-PART`, blocking playlist reloads don't exist). The `dash`
muxer has `-ldash`; hls doesn't — it's a scope decision, not a version
gap. [Source: rainmanjam/polyemesis docs/roadmap/LL-HLS.md — C,
2026-07; voidstackloop/escld docs/RTMP.md — C]

Realistic floor with plain HLS: **~2–4 s end-to-end** via 1 s segments
+ fast playlist refresh — but 1 s segments double HTTP overhead and
halve error tolerance. For a 1 GB stick on a flaky cloud chain, the
4 s segments in the templates (≈8–12 s glass-to-glass) are the right
trade: stability over shaving seconds. Do NOT chase LL-HLS here.

## 6. Segment type: MPEG-TS vs fMP4

The stick's Vega media pipeline consumes HLS via MSE `appendBuffer`,
which requires **fMP4** (MPEG-TS can't go into a SourceBuffer).
[Source: stick-playback research, 2026-10-05]

BUT the relay serves Emby and other clients too, and MPEG-TS is the
max-compatibility choice (the macreplay/kototv commands both default
to it). Recommendation:
- **Default: MPEG-TS** (`-hls_segment_type mpegts`) — plays
  everywhere, including the current Emby/Flix Pro chain.
- **When the native Vega app's MSE player lands:** add a parallel
  fMP4 rendition (`-hls_segment_type fmp4 -hls_fmp4_init_filename
  init.mp4`, segments as `.m4s`) from the same ffmpeg job, or a
  second lightweight job. Don't switch the primary until the MSE
  player is proven.

## 7. What to change in the relay (concrete)

1. **Keep `-output_ts_offset`.** Add per-channel PTS persistence so
   relay restarts (not just channel restarts) continue the timeline.
2. **Drop `+igndts` from the default input flags** → use
   `+genpts+discardcorrupt`. Keep `+igndts` as a per-channel escape
   hatch for corrupt-DTS sources.
3. **Adopt the remux-first ladder** (Section 1): `-c copy` +
   `h264_mp4toannexb` when the source is H.264/AAC; transcode only
   otherwise. This cuts relay CPU to near-zero for the common case.
4. **Add `-bsf:v h264_mp4toannexb`** to every H.264-copy path —
   non-negotiable.
5. **Re-encode audio to AAC even on remux** (`-c:a aac -b:a 128k
   -ar 48000 -ac 2`) — kills the ADTS segment-boundary glitch class.
6. **Add the reconnect family + `-timeout`** to every input.
7. **Add `temp_file` to `hls_flags`** so readers never see partial
   segments.
8. **Add a memory watchdog** (500 MB RSS kill+restart per ffmpeg).
9. **Handle SIGTERM properly** in the supervisor for clean segment
   finalization.
10. **Don't chase LL-HLS.** 4 s segments; revisit only if tune-in
    latency becomes a measured complaint.

## Sources

- https://github.com/lolimmlost/jellyfin-virtual-tv/blob/HEAD/CONTEXT.md (C)
- https://github.com/gtsteffaniak/go-ffmpeg/blob/HEAD/docs/hls.md (C)
- https://github.com/m0ntana/ffmpeg_dynamic_hls/blob/HEAD/README.md (C)
- https://github.com/roto31/exstreamtv/blob/HEAD/EXStreamTV.wiki/Architecture.md (C)
- https://github.com/roto31/exstreamtv/blob/HEAD/.cursor/skills/exstreamtv-expert/SKILL.md (C)
- https://github.com/live-miracles/restream-srs/commit/75f1625dc3dbe56540e638793ca188c8c908b1e4 (C)
- https://github.com/vnnkl/macreplay/blob/HEAD/HLS_IMPLEMENTATION.md (C)
- https://github.com/tkgstrator/kototv/blob/HEAD/.claude/skills/ffmpeg-hls/SKILL.md (C)
- https://github.com/szebest/taitube-platform/blob/HEAD/.agents/skills/vp-ffmpeg-hls-ladder/SKILL.md (C)
- https://github.com/rendi-api/ffmpeg-llm/blob/HEAD/skills/ffmpeg-command/references/streaming.md (C)
- https://github.com/thangho98/velox/blob/HEAD/docs/ffmpeg-hls-reference.md (C)
- https://github.com/madebyjamstudios/kodiak/blob/HEAD/docs/design/engine-hardening.md (C)
- https://github.com/dispatcharr/dispatcharr/issues/1422 (C)
- https://github.com/m3ue/m3u-editor/issues/1363 (C)
- https://github.com/rainmanjam/polyemesis/blob/HEAD/docs/roadmap/LL-HLS.md (C)
- https://github.com/voidstackloop/escld/blob/HEAD/docs/RTMP.md (C)
- https://github.com/nilaoda/n_m3u8dl-re/commit/d4e49c8964ce37293ec9c4253b8a0f760c83bb28 (C)
- https://dev.to/masonwritescode/add-a-dvr-window-to-your-live-hls-stream-without-404ing-the-scrubber-4db8 (C)
- https://dev.to/rtagl/how-i-fixed-my-hls-seeking-lag-with-one-keyframe-trick-gop-explained-2gh (C)
- https://trac.ffmpeg.org/ticket/3032 (O)
