# Emby Player Tips, Tricks, Hacks & Power-User Guide — KaviTV Edition

**Date:** 2026-10-04 · **Server:** Emby 4.10.1.0 on Windows (SETHS-PC) · **Client:** Fire TV Stick (Emby for Android TV)
**Setup:** 3 KaviTV channels (Horror 413289 / Experimental 413291 / Independent 413292) via one M3U tuner → Python relay `:8100` serving endless MPEG-TS (H.264 + AAC, `video/mp2t`, `.ts` URLs) · self-generated XMLTV/M3U on GitHub Pages · XC bridge `:8880` for Flix Pro.

Companion deep-dives (this folder): `emby-player-hacks-a-firetv.md` (Fire TV client), `emby-player-hacks-b-power.md` (server hacks/plugins/API), `emby-player-hacks-c-tuner.md` (tuner/XMLTV/debugging). Earlier research: `emby-tuner.md`, `emby-tuning.md`, `hls-seek.md`, `platforms.md`, `flixpro.md`.

Seth's rule honored: GitHub + Emby forums consulted throughout; claims carry citation URLs.

---

## 1. Emby Fire TV / Android TV app — every setting that matters for Live TV

The app is **Emby for Android TV** (package `tv.emby.embyatv`; the Amazon Appstore "Emby for Fire TV" is identical, no unlock needed anymore). Player core is **ExoPlayer 2.18.7**. Latest build **2.1.55g** (Aug 2026) via APKMirror; the Appstore build auto-updates. (Full version/app detail: companion A §0.)

**Settings → Playback**
- **Max streaming bitrate** — posts as `MaxStreamingBitrate` in PlaybackInfo. Below the channel's real bitrate → server transcodes with `TranscodeReason=ContainerBitrateExceedsLimit`. On a LAN, **Auto** is the safe default (a forum report saw ~1 fps video after forcing 100 Mbps on a passthrough setup). https://emby.media/community/index.php?/topic/80828-virtualtv-plugin/page/3/
- **Audio / Audio Output, DTS/DTS-HD passthrough toggles** — exist in the TV app (missing from the unified mobile app). For a stereo TV/soundbar, Emby dev ebr's advice: **"Downmix to stereo"** — the app downmixes client-side now instead of asking the server to transcode/remux, which maximizes direct play. https://emby.media/community/index.php?/topic/126826-pass-thru-on-android-version-of-app/
- **Refresh rate switching** + "Prefer exact refresh rate" — cosmetic for our 30/60 fps progressive channels; doesn't affect transcode decisions.
- **Use external player** — hands playback to VLC on the Fire TV. The escape hatch when ExoPlayer chokes but VLC plays the same URL. https://emby.media/community/topic/106496-mi-box-s-no-audio-passthrough/
- **Stats for nerds** — playback OSD settings menu, or **long-press select** during playback. Confirms Direct Play vs transcode on the TV itself.

**Settings → Live TV → "Enable direct play of live TV"** — the single most important toggle (see §2).

**There's also a unified "Emby for Android" app (3.5.x)** with a TV mode; its Live TV toggle is called **"Prefer Direct Streaming of LiveTV"** (Client App Settings → Playback). It lacks the DTS passthrough toggles. Only relevant if Seth ever switches apps. https://emby.media/community/topic/148190-guid-ssl-issue-for-remote-user-swapping-from-androidtv-to-unified-client-on-ccwgtv-4k/

---

## 2. Direct Play vs Transcode for Live TV — the core mental model

Emby dev **ebr** documents two modes (https://emby.media/community/index.php?/topic/104287-confusion-about-live-tv-settings/page/2/):

| | Seek mode (default) | Direct play of Live TV (toggle ON) |
|---|---|---|
| What the server does | Remuxes tuner TS → HLS segments (`MinSegments=2`, `BreakOnNonKeyFrames=true`) | Passes TS bytes through untouched (no ffmpeg) |
| Tune-in | ~8–10 s | ~3 s (ebr measured) |
| Pause/seek | Works | **Disabled** |
| Closed captions (Android TV) | Work | Don't work |

Nuance: even "direct" live TV flows **through the server** (tuner stream-sharing), it just isn't re-containerized. Switching a session between modes costs ~15 s — pick one and stay in it.

**When 4.10.x direct-plays vs transcodes** — decided server-side by `StreamBuilder` against the client's DeviceProfile. The Fire TV app posts profile **`Android-Exo`** whose video DirectPlayProfile explicitly includes containers **`ts, mpegts`** + codecs `h264, hevc, vp8, vp9…` + audio `aac, mp3, ac3…` (https://emby.media/community/index.php?/topic/80828-virtualtv-plugin/page/3/). Our H.264/AAC MPEG-TS channels are direct-playable **on paper** — all of container+codec+bitrate+user-policy must pass; preference order is always Direct Play → Direct Stream (remux) → Transcode (https://github.com/MediaBrowser/Emby/wiki/Playback-Guidelines).

**The `ts` vs `mpegts` alias trap** (worth knowing, not currently biting us): Emby can report a live source as `Container: mpegts` while a client's profile only lists `ts` → `TranscodeReasons=ContainerNotSupported` on an otherwise playable stream. Third-party client plezy fixed exactly this by advertising both spellings (https://github.com/edde746/plezy/pull/2294). The official Android-Exo profile already lists **both** `ts,mpegts`, so our Fire TV is fine — but if "ContainerNotSupported" ever appears in our logs, this is the first place to look.

**Maximizing direct play for KaviTV on Fire TV:** (1) Live TV → direct play ON; (2) Playback → bitrate Auto; (3) Playback → Audio = Downmix to stereo; (4) server user policy allows direct play, no bitrate cap; (5) keep the stream clean: H.264 ≤ High@4.1-ish, AAC-LC ADTS, steady PAT/PMT. (Companion A §2.)

---

## 3. Emby hacks & power tricks (GitHub-sourced)

### 3.1 Web client customization
- **Persistent route: Dashboard → General → Custom CSS** (stored in server config, survives updates). Active themes: **Embymalism** (`@import url("https://cdn.jsdelivr.net/gh/v1rusnl/Embymalism@main/Embymalism.css");`, updated days ago — https://github.com/v1rusnl/embymalism), **Emby-Fluent** (https://github.com/heichaowo/Emby-Fluent/blob/HEAD/README-EN.md).
- **Direct JS injection** into `C:\Users\sethr\AppData\Roaming\Emby-Server\system\dashboard-ui\index.html` works (emby-crx beautification, home-swiper-ui carousels — https://github.com/sohag1192/emby-home-swiper-ui) but is **wiped on every server update** — keep snippets in the repo and re-apply, or use Tampermonkey `@match *://*/web/index.html*` for client-only injection.

### 3.2 Reverse proxy (nginx/Caddy/Apache) + Tailscale Serve
- Websocket path is **`/embywebsocket`** — proxy must forward the Upgrade handshake (https://emby.media/community/topic/50062-web-sockets-and-reverse-proxy/). Minimal nginx: `proxy_http_version 1.1` + `Upgrade`/`Connection` headers + **`proxy_buffering off`** (critical — otherwise HLS/live segments flush in 60 s chunks) + long read timeouts. Sample: https://github.com/caizhenwei33-cmyk/emby
- Caddy: `reverse_proxy 127.0.0.1:8096` handles websockets transparently.
- **Tailscale Serve gotcha:** `tailscale serve --bg 8096` gives tailnet HTTPS, but 100.x IPs count as *remote* — Emby's **Network → "Allow remote connections"** must be on.

### 3.3 Transcoding tuning beyond the dashboard
- `C:\Users\sethr\AppData\Roaming\Emby-Server\config\encoding.xml` mirrors dashboard settings (edit with server stopped).
- Verify HW detection: bundled `ffdetect-emby qsvenc` / `ffdetect-emby nvenc`. Premiere-gated; confirm it's *active* by forcing a low bitrate and watching dashboard session + ffmpeg CPU.
- NVENC preset names differ from x264 (`hp/hq/bd/ll/llhq/…`, not ultrafast→placebo).
- Fastest way to see Emby's real ffmpeg command: read the top of any `logs\ffmpeg-transcode-*.txt`.
- **No user-facing HLS segment-length knob** — it's driven by the client's DeviceProfile (`SegmentLength: 3`, `MinSegments: 2` typical). A bridge can inject its own profile via PlaybackInfo.

### 3.4 Library/scan optimization
- Full scan = scheduled task key **`RefreshLibrary`**; Windows real-time monitoring covers most changes so the daily scan is a backstop.
- Chapter images: per-library toggle, costs a full decode pass — schedule off-peak.
- **Trickplay** (scrub thumbnails, 4.9/4.10): offload to GPU via **media_preview_generator** (https://github.com/stevezau/media_preview_generator) instead of Emby's built-in decoder.

### 3.5 Plugins worth knowing (Live TV / IPTV)
| Plugin | Why |
|---|---|
| [EMBY-XC](https://github.com/sftech13/emby-xc) | Xtream→Emby tuner; **"Clear Channel Logo Cache on Guide Refresh"**; built-in `RefreshLiveTvTask` every 4 h |
| [emby-xtream](https://github.com/firestaerter3/emby-xtream) | Active fork; stream format ts/m3u8, EPG/M3U cache knobs, STRM sync, dashboard. ⚠️ Xtream creds end up plaintext in served M3U/STRMs |
| [emby-xtreamimport](https://github.com/siffdk/emby-xtreamimport) | Xtream → .strm libraries + M3U live channels |
| [Phospharr](https://github.com/invectedgaming/phospharr) | Pushes guide refreshes to Emby via API — **the pattern KaviTV's generator should copy** (trigger RefreshGuide after each generate.py run) |
| Playback Reporting (community) | Server-side playback stats — useful for KaviTV viewing analytics |

### 3.6 API power tricks (base `http://SETHS-PC:8096/emby`, `?api_key=` or `X-Emby-Token`)
- `GET /Sessions` — audit for leaked transcodes. `POST /Sessions/{Id}/Playing/{Command}` — remote-control clients.
- **Kill switches:** `POST /LiveStreams/Close?LiveStreamId=` (frees the tuner) · `DELETE /emby/Videos/ActiveEncodings?playSessionId=&deviceId=` (kills stuck transcodes, returns 204).
- `POST /System/Restart?api_key=` — remote restart (nightly maintenance scripts; check `GET /Sessions` first).
- **WebSocket** `ws:///embywebsocket?api_key=&deviceId=` — `LibraryChanged`, `ScheduledTaskEnded` events; built-in **webhooks** emit `playback.start/stop` (simplest KaviTV viewing stats — no polling).
- Scheduled tasks: `GET /ScheduledTasks`, `POST /ScheduledTasks/Running/{Id}` (204), `POST /ScheduledTasks/{Id}/Triggers` with `TaskTriggerInfo` (`IntervalTicks` in 100 ns ticks — e.g. 6 h = `216000000000`). Refresh Guide key = `RefreshGuide` (default daily). **Luke's rule:** interval ≈ guide-data duration minus a couple hours; never run it faster than its own duration (overlaps restart each other).

---

## 4. M3U tuner power tips

- **One tuner is right for KaviTV.** Emby does *not* merge multiple M3U tuners — each gets `m3u_`+md5(url) channel-id prefixes, so a second tuner would duplicate the 3 channels. Multiple tuners are only for per-provider connection limits or per-user tag dedication. Playback tries tuners in creation order. ([M3U-Tuners.md](https://github.com/embysupport/emby.docs/blob/HEAD/M3U-Tuners.md))
- **Simultaneous stream limit:** `0` (default) = unlimited. With `.ts` URLs the server uses `SharedHttpStream` — one upstream connection per channel, refcounted ("consumer count") — so the limit counts *distinct tuned channels*, not viewers. **Keep at 0.**
- **"Enable Stream Looping" (autoloop): OFF — verified in code.** In `M3UTunerHost.CreateMediaSourceInfo`: `supportsDirectPlay = !info.EnableStreamLooping && info.TunerCount == 0`, `supportsDirectStream = !info.EnableStreamLooping`, and `SharedHttpStream` requires `!RequiresLooping`. **ON disables direct play, direct stream, AND sharing** — every viewer goes through ffmpeg. It's for finite VOD-like "live" files, not endless TS. (https://github.com/jellyfin/jellyfin/blob/master/src/Jellyfin.LiveTv/TunerHosts/M3UTunerHost.cs)
- **Channel numbers:** `tvg-chno` supported but must be **numeric** (parser ignores non-numeric). tvg-ids must stay untouched.
- **Hiding channels:** Edit Metadata → tag/parental rating, or just keep the M3U minimal (ebr's own advice — https://emby.media/community/index.php?/topic/74396-tv-guide-customization/). Our 3-channel playlist already does this.
- **Channel image source:** tuner setting, **M3U** vs Guide Data — set to **M3U** so `tvg-logo` wins.

---

## 5. XMLTV guide hacks

- **Guide Days:** set explicitly (e.g. **3**) instead of Auto for a 3-channel guide (Live TV → Advanced).
- **Cadence:** Luke's rule — interval ≈ guide duration minus a couple hours. For our 72 h guide: `generate.py` → push → Refresh Guide on a **24 h** schedule, generation *before* the refresh. (Companion C §2.1.)
- **Program images: YES, Emby shows `<icon>` per `<programme>`.** Mapped to `ProgramInfo.ImageUrl` (verified in Jellyfin's `XmlTvListingsProvider.cs`; confirmed for Emby by the emby-xtream author — https://github.com/firestaerter3/emby-xtream/commit/47ac7b8e370139af3178a1f21e2d3312588200f2). Guide grid shows programme art; where absent it **falls back to the channel logo** — which is why Seth's guide looked logo-only. **Put a real `<icon>` on every programme** (even a per-channel default) and the Fire TV guide populates. `?v=N` busting works for programme icons too.
- **Categories:** map XMLTV `<category>` values to Emby program types in the Xml TV provider settings (movies/sports/kids…). Use consistent strings in the generator.
- **Stale logos beyond `?v=N`:** per-channel image delete (Edit Metadata) + Refresh Guide. Watch logs for `Error downloading image … mime type text/html` = the URL served HTML (GitHub *blob* page instead of *raw*) — classic "logo never updates" cause (https://emby.media/community/topic/129561-missing-guide-images/). No server-side logo cache folder to purge on Windows; images tracked in `library.db`.

---

## 6. Debugging Live TV like a pro

**Log locations (Windows):** `%APPDATA%\Emby-Server\programdata\logs\embyserver.txt` · per-session `ffmpeg-transcode-*.txt` / `ffmpeg-directstream-*.txt` (full ffmpeg command at top) · temp segments in `programdata\transcoding-temp\`. (https://github.com/embysupport/emby.docs/blob/HEAD/Log-Files.md)

**Tune-up sequence — what each line proves:**
| Log line | Meaning |
|---|---|
| `M3UTunerHost: Opening SharedHttpStream Live stream from http://10.0.0.98:8100/…` | Server issued GET to relay — **tuner reachability proven past this line** |
| `Beginning SharedHttpStream stream to …\transcoding-temp\{guid}.ts` | Relay responded; body copying |
| `Live stream opened after {N}ms` | Open succeeded — everything after is transcode/client territory |
| `consumer count is now {N}` → 0 → `Closing live stream` → `Deleting temp file` | Normal teardown |
| `Zero bytes copied from stream SharedHttpStream` → `EndOfStreamException` | Relay accepted but sent **no bytes** — relay wedged / ffmpeg died |
| `Error opening tuner` + `HttpRequestException`/`SocketException` | Tuner unreachable (relay down, wrong IP/port, firewall) |
| `LiveTvConflictException: Unable to find host to play channel` | Terminal tuner failure — all hosts failed |
| `…/master.m3u8?…&TranscodeReasons=ContainerNotSupported,…` | Transcode decision + reasons |
| `FfRunException` / `No video encoder found for 'h264'` | ffmpeg itself failed — server/install problem |
| `Playback stopped … Stopped at 0 ms` right after open | **Client rejected the stream** |

**TranscodeReason tokens:** `ContainerNotSupported` (container not in profile / live source `SupportsDirectPlay: false`) · `VideoCodecNotSupported`/`AudioCodecNotSupported` · `ContainerBitrateExceedsLimit` (app bitrate cap too low — set Auto) · `DirectPlayError` (client tried direct, rejected — check ffmpeg log) · `SubtitleCodecNotSupported`. Full enum: https://github.com/jellyfin/jellyfin/blob/master/MediaBrowser.Model/Session/TranscodeReason.cs

**"No compatible streams are currently available"** = PlaybackInfo returned zero playable sources. Server-side causes, most→least common: (1) **tuner couldn't be opened** (unreachable/403/zero bytes) — #1 for Live TV; (2) broken ffmpeg (`No video encoder found` — reinstall official build); (3) multiple server instances / SQLite lock; (4) client codec profile forcing a failing transcode.

**`RemoteServiceUnavailableException` is a red herring for tuner debugging** — it's Emby Connect/cloud reachability (firewall/VPN), not the relay (Luke — https://emby.media/community/topic/123518-fire-stick-stops-on-pin-screen/page/2/). Seth saw this exact text in his Fire TV photo; treat a one-off as transient client↔server failure (e.g. tried during a relay restart), not a codec problem.

**The 12-item troubleshooting checklist** (ordered by likelihood for our setup) is in companion C §5 — relay reachability first, `?v=N` logos, guide window, then ffmpeg logs.

---

## 7. Firestick-specific

- **Cache clearing:** Fire TV Settings → Applications → Manage Installed Applications → Emby → **Clear cache** (first resort; fixes 1-fps and stale-data cases). Clear *data* only as a last resort (factory-resets the app, re-login required).
- **Sideloading:** Amazon Appstore first ("Emby for Fire TV", auto-updates). APKMirror (`tv.emby.embyatv`, newest 2.1.55g) for versions the store hasn't pushed. Downloader app or `adb install`; "Apps from Unknown Sources" on. (Fire OS only — Vega OS can't sideload.)
- **Network:** 5 GHz Wi-Fi or Amazon Ethernet adapter; force-stop background apps; keep free storage (low storage → buffering). If connects stall *only* from the Fire TV, suspect the **IPv4/IPv6 path** issue (one client changelog fixed "stall on unavailable IPv4 or IPv6 path" — https://github.com/edde746/plezy/releases/tag/2.19.0).
- **Audio/buffering:** Fire TV Settings → Display and Sounds → Audio → Surround Sound → try stereo-only if buffering on a stereo setup; pairs with in-app "Downmix to stereo".
- **HDMI-CEC:** toggle off if phantom input/AVR weirdness kills playback. No Emby-specific CEC bug documented.
- **Audio passthrough** (AC3/DTS/TrueHD library content only — our AAC-stereo channels don't need it): Fire TV Surround → Best available + in-app Audio Output + DTS/DTS-HD passthrough toggles.

---

## 8. Top 5 things we should change or try (opinionated)

**1. Turn ON "Enable direct play of live TV" on the Fire TV app — today.**
Our exact symptom (MPEG-TS M3U channel plays a split second, then "Playback Error") is documented in an Emby forum thread and fixed by this toggle (https://emby.media/community/index.php?/topic/135515-live-tv-playback-error-in-emby-on-fire-tv-and-android-tv/&do=findComment&comment=1416185). It bypasses the server HLS remux entirely (~3 s tune-in vs 8–10 s) and removes Emby's ffmpeg from the path — which is where our crash lives. Cost: no pause/seek on live TV, no closed captions in the Android TV app. For movie channels you watch start-to-finish, that's the right trade.

**2. Lock in the `.ts` + autoloop-OFF + limit-0 tuner configuration and never drift.**
Verified in `M3UTunerHost.cs`: `.ts` is the *only* URL shape that gets the shared, direct-play path with zero probing; autoloop ON kills direct play, direct stream, *and* sharing for every viewer; limit 0 is correct because sharing refcounts per channel. These three are already set — the risk is a future M3U edit silently moving us off the good path (e.g. back to `.m3u8`, which forces per-viewer ffmpeg remux and can never share). Consider a CI check on the generated M3U asserting: URLs end in `.ts`, tvg-ids stable, no `tvg-chno` unless intended.

**3. Harden the relay's TS output for ExoPlayer specifically.**
ExoPlayer's TS extractor is documentedly fragile on live MPEG-TS (jellyfin-androidtv#5237: "playback loops/resets every ~30s (ExoPlayer internal discontinuity)"; ExoPlayer#1789: `Discontinuity detected [expected X, got Y]` freezes). VLC tolerates what ExoPlayer rejects — which matches "works when probed, dies on Fire TV". We've added `-copyts -start_at_zero`; if the split-second crash persists, next steps in order: (a) confirm first bytes contain PAT/PMT + keyframe (ExoPlayer joins mid-stream and needs them immediately — `-mpegts_flags resend_headers` is already set, verify it's effective); (b) check AAC is ADTS-framed with consistent frame sizes; (c) compare "Stats for nerds" + `BuildVideoItem` PlayMethod with direct-play ON vs OFF to isolate relay-framing vs server-remux; (d) as a last resort, have the relay *transcode* audio to AAC (`-c:a aac`) instead of stream-copying, since audio framing is the most common ExoPlayer TS killer.

**4. Put `<icon>` on every XMLTV `<programme>`.**
Seth already noticed posters missing. Emby falls back to the channel logo when a programme has no image — the guide looks bare. The generator already has per-movie data; add poster URLs (Emby `Items/{id}/Images/Primary` or TMDB) as programme icons. This is the highest visible-payoff change after playback itself.

**5. Close the ops loop: generate → push → RefreshGuide in one motion, Guide Days = 3.**
Copy the Phospharr pattern: `generate.py` finishes → `POST /emby/ScheduledTasks/Running/{RefreshGuideId}` → poll `State` to Idle. Set Live TV → Advanced → Guide Days to **3** (explicit, not Auto) to match the 72 h window. And add the EMBY-XC plugin's trick to the toolbox: its "Clear Channel Logo Cache on Guide Refresh" exists because logos are sticky — if `?v=N` ever stops working, that's the next lever before delete/re-add tuner.

**Deliberately NOT recommended:** a second M3U tuner (duplicates channels, no pooling benefit); stream-looping ON ("fixes" nothing for endless TS, kills sharing); chasing fMP4-HLS output (Plex-ism, not an Emby client option); editing `index.html` for web UI tweaks (use Dashboard → Custom CSS); weekly guide refreshes (Luke: interval ≈ guide duration minus a couple hours).
