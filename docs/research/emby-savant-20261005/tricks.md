# Emby Server API — Savant Tricks (2026-10-05)

Researched GitHub-first for Seth's Emby 4.10.1.0. Focus: remote operation
and automation. Every finding labeled **[O]** verified-official,
**[C]** verified-community, **[P]** plausible, with source + date.

Base URL: `http://SETHS-PC:8096`. Auth: `X-Emby-Token: <api-key>` header
(or `Authorization: MediaBrowser Token="<key>"`). API key = server-wide,
no user context — per-user actions (mark played, favorites) need a
username/password login for `AccessToken` + `UserId`. **[C]**
(https://github.com/oratorian/emby-mcp-server, 2026-05)

---

## 1. Sessions — remote control of other clients

### 1.1 Playback commands on another session
```
POST /Sessions/{id}/Playing/Pause
POST /Sessions/{id}/Playing/Unpause
POST /Sessions/{id}/Playing/PlayPause
POST /Sessions/{id}/Playing/Stop
POST /Sessions/{id}/Playing/NextTrack
POST /Sessions/{id}/Playing/PreviousTrack
POST /Sessions/{id}/Playing/Seek?SeekPositionTicks=<ticks>
```
**[O]** (https://emby.media/community/topic/81658-remote-control-howto/,
long-standing wiki). Ticks: 1 tick = 100 ns → `ticks = seconds × 10⁷`. **[O]**

**Gotchas:**
- Sessions are **ephemeral** — they appear when a client connects and vanish
  when it closes; session IDs change. Always `GET /Sessions` fresh. **[C]**
  (emby-mcp-server README)
- **Stop is permanent.** Emby keeps no server-side resume history; you can't
  tell a client to "resume where you left off" after Stop. **[C]** (same)
- `NextTrack`/`PreviousTrack` are **quirky on video** — most video clients
  ignore them or remap to 30s skip / chapter jump. **[C]** (same)
- The `capabilities` object on each session tells you what's advertised
  (`can_set_volume`, `can_display_message`, `can_go_home`, `can_navigate`,
  …). Playstate commands (Pause/Stop/Seek) are NOT in capabilities — they're
  always available on any controllable session (`SupportsRemoteControl`). **[C]**

### 1.2 Start playback on another session (the Fire TV trick)
```
POST /Sessions/{id}/Playing
  ItemIds=<comma-delimited ids>&PlayCommand=PlayNow|PlayNext|PlayLast
  &StartPositionTicks=<ticks>&MediaSourceId=<id>
  &AudioStreamIndex=<n>&SubtitleStreamIndex=<n>&StartIndex=<n>
```
**[O]** (Emby remote-control wiki). This is how you push a specific item
(e.g. a KaviTV channel's current program) onto the Firestick's session
without touching the remote. `StartPositionTicks` is ignored for
PlayNext/PlayLast.

### 1.3 General commands — USE THE BODIED FORM
```
POST /Sessions/{id}/Command
Content-Type: application/json
{"Name": "SetVolume", "Arguments": {"Volume": "50"}}
```
Known command names: `VolumeUp`, `VolumeDown`, `Mute`, `SetVolume`
(`Arguments.Volume`), `DisplayMessage` (`Arguments`: `Header`, `Text`,
`TimeoutMs`), `ToggleFullscreen`, `GoHome`, `MoveUp/Down/Left/Right`,
`PageUp`, `PageDown`, `PreviousLetter`, `NextLetter`. **[O]** (Emby wiki)
+ **[C]** (emby-mcp-server).

**Critical:** the per-command path `POST /Sessions/{id}/Command/{Command}`
**silently no-ops** on some clients (verified: `SetVolume` on Emby Theater
Windows). The bodied form works everywhere tested. **[C]**
(emby-mcp-server README + design notes, 2026-05)

### 1.4 Remove an extra user from a session
```
DELETE /Sessions/{Id}/Users/{UserId}
```
**[C]** (https://github.com/zhaiyong4118/dart_emby_api,
ScheduledTaskServiceApi/SessionsServiceApi docs, 2026-08)

### 1.5 Manage API keys via the API
```
GET  /Auth/Keys
DELETE /Auth/Keys/{Key}
```
**[C]** (dart_emby_api docs). Useful for rotation without the dashboard.

---

## 2. Live TV — tuners, channels, guide

### 2.1 The setup flow (verified live, reversible)
1. `GET /LiveTv/Info` — `IsEnabled` flips `true` the moment one tuner exists.
2. `POST /LiveTv/TunerHosts` — add tuner (`m3u` or `hdhomerun`).
   **GOTCHA: Emby fetches and validates the playlist AT ADD TIME.**
   Unreachable URL → HTTP 500 "Connection timed out", NO tuner created.
   Have the playlist reachable from the SERVER's network position. **[C]**
   (https://github.com/ghively/gh-tools/blob/HEAD/skills/emby-control/references/livetv.md,
   live-verified 2026-07-15)
3. `POST /LiveTv/ListingProviders` — add guide (`xmltv` or `embygn`).
   Gzipped `.xml.gz` URLs are fine.
4. Run the **"Refresh Guide"** scheduled task (see §5) — channels import
   **asynchronously**; count is 0 until this runs. **[C]** (same)
5. `GET /LiveTv/TunerHosts/Types` and `GET /LiveTv/ListingProviders/Available`
   list what's supported on your server.

### 2.2 Channel management
```
POST /LiveTv/Manage/Channels/{Id}/Disabled      {"Disabled": true}
POST /LiveTv/Manage/Channels/{Id}/SortIndex     {"SortIndex": n}
GET  /LiveTv/Channels?include_disabled=true     (management view)
```
**[C]** (gh-tools livetv.md). Note: Seth's guide-sorting experiments
(favorites, sort index) were ignored by the Fire TV client — server-side
disable/reorder works, client display is the client's business.

### 2.3 Channel mapping (guide names ≠ tuner names)
```
GET  /LiveTv/ChannelMappingOptions?ProviderId=<id>
POST /LiveTv/ChannelMappings
```
**[C]** (gh-tools livetv.md).

### 2.4 Guide queries
`GET /LiveTv/Programs` (hours/search params), `GET /LiveTv/Programs/Recommended`.
**[C]** (gh-tools livetv.md).

### 2.5 DVR (Premiere)
```
GET  /LiveTv/Timers/Defaults?ProgramId=<id>     → POST the result to…
POST /LiveTv/Timers          (one airing)
POST /LiveTv/SeriesTimers     (series pass)
GET  /LiveTv/Recordings/Folders
```
Recording path config lives in the **`livetv` named config store**
(`GET /System/Configuration/livetv`). **[C]** (gh-tools livetv.md).

### 2.6 Tuner removal
`DELETE /LiveTv/TunerHosts?Id=<id>` → 200, tuner gone, `IsEnabled` back
to `false`. **[C]** (gh-tools livetv.md, live-verified).

### 2.7 User access
Each user's policy: `EnableLiveTvAccess` (view), `EnableLiveTvManagement`
(admin). Live TV management APIs require the caller's policy to have it.
**[C]** (gh-tools livetv.md).

---

## 3. Playstate reporting (client → server)

For a client (or a bridge acting as one) reporting its own playback:

```
POST /Sessions/Playing          (PlaybackStartInfo)
POST /Sessions/Playing/Progress (PlaybackProgressInfo)
POST /Sessions/Playing/Stopped  (PlaybackStopInfo)
```
Body fields: `ItemId`, `MediaSourceId`, `PlaySessionId`, `PositionTicks`,
`CanSeek`, `IsPaused`, `PlayMethod` (`Transcode`|`DirectStream`|`DirectPlay`),
stream indexes, queue fields, `EventName`. **[C]**
(https://github.com/yuanjing-hash/ohmycine research docs, 2026-05;
https://github.com/ad-repo/nullplayer SKILL.md)

**Critical:** `PlaySessionId` is **required** — `POST /Sessions/Playing/Progress`
without it returns **400**. Generate a GUID at start, reuse for
Progress/Stop. **[C]** (https://github.com/ccoupel/emby_virtuallib commit
2bc630b, 2026-04-05).

`ProgressEvent` enum values: `TimeUpdate`, `Pause`, `Unpause`,
`VolumeChange`, `RepeatModeChange`, `AudioTrackChange`,
`SubtitleTrackChange`, `PlaylistItemMove/Add/Remove`, `QualityChange`,
`StateChange`, `SubtitleOffsetChange`, `PlaybackRateChange`,
`ShuffleChange`, `SleepTimerChange`. **[C]** (ohmycine research, from
official schemas).

Real clients throttle progress reports to ~10 seconds. **[C]**
(ohmycine, from apiclient.js/playbackmanager.js source).

Legacy user-scoped equivalents (still live):
`POST /Users/{UserId}/PlayingItems/{Id}`,
`POST /Users/{UserId}/PlayingItems/{Id}/Progress`,
`POST /Users/{UserId}/PlayingItems/{Id}/Delete`. **[C]** (same)

---

## 4. Webhooks & real-time events

### 4.1 Webhooks plugin (Premiere required)
Dashboard → Plugins → Catalog → **Webhooks**, then per-user
Notifications → Add. Event types include `PlaybackStart` (3),
`PlaybackProgress` (4), `PlaybackStop` (5), `ItemAdded` (1),
`ItemDeleted` (24), `MarkPlayed`, `MarkUnplayed`. The Generic destination
sends custom headers; payload is template-driven. **[C]**
(https://github.com/tophers/mixerbee WEBHOOKS_EMBY.md, 2026-10;
https://github.com/sl0wz3r/dupearr research, from NotificationType.cs).

### 4.2 tracearr/media-server-sse — the no-Premiere alternative
Plugin adding a **Server-Sent Events** endpoint: real-time playback,
session, library, task, and server-stat events over ONE authenticated
HTTP connection. Pause is a first-class event; library items arrive one
per event; includes CPU/RAM stats. No Premiere needed, no hosted receiver
needed. **[C]** (https://github.com/tracearr/media-server-sse, 2026-10).
Comparison: https://github.com/connorgallopo/tracearr-docs (sse-plugin/comparison).

### 4.3 WebSocket
`ws:///embywebsocket`. Client → server: `SessionsStart`
(interval in ms), `SessionsStop`. Server → client: `Sessions`,
`PlaybackStarted/Stopped`, `SessionEnded`, `Play`, `Playstate`,
`GeneralCommand`, `UserDataChanged`. **[C]**
(https://github.com/evilpig/homeassistant-emby docs, 2026-07).
Note: no dedicated pause/unpause events — infer from `PlayState.IsPaused`.

---

## 5. Scheduled tasks

```
GET  /ScheduledTasks                        list all (find by Key/Name)
POST /ScheduledTasks/Running/{Id}           START a task
POST /ScheduledTasks/Running/{Id}/Delete    stop a running task
POST /ScheduledTasks/{Id}/Triggers          update triggers
```
**The trigger endpoint is `/ScheduledTasks/Running/{Id}`, NOT
`/ScheduledTasks/{Id}/Trigger` — the latter 404s.** **[C]**
(https://github.com/evilpig/homeassistant-emby commit 734e482, 2025-11).

Guide refresh = find task with Key `RefreshGuide`, POST Running. **[C]**
(https://github.com/snapetech/iptvtunerr docs; Emby forum 2019).

Handy task keys: `RefreshLibrary` (scan), `RefreshGuide`, `CleanLogFiles`,
`CleanCache`, `CleanTempFiles`, `CleanDatabase`, `CleanTranscodingTempFiles`,
`BackupDatabase`, `OptimizeDatabase`, `RefreshChapterImages`,
`DownloadSubtitles`, `RefreshPeople`. **[C]** (emby-mcp-server README).

---

## 6. Library & user shortcuts

- **Round-trip writes:** `POST /System/Configuration`, `/Items/{id}`,
  `/Users/{id}/Policy` expect the FULL object — a partial POST **silently
  resets omitted fields**. Always GET-merge-POST. **[C]** (gh-tools SKILL.md)
- **Plugin settings** live in named stores `/System/Configuration/{key}`
  (e.g. `webhooks`, `livetv`, `dlna`) — the legacy
  `/Plugins/{id}/Configuration` route **500s** for most modern plugins. **[C]**
- **Deletes:** almost every `DELETE` has a `POST …/Delete` alias.
  `GET /Items/{Id}/DeleteInfo` → `{"Paths": [...]}` previews what dies.
  Deletes remove the WHOLE item folder; `DELETE /Items/999999`
  (nonexistent) still returns 204. **[C]** (dupearr research, live-tested)
- **Self-discovery:** the server exposes its live OpenAPI spec —
  enumerate endpoints programmatically instead of guessing. The
  gh-tools skill uses `emby_list_endpoints` for this. **[C]**
- Ticks everywhere: seconds × 10⁷. **[O]**
- `POST /Users/{userId}/PlayedItems/{itemId}` = scrobble/mark played.
  **[C]** (nullplayer SKILL.md)

---

## 7. 4.10.x notes

- 4.10.0.40 changelog is fixes-only at the API surface: improved HLS
  manifest `codecs` values, live-TV favorite/guide fixes, Roku search
  fix. No breaking API changes found. **[C]**
  (https://github.com/linuxserver/docker-emby/releases/tag/4.10.0.40-ls296)
- New **Home endpoint workflow is gated at 4.10.0.4** — Emby's own client
  won't use it below that; the 4.9 schema listing it is not evidence it
  works. Seth is on 4.10.1.0 → usable. **[C]**
  (https://github.com/blurbery/vivid docs/cores/emby.md, 2026-10)
- Emby went closed-source after 3.5.3; Jellyfin is the fork — Jellyfin
  API knowledge transfers ~90% (same heritage), but verify endpoint by
  endpoint. **[O]** (well-established)

---

## 8. Already covered elsewhere (one-liners)

- `GET /Sessions` lists sessions with `NowPlayingItem`, `PlayState`,
  transcode info — the ops console/watchdog already use it.
- `DisplayMessage` via bodied `/Sessions/{id}/Command` puts text on the
  Fire TV screen — the phone-remote "message a screen" feature.
- The `mby` TUI (https://github.com/slatkin/mby) implements exactly the
  remote-control-sessions flow the ops console needs — steal its patterns.
