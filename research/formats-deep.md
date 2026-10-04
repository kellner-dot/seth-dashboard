# IPTV Formats Deep Dive — Flix Pro Player, XC M3U, Stalker, EPG Formats

**Date:** 2026-10-04 · **For:** Seth's KaviTV setup (Emby + Python XC bridge + Flix Pro Player)
**Companions:** `flixpro.md` (Xtream client behavior), `xtream-api.md` (API reference), `platforms.md` (architecture), `emby-tuner.md`
**Method:** three parallel research tracks (web + GitHub doc fetches); claims cite sources; unverified items flagged.

---

## 1. Flix Pro Player — every input format

### 1.1 Identity (read first — two apps share the name)

| | Seth's app | The other one |
|---|---|---|
| Name | Flix Pro Player - IPTV | Flix Pro Player |
| Developer | Edgecode solutions / FlixProPlayer LLC | Logic Titans |
| Android package | `flix.pro.tv` | `flix.pro.player` |
| Status | **Delisted from Google Play 2026-06-17** (v3.1.1, May 2025 last); sideload-only | Active, v3.3.5 (Aug 2026) |
| iOS | Jason Littleton listing, same branding | — |

Everything below is about **`flix.pro.tv`** only. Sources: [AppBrain](https://www.Appbrain.Com/app/flix-pro-player-iptv/flix.pro.tv), [chrome-stats](https://chrome-stats.com/d/flix.pro.tv), [APKPure](https://apkpure.com/flix-pro-player-iptv/flix.pro.tv).

### 1.2 Xtream Codes API login (primary, well-documented)

Server URL + username + password → `player_api.php`. Full action inventory, EPG surfaces (all three: `get_short_epg`, `get_simple_data_table` + aliases, `xmltv.php`), stream URL shapes (`/live/`, `/movie/`, `/series/`, `/timeshift/`), base64 EPG titles, and ~10 server-side quirks are documented in **`flixpro.md` §2–6** — not repeated here. Our bridge already implements the P0 surface.

### 1.3 M3U/M3U8 playlist mode (thin public record — read honestly)

**Verified:**
- Declared playlist types on the store listing: **"XC, M3U, Stalker Portal (Coming soon)"** — [APKPure](https://apkpure.com/flix-pro-player-iptv/flix.pro.tv)
- The developer's documented setup flow (verbatim): *"Get an xtream playlist from your provider (we are just a Media player). Upload your playlist to our website: https://flixproplayer.com/ or the app."*
- **Web upload path is real**: flixproplayer.com (Next.js, Cloudflare) exposes an app route **`/manage-playlists/`** seen in a [urlscan.io crawl](https://urlscan.io/result/5d7228b7-cbd3-4fa0-88de-afba890e8d2c/) — the "upload your playlist to our website" flow is a genuine web UI.
- App delisted 2025-06-17; no updates since v3.1.1 (May 2025). Sideload-only.

**Could NOT verify (searched GitHub issues/code, reddit incl. `site:reddit.com` — zero hits, IPTV forums, YouTube, vendor site):** the exact M3U add-screen flow; whether there's a **separate EPG URL field** and where it lives; which `#EXTINF` attributes are honored vs ignored (`tvg-id`, `tvg-name`, `tvg-logo`, `group-title`, `tvg-chno`, `tvg-shift`, `catchup`/`catchup-days`/`catchup-source`, `timeshift`); whether it requires `#EXTM3U x-tvg-url`/`url-tvg`; gzip handling; max playlist size. **No public documentation, teardown, or user report covers any of this.**

**Best inference (labeled, do not build on without on-device testing):** the app is XC-first ("advanced Xtream player"), so its M3U parser most plausibly honors the standard attribute set its XC path already consumes — `tvg-id` (EPG join), `tvg-name`, `tvg-logo`, `group-title` (categories) — and EPG most plausibly comes from the playlist header's `x-tvg-url`/`url-tvg` or a separate field. To confirm: drive the actual app or its `/manage-playlists/` web flow and check (a) EPG URL placement, (b) `tvg-chno` handling, (c) catchup attributes.

**Practical consequence for Seth:** Flix Pro's M3U mode is a fallback, not the primary path. Since our bridge already speaks Xtream (which Flix Pro handles fully, EPG included), there is **no reason to use Flix Pro's M3U mode** — Xtream login gives strictly more (VOD, series, catchup flags, three EPG surfaces). M3U mode only matters if Seth ever points Flix Pro at a *different* provider that lacks XC.

### 1.4 Stalker Portal mode: "Coming soon"

The listing advertises it, but no version of `flix.pro.tv` is known to have shipped it (last update May 2025). If it ever ships, §4 below documents exactly what the bridge would need to serve. TiviMate, OTT Navigator, and STBEmu already speak it — so bridge-side Stalker support would benefit those apps immediately, Flix Pro eventually.

### 1.5 Feature matrix per input format (Flix Pro `flix.pro.tv`)

| Feature | Xtream API login | M3U playlist mode | Stalker (if shipped) |
|---|---|---|---|
| Live TV | ✅ full | ✅ (parser-dependent) | ✅ expected |
| EPG | ✅ 3 surfaces (JSON ×2 + xmltv.php) | ⚠️ header `x-tvg-url` or manual field (unverified) | ✅ per-channel JSON EPG |
| VOD / Series | ✅ | ❌ (M3U has no VOD/series model) | ✅ (separate actions) |
| Catchup/timeshift | ✅ via `tv_archive` flags | ⚠️ via `catchup=` attrs (unverified) | ✅ `enable_tv_archive` |
| Favorites | ✅ app-local | ✅ app-local | ✅ app-local |
| Resume/seek (VOD) | ✅ via HTTP Range | n/a | ✅ |

---

## 2. XC M3U — the `get.php?type=m3u_plus` variant, exactly

This is the M3U that Xtream/XUI panels generate for "M3U playlist" users. Our bridge does not yet offer it (§7 recommends adding it — it's cheap).

### 2.1 Request

```
GET /get.php?username={u}&password={p}&type=m3u_plus&output=ts
```

- `type`: `m3u_plus` (default, full attributes) or `m3u` (**simple list, no tvg attributes** — verified via [xtreampulsar changelog](https://github.com/dearbulut/xtreampulsar)). Params documented at [iptv-clone docs](https://github.com/gitgonewild/iptv-clone/blob/HEAD/docs/XTREAM_API.md).
- `output`: `ts` (default) or `m3u8` — changes the **stream-URL file extension**. Also seen in the wild: `hls`, `mpegts` ([KroozTV templates](https://krooztv.com/billing/knowledgebase/11/Krooz-IPTV---Krooz-Tv.html?language=hungarian)); `rtmp` appears in some panels' `allowed_output_formats`.
- One file contains **live + VOD + series** (consumers classify them out of it).

### 2.2 `#EXTM3U` header

Reimplementation docs show:
```
#EXTM3U url-tvg="http://host/xmltv.php?username=user&password=pass"
```
— [iptv-clone](https://github.com/gitgonewild/iptv-clone/blob/HEAD/docs/XTREAM_API.md).
**Flag:** whether *stock* Xtream/XUI emits `url-tvg` is unverified from a primary source; it varies by fork. TiviMate's setup offers manual EPG-URL entry "if the EPG URL doesn't import automatically" ([guide](https://medium.com/@elliegillnorth/how-to-install-tivimate-player-on-firestick-android-tv-google-tv-1a8fcf3aee70)), implying the header is not universal. **Bridge guidance: emit both `url-tvg` and `x-tvg-url` pointing at our `xmltv.php` — harmless when honored, ignored otherwise — but always document the EPG URL separately.**

### 2.3 `#EXTINF` lines (live, `m3u_plus`)

Exact observed attribute set and order:
```
#EXTINF:-1 tvg-id="channel-1" tvg-name="Example Channel" tvg-logo="http://example.com/logo.png" group-title="Sports",Example Channel
```
— [iptv-clone](https://github.com/gitgonewild/iptv-clone/blob/HEAD/docs/XTREAM_API.md)

Mapping (confirmed in code by [iptv-proxy's `xtreamGenerateM3u`](https://github.com/alvarolobato/iptv-proxy/blob/HEAD/pkg/server/xtreamHandles.go), `Length: -1`):

| M3U attribute | XC source field |
|---|---|
| `tvg-id` | `epg_channel_id` |
| `tvg-name` | channel name |
| `tvg-logo` | `stream_icon` |
| `group-title` | category name |
| duration | always `-1` for live |

With `type=m3u` (not plus): `#EXTINF:-1,Channel Name` — attributes stripped.

**Attributes stock XC `get.php` does NOT emit** (no positive evidence found):
- No `catchup` / `catchup-days` / `catchup-source` / `timeshift` / `tvg-shift`. XC exposes archive via JSON instead: `tv_archive` (0/1) + `tv_archive_duration` (days) in `get_live_streams` ([sohva-tv spec](https://github.com/macstered/sohva-tv/blob/HEAD/docs/rebuild/specs/22-catchup-and-reminders.md)). Catchup playback uses `/timeshift/{u}/{p}/{duration}/{start}/{stream_id}.ts` ([InfiniTV PR](https://github.com/infinitel8p/Extreme-InfiniTV/pull/106)).
- **No `#EXTVLCOPT` / `#KODIPROP` lines.** These are *provider-crafted* per-stream directives (custom UA, DRM license data) that tools like xTeVe pass through verbatim — not panel-generated ([xteve-reborn release notes](https://github.com/theantipopau/xteve-reborn/blob/HEAD/tools/release/notes-v3.0.4.md)).
- Panel-specific exceptions (do not mistake for stock): some forks emit `tvg-type="movie"` / `tvg-type="series"` ([lumora sample](https://github.com/disclosurez/lumora/issues/1); recognized by [tuliprox](https://github.com/euzu/tuliprox/pull/830)); XtreamPulsar emits `catchup-source`/`tv-archive` attributes ([xtreampulsar](https://github.com/dearbulut/xtreampulsar)).

### 2.4 Stream URL lines

```
Live:    http://host:port/live/{username}/{password}/{stream_id}.ts      (or .m3u8)
VOD:     http://host:port/movie/{username}/{password}/{stream_id}.{container_extension}
Series:  http://host:port/series/{username}/{password}/{episode_id}.{container_extension}
```
Verified by [go.xtream-codes](https://github.com/tellytv/go.xtream-codes/blob/master/xtream-codes.go); same in [zap-tv PRD](https://github.com/arobce/zap-tv/blob/HEAD/IPTV-Player-PRD.md), [iptv-proxy](https://github.com/wireshj/iptv-proxy). Extension-less `/live/u/p/id` also works (302) per [iptv-clone](https://github.com/gitgonewild/iptv-clone/blob/HEAD/docs/XTREAM_API.md).

### 2.5 VOD / series entries

- **Duration: not real seconds.** Commonly `-1` (the norm — "Many IPTV providers mark movies/episodes as #EXTINF:-1", [vodstrm#9](https://github.com/xaque8787/vodstrm/issues/9)) or `0` on some panels. Never trust it as runtime.
- VOD: `group-title` = VOD category, `tvg-logo` = poster, URL under `/movie/…`.
- Series: one entry **per episode** (`Show Name S01 E01`), URL under `/series/…` with the *episode* id.
- EPG is **not** embedded; guide comes from separate `GET /xmltv.php?username=X&password=Y`, joined on `tvg-id` ↔ `<channel id>`.

### 2.6 Serving notes

- `Content-Type` varies by panel (`application/octet-stream` is common — iptv-proxy sets exactly that; others use `audio/x-mpegurl`).
- Line endings/encoding of stock output: unverified. General M3U convention: **CRLF + UTF-8 without BOM** ([iptv-org convention](https://github.com/hvs3yn/iptv/blob/HEAD/docs/playlists.md)).

### 2.7 How it differs from a "plain" M3U

A hand-written M3U (like our current `kavitv.m3u`) and XC's `m3u_plus` share syntax, but: XC's is **credential-bound** (every URL embeds username/password), **multi-section** (live+VOD+series in one file), uses **`epg_channel_id`** as `tvg-id` (not arbitrary strings), links EPG via header `url-tvg` → `xmltv.php`, and marks durations `-1`/`0` rather than real runtimes. A plain M3U is anonymous, single-purpose, and human-curated.

---

## 3. M3U vs M3U8 — what's actually different

**Byte-level: exactly one thing — declared character encoding.** `.m3u` = the 1990s Winamp-era format with *no* encoding specified (in practice Latin-1/Windows-1252 or writer's choice); `.m3u8` = identical syntax with the promise "these bytes are UTF-8" (the **8** is UTF-8, not a version number). Syntax, tags, parsing: identical. Sources: [m3uplayer.app](https://m3uplayer.app/m3u-file-format/m3u8-vs-m3u), [iptvowl](https://iptvowl.com/).

**What the HLS spec actually says** ([RFC 8216 §4.1](https://www.rfc-editor.org/info/rfc8216/)): playlists MUST be UTF-8 and **MUST NOT contain a BOM** ("clients SHOULD fail to parse Playlists that contain a BOM or do not parse as UTF-8"). A playlist is identified by path ending `.m3u8` **or** `.m3u`, or by `Content-Type: application/vnd.apple.mpegurl` / `audio/mpegurl` — **the spec treats both extensions as valid HLS playlist identifiers**; the extension alone never disqualifies a playlist.

**When it matters for an IPTV channel-list playlist** (not an HLS media playlist):
1. **Non-ASCII channel names** (Arabic, Cyrillic, CJK, accented Latin): serve UTF-8 regardless of extension — and **without BOM** (some IPTV players reject a BOM; RFC forbids it for HLS).
2. **Players sniff content, not just extension.** Real-world proof: a provider served an extended-M3U channel list (no `#EXT-X-*` tags) at a `.m3u8` URL with `Content-Type: audio/mpegurl` — the client had to detect "not actually HLS" from content ([iptv-smarttv-player ARCHITECTURE](https://github.com/map4uk14/iptv-smarttv-player/blob/HEAD/ARCHITECTURE.md)). Conversely, players that key *stream handling* off the URL (treating an entry ending `.m3u8` as an HLS manifest) do so per **entry URL**, not per playlist extension.
3. **Per player — no verified case of any major player refusing a channel list over `.m3u` vs `.m3u8` alone:** VLC (liberal sniffer), TiviMate (accepts either; EPG auto-import reads header when present), IPTV Smarters (no extension sensitivity documented), Emby M3U tuner (any URL; uses `tvg-id`/`tvg-name`/`tvg-logo`/`group-title` per entry), Kodi IPTV Simple Client (parses extended M3U either way; honors `#KODIPROP`/`#EXTVLCOPT` per-entry directives independent of playlist extension).

**Do not conflate** the playlist file's extension with the *stream* URLs inside it: a list named `.m3u8` whose entries point at `.ts` URLs is not an HLS manifest, and renaming it doesn't make it one ([101convert](https://www.101convert.com/convert/m3u-to-m3u8)).

**Serving recommendation for our bridge:** UTF-8, no BOM, LF or CRLF, either extension (`.m3u` is the safer default for "channel list" semantics; `.m3u8` is fine too and signals UTF-8). What actually breaks players: a BOM, wrong/missing charset on non-ASCII names, or entry URLs whose extension misleads stream-type sniffing — not the playlist's own extension.

---

## 4. Stalker Portal / Ministra — the third protocol

### 4.1 Background

"Stalker Portal" is the client protocol of **Stalker Middleware**, Infomir's free/open-source IPTV middleware (commercialized as **Ministra TV Platform**). Clients: MAG set-top boxes and emulating apps (STBEmu, OTT Navigator, TiviMate, IPTV Smarters, PureFusionIPTV). Identity is a **MAC address**, not username/password. Sources: [stalkerhek wiki](https://github.com/CrazeeGhost/stalkerhek/wiki), [PureFusionIPTV docs](https://github.com/eliminater74/purefusioniptv_documentation/blob/HEAD/STALKER_PORTAL.md).

**Important distinction:** Infomir's public [REST API v1 docs](https://wiki.infomir.eu/eng/ministra-tv-platform/ministra-setup-guide/rest-api-v1) (`stalker_portal/api/v1/...`, OAuth2) are the **operator-side** API (billing/STB management) — **not** what STB apps speak. Apps use the legacy **"JS API"** (`type=`/`action=` JSON endpoint). "Stalker API" = the JS API below.

### 4.2 Base endpoint (no single canonical path — clients probe)

All actions are GETs to one PHP endpoint; real clients (TiviMate, OTT Navigator) **probe** candidate paths at setup:

- `/stalker_portal/server/load.php` (classic install)
- `/portal.php` (also `/c/portal.php`; common on resold panels)
- `/stalker_portal/c/portal.php` (some Ministra deployments)

Every request appends `JsHttpRequest=1-xml` (transport marker; response is still JSON), and every response wraps as `{"js": <payload>}`. Sources: [blammytv stalker docs](https://github.com/adam-edword/blammytv/blob/HEAD/docs/stalker-implementation.md) (verified against server source `server/load.php`), [stalkerhek](https://github.com/kidpoleon/stalkerhek).

### 4.3 Request headers (every call)

```
User-Agent: Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3
Referer:    http://HOST/stalker_portal/c/
Cookie:     mac=<url-encoded MAC>; stb_lang=en; timezone=Europe/London
X-User-Agent: Model: MAG254; Link: WiFi
Authorization: Bearer <token>          (omit on handshake; required after)
```

MAC in cookie is URL-encoded (`00%3A1A%3A79%3A…`; Infomir OUIs conventionally `00:1A:79:`). Some portals reject browser UAs — a MAG-looking UA is required. `timezone` should be a real IANA zone (affects EPG timestamps). Strict portals may demand `sn`/`device_id`/`signature` — rare. Sources: [blammytv](https://github.com/adam-edword/blammytv/blob/HEAD/docs/stalker-implementation.md), [PureFusionIPTV](https://github.com/eliminater74/purefusioniptv_documentation/blob/HEAD/STALKER_PORTAL.md).

### 4.4 Auth flow

**Handshake** (no `Authorization` yet):
```
GET {base}?type=stb&action=handshake&token=&JsHttpRequest=1-xml
→ { "js": { "token": "C00F7332ED272F00D5FD3E82F567A282", "random": "…" } }
```
All subsequent requests: `Authorization: Bearer <token>`.

**get_profile** (register device):
```
GET {base}?type=stb&action=get_profile&hd=1&ver=…&stb_type=MAG254&…&JsHttpRequest=1-xml
→ { "js": { "id":…, "name":…, "blocked":0, "account_balance":…, … } }
```
Blocked/expired or HTTP 4xx = auth failed. **Variant:** minority of portals layer login/password: `type=stb&action=do_auth&login=<u>&password=<p>` after handshake.

**Keepalive:** tokens expire (~1h, community-reported, exact TTL unverified); sessions kept alive via watchdog `type=watchdog&action=get_events` polled ~every 88s. Robust clients re-handshake lazily on 401/403.

### 4.5 Live TV: categories + channels

```
GET {base}?type=itv&action=get_genres&JsHttpRequest=1-xml
→ { "js": [ { "id":…, "title":…, "alias":…, … } ] }

GET {base}?type=itv&action=get_all_channels&JsHttpRequest=1-xml
→ { "js": { "data": [ { "id", "name", "number", "cmd", "xmltv_id",
                        "logo", "tv_genre_id", "status", "hd",
                        "enable_tv_archive", … } ] } }
```

Confirmed fields from `itv.class.php getAllChannels()` (verified against open-source server fork). **Fallback — paginated per genre** (mandatory; some portals ignore `get_all_channels`):
```
GET {base}?type=itv&action=get_ordered_list&genre=<id>&p=<page>&fav=0&sortby=number&JsHttpRequest=1-xml
→ { "js": { "total_items":…, "max_page_items":…, "data":[ … ] } }
```
Pagination is 0-based on some forks, 1-based on others. Sources: [blammytv](https://github.com/adam-edword/blammytv/blob/HEAD/docs/stalker-implementation.md), [iptvnator](https://github.com/4gray/iptvnator/blob/HEAD/docs/architecture/stalker-portal.md), [stalkerhek CHANGELOG](https://github.com/kidpoleon/stalkerhek/blob/HEAD/CHANGELOG.md).

### 4.6 Stream resolution: `create_link` (no Xtream analogue — read carefully)

Channel rows contain **no playable URL** — only an opaque `cmd`. At play time:
```
GET {base}?type=itv&action=create_link&cmd=<url-encoded channel cmd>&JsHttpRequest=1-xml
→ { "js": { "cmd": "ffmpeg http://host:port/ch/<id>?play_token=…", … } }
```

**Critical parsing rule:** returned `js.cmd` may be prefixed with a "solution" word (`ffmpeg`, `ffrt`, `auto`, …) + space + the real `http(s)://…` URL. Strip rule: take the substring from the first occurrence of `http` (or the whitespace token starting with `http://`/`https://`). The resolved URL typically carries a **`play_token`** and is **short-lived / effectively single-use** — never persist; re-resolve every play. Always call `create_link` even if the raw `cmd` looks like a URL (it registers the play and returns the load-balanced/secure variant). Verified against `itv.class.php createLink()` ([blammytv](https://github.com/adam-edword/blammytv/blob/HEAD/docs/stalker-implementation.md)); also [iptv-manager-pro](https://github.com/phantomlimb717/iptv-manager-pro/blob/HEAD/Stalker-Portal-Playback-Features.md), [PureFusionIPTV](https://github.com/eliminater74/purefusioniptv_documentation/blob/HEAD/STALKER_PORTAL.md).

### 4.7 EPG (per-channel JSON — no bulk XMLTV)

- **Short EPG (now+next):** `GET {base}?type=itv&action=get_short_epg&ch_id=<id>&size=10&JsHttpRequest=1-xml` → `js` = array of `{ id, ch_id, name, descr, time, time_to, start_timestamp, stop_timestamp, duration }` (Unix seconds).
- **Window EPG (guide fill):** `GET {base}?type=itv&action=get_epg_info&period=<n>&JsHttpRequest=1-xml` → `js` = **map keyed by `ch_id`**, each an array of programmes (adds `category`, `director`, `actor`). Closest thing to a bulk fetch; TiviMate consumes it natively ([stalker-portal-proxy](https://github.com/selva005/stalker-portal-proxy) confirms).

### 4.8 VOD / Series (least standardized area)

- Categories: `type=vod&action=get_categories` / `type=series&action=get_categories` (⚠️ some portals split differently — clients fall back `type=vod` → `type=video`).
- Listing: `type=vod&action=get_ordered_list&category=<id>&p=<page>&sortby=added` → `total_items`/`max_page_items`/`data`; item fields `id`, `name`, `cmd`, `series` (non-empty ⇒ series), `screenshot_uri`, `rating_imdb`.
- Seasons/episodes: `get_ordered_list` with `movie_id=<series_id>`, then `movie_id=<series_id>&season_id=<id>` (some forks use `type=vod` for both, some `type=series`).
- Playback: `type=vod&action=create_link&cmd=<cmd>` — **`create_link` must use the item's own type** (`itv` vs `vod`); hardcoded `type=itv` returns nothing for movies.
- Account: `type=account_info&action=get_main_info`.

Could not verify: `itv.get_all_fav` shape (exists in some forks; skip in any implementation).

### 4.9 Minimal API surface for our bridge (inbound Stalker, live TV + EPG)

**Yes, feasible** — precedent: [iptvproxystream](https://github.com/Abhaikumar007/iptvproxystream) (FastAPI) serves a Stalker endpoint alongside Xtream and M3U; [stalker-portal-proxy](https://github.com/selva005/stalker-portal-proxy) is a full Stalker session proxy.

| # | Request | Response |
|---|---|---|
| 1 | `GET /portal.php` (+ accept `/c/portal.php`, `/stalker_portal/server/load.php`) `type=stb&action=handshake` | `{"js":{"token":"<random-hex>"}}` |
| 2 | `type=stb&action=get_profile` | `{"js":{"id":1,"name":"KaviTV","blocked":0}}` |
| 3 | `type=itv&action=get_genres` | `{"js":[{"id":"<cat>","title":"<name>"}]}` from XC categories |
| 4 | `type=itv&action=get_all_channels` | `{"js":{"data":[{id,name,number,cmd,xmltv_id,logo,tv_genre_id}]}}` — `cmd` can be `ffmpeg <bridge-stream-url>` or an opaque token |
| 5 | `type=itv&action=get_ordered_list` | same rows paginated (`total_items`, `max_page_items`, `data`) — some clients never call `get_all_channels` |
| 6 | `type=itv&action=create_link&cmd=…` | `{"js":{"cmd":"ffmpeg <actual stream url>"}}` — bridge URLs are stable, so just return them |
| 7 | `type=itv&action=get_short_epg` / `get_epg_info&period=` | programme arrays / ch_id-keyed map from `timeline.json` |

Auth can be trivial server-side: accept any MAC cookie, issue a static token, accept any `Authorization: Bearer`, never expire — this is a trusted local bridge, not a provider panel. Ignore `JsHttpRequest`; always wrap in `{"js": …}`. VOD/series actions can return empty lists.

**Effort: ~200–400 lines, a day or less**, plus testing against a real client (OTT Navigator, STBEmu, TiviMate — TiviMate's bulk `get_epg_info` call is a known finicky spot). **Caveat:** no single spec exists — behavior is "whatever real portals do," so testing against the actual client matters more than docs. **Strategic note:** Emby does not speak Stalker (it consumes M3U/XMLTV tuners), so this is purely for external players — Flix Pro if/when "Coming soon" ships, plus TiviMate/OTT Navigator today.

---

## 5. Other playlist formats — brief survey

| Format | What | Who consumes it (2026) | Verdict for Seth |
|---|---|---|---|
| **XSPF** (XML Shareable Playlist, Xiph, 2005) | XML playlist: `<playlist><trackList><track><location>…` | VLC, Audacious, foobar2000; legacy Android "IPTV Core" family. **Dead as an IPTV format** — no modern IPTV app takes it. | Ignore |
| **PLS** (SHOUTcast/Winamp INI-style) | `[playlist]` / `File1=` / `Title1=` / `Length1=` | VLC, Winamp, foobar2000 — internet-radio players, not IPTV. Hobby players bundle readers for completeness. | Ignore |
| **Enigma2 bouquets** | `/etc/enigma2/userbouquet.*.tv`: `#SERVICE 4097:…:<urlencoded-url>` + `#DESCRIPTION` | Enigma2 Linux satellite boxes (Vu+, Dreambox) + PC generators (e2m3u2bouquet, JediMakerXtream). EPG must be manually mapped (no real service refs for IPTV). | Ignore unless he buys a satellite box |
| **ASX / .cue** | Windows Media / CD-image playlists | Completeness readers in hobby players only | Ignore |
| **JTV** (EPG, not playlist) | Legacy binary EPG (`JTV.zip`: `.pdt`+`.ndx` per channel) | Legacy Dune HD players, old RU/UA stacks | Ignore — see §6.2 |

**Other things that are NOT playlist formats** (commonly confused): **SAT>IP** (DVB-over-IP LAN tuner sharing — irrelevant), **tokenized/cookie HLS** (stream-auth mechanism, not a format; our relay already abstracts it), **"Xtream Stalker hybrid"** (no such standard — what exists are multi-protocol proxies like [stalkerhek](https://github.com/kidpoleon/stalkerhek) and [iptvproxystream](https://github.com/Abhaikumar007/iptvproxystream) serving both from one catalog).

**Bottom line:** in 2025–2026 the formats that matter are **M3U, Xtream Codes, Stalker Portal** — everything else is legacy or out of scope.

---

## 6. EPG formats compared

### 6.1 XMLTV — deep specifics (verified against the DTD)

Authoritative: [XMLTV DTD](https://raw.githubusercontent.com/XMLTV/xmltv/master/xmltv.dtd) (repo [`XMLTV/xmltv`](https://github.com/XMLTV/xmltv)).

- **Root:** `<!ELEMENT tv (channel*, programme*)>`; all root attrs optional (`generator-info-name`, `source-info-url`, …).
- **`<channel>`:** `id` **#REQUIRED**; minimum valid = one `<display-name>`.
- **`<programme>`:** `start` + `channel` **#REQUIRED**; `stop` technically optional (#IMPLIED) but always emit it. Child order per DTD: `title+, sub-title*, desc*, credits?, date?, category*, keyword*, language?, orig-language?, length?, icon*, url*, country*, episode-num*, video?, audio?, previously-shown?, premiere?, last-chance?, new?, subtitles*, rating*, star-rating*, review*, image*`.

**Minimum per consumer:**

| Consumer | Channel join key | Min. programme |
|---|---|---|
| Emby | M3U `tvg-id` == `<channel id>` (exact) | `start`/`stop`, `channel`, `<title>` |
| TiviMate | `tvg-id` → `<channel id>` (case-sensitive), fallback `tvg-name`, last-resort display-name text match | same |
| Kodi (IPTV Simple) | `tvg-id` → channel id | same |
| Plex DVR | manual channel mapping in UI | same |
| IPTV Smarters | `tvg-id` → channel id (or XC API) | same |

**Optional children that matter:**
- `<desc>` — all consumers display it.
- `<category>` — Emby/Jellyfin map to Genres (and IsMovie/IsSports/IsNews/IsKids flags); TiviMate parses but ignores for coloring. No standard vocabulary.
- programme-level `<icon src>` — Emby ingests programme icons; TiviMate "Prefer logos from EPG" setting uses channel icons.
- `<date>` (`YYYYMMDD`) — feeds Emby ProductionYear.
- **`<episode-num system="xmltv_ns">`** — the useful one. **Zero-based**: `"1.4."` = season 2, episode 5; `"1.4/13."` adds totals. Emby parsers handle it ([emby.fastiptv](https://github.com/danielalmering/emby.fastiptv/blob/HEAD/CLAUDE.md)). `system="onscreen"` is cosmetic free text. Put `xmltv_ns` **first** if emitting multiple (some parsers read only the first).
- `<previously-shown/>` — Emby flags "Repeat"; feeds new-vs-repeat recording rules. Cheap; recommended.
- `<premiere/>`, `<last-chance/>`, `<new/>` — Emby Premiere/Finale badges.
- `<rating system="…"><value>TV-MA</value></rating>` — maps to Emby `OfficialRating` + parental controls. ⚠️ Which `system` string Emby prefers (`VCHIP` vs `MPAA` vs `TVPG`) is reported-working but not officially documented.
- `<credits>` (director/actor/…) — Emby imports people; TiviMate ignores.
- `<star-rating>`, `<subtitles>` — largely ignored by IPTV apps; harmless.

**Timezone:** DTD format `YYYYMMDDhhmmss` + space + offset; no-timezone ⇒ UTC *per the DTD*, but not per every parser. **`Z` is NOT in the DTD** — always emit explicit `+0000`, never `Z`, never bare timestamps (bare risks server-local interpretation; TiviMate lists "wrong time zone" as a top shifted-guide cause).

**Multiple `<display-name>`:** legal and intended — DTD: *"Names listed earlier are considered 'more canonical'"*. TiviMate's last-resort fallback matches against `<display-name>` entries (plural), so extra aliases help, never hurt. Emby ignores display-name for matching. Safe to include aliases, canonical first.

**`<lcn>`** (logical channel number): **NOT in the DTD** — de-facto extension used by [iptv-manager](https://github.com/dreed47/iptv-manager). Emby uses M3U `tvg-chno`/channel mapping instead. Non-standard; use knowingly.

**File size / limits:** no official Emby XMLTV day-cap found. Community feeds Emby **14-day XMLTV files** routinely ([emby.media](https://emby.media/community/topic/39378-does-xmltv-work/)); cost is import time (~15 min nightly for 50 channels). Emby ingests whatever window the file contains. Ecosystem rule of thumb: TiviMate 3–7 days, iptv-org/epg several days, Xtream panels 2–7 days. **72h is comfortably inside every consumer's happy zone.**

### 6.2 JTV — verdict: do not generate

"JTV 3.x TV Program Data" — legacy **binary** EPG as `JTV.zip` with per-channel `.pdt` (program names) + `.ndx` (12-byte records: FILETIME timestamps + offsets) pairs. Little-endian, undefined text encoding (win-1251 for Cyrillic), no genres/icons/episode numbers — strictly less metadata than XMLTV. Remaining users: legacy Dune HD players, old RU/UA stacks. **None of Seth's consumers (Emby, Flix Pro, TiviMate, Kodi, Smarters) read JTV.** ([spec via kamleong](https://github.com/kamleong/kamleong.github.io); [converter xmltv2jtv](https://code.google.com/archive/p/xmltv2jtv/wikis/JTVFormat.wiki))

### 6.3 Other EPG transports

- **Xtream `xmltv.php`:** plain XMLTV, same format; channel `id` == stream's `epg_channel_id` ([xc_vm docs](https://github.com/marsiratv/xc_vm/blob/HEAD/docs/en/api/xtreamcodes_api.md)). "epg.xml" on self-hosted bridges (xTeVe etc.) = same XMLTV, unauthenticated. No format difference.
- **Gzip'd XMLTV (`.xml.gz`):** TiviMate decompresses `.gz`/`.zip` natively; Kodi accepts `.xml.gz`; Emby `.gz` support is community-reported, **not officially documented**. At 3 channels / 72h the file is tiny — skip gzip.
- **JSON EPG APIs** (`get_short_epg`, `get_simple_data_table`): no standard; de-facto Xtream shape `{"epg_listings":[…]}` with `start_timestamp`/`stop_timestamp` and often base64 titles (our bridge already does this).
- **EIT embedded in MPEG-TS:** PID `0x12`, needs TDT/TOT + ISO-6937/UTF-8 signalling; **ffmpeg cannot generate EIT from XMLTV** (needs tsduck/opencaster/tvheadend or hand-rolled sections); Emby/Flix/TiviMate don't parse EIT from HTTP IPTV streams anyway. Skip.

### 6.4 One XMLTV for Emby + Flix Pro? **Yes.**

**The entire trick: the channel `id` string must be byte-identical in all three places** — M3U `tvg-id` ↔ XMLTV `<channel id>` ↔ XC `epg_channel_id`. Checked for conflicts, none material:

- **Window length:** no "Emby max 72h" cap exists in any doc; 14-day files work. Flix Pro caches whatever `xmltv.php` returns.
- **Icons:** both accept plain `https://` URLs.
- **Language elements** (`<title lang="en">`): inert for both.
- **Extra metadata** (`<category>`, `<episode-num system="xmltv_ns">`, `<previously-shown/>`, programme `<icon>`): Emby consumes; Flix Pro's parser skips unknown elements gracefully. Pure upside.

**Recommended XMLTV shape (serves both):**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<tv generator-info-name="KaviTV/generate.py" date="20261004230000 +0000">
  <channel id="kavitv.horror">
    <display-name lang="en">KaviTV Horror</display-name>
    <display-name>Horror</display-name>
    <icon src="https://…/logo-horror.jpg" width="512" height="512"/>
  </channel>
  <programme start="20261005000000 +0000" stop="20261005013000 +0000" channel="kavitv.horror">
    <title lang="en">Night of the Living Dead</title>
    <desc lang="en">1968 zombie classic…</desc>
    <category lang="en">Horror</category>
    <date>1968</date>
    <episode-num system="xmltv_ns">0.0.</episode-num>
    <previously-shown start="20261004000000 +0000" channel="kavitv.horror"/>
    <rating system="VCHIP"><value>TV-14</value></rating>
  </programme>
</tv>
```

Rules: UTC + explicit `+0000` (never `Z`, never bare); canonical `<display-name>` first; `xmltv_ns` first among episode-nums; identical channel IDs everywhere.

---

## 7. Practical recommendation for Seth — ranked by effort vs benefit

Current state: Emby (M3U tuner + XMLTV) ✅ · XC bridge (player_api + `/live/` + EPG + `xmltv.php`) ✅ · `timeline.json` single source of truth ✅

| # | Action | Effort | Benefit | Notes |
|---|---|---|---|---|
| 1 | **Add `get.php?type=m3u_plus&output=ts`** to the bridge | ~1–2 hrs | **High** | Unlocks every M3U-only app (VLC debugging, TiviMate M3U mode, Kodi, Smarters M3U login) against the *same* catalog + credentials. Emit header `url-tvg`→`xmltv.php`, `tvg-id`=`epg_channel_id`, `tvg-name`, `tvg-logo`, `group-title`, duration `-1`, live+VOD+series URLs per §2. UTF-8 no BOM. |
| 2 | **Enrich the XMLTV** per §6.4 | ~1 hr | **Medium** | Add `<category>`, `<episode-num system="xmltv_ns">` (first), `<previously-shown/>`, programme `<desc>` — Emby consumes all of it; zero risk to Flix Pro. One builder change benefits both. |
| 3 | **Inbound Stalker Portal** (§4.9) | ~1 day | **Medium** (grows if Flix Pro ships it) | One route + ~8 actions + handshake/profile stubs. Immediately useful for TiviMate/OTT Navigator/Stalker-capable apps; Flix Pro "Coming soon" makes it future-proof. Test against a real client — docs < behavior. |
| 4 | **`.ts` + `.m3u8` for `/live/`** | ~30 min | **Low–Medium** | flixpro.md already recommends serving both and advertising both in `allowed_output_formats`. Our relay emits TS; the `.m3u8` variant can re-wrap or 302 to the same bytes — decide once, document in `allowed_output_formats` exactly what's served. |
| 5 | **Flix Pro M3U-mode testing** | on-device session | **Low** | Only matters if Seth ever uses a non-XC provider in Flix Pro. XC login already gives strictly more. Defer until needed; the open questions (§1.3) need the actual app, not more research. |

**Explicitly not recommended:** JTV generation (no consumer), EIT injection (no consumer parses it; ffmpeg can't make it), XSPF/PLS/Enigma2 (legacy/niche, zero overlap with Seth's stack), gzip XMLTV (file too small to matter), `catchup=` M3U attributes (no archive exists; XC JSON flags are the correct mechanism).

**The one-line architecture:** `timeline.json` → `generate.py` → {Emby M3U + Emby XMLTV} and bridge → {`player_api.php`, `get.php`, `xmltv.php`, (future) Stalker} — every format rendered from the same slots, drift impossible in every direction.

---

## Sources (by section)

**§1 Flix Pro:** [APKPure flix.pro.tv](https://apkpure.com/flix-pro-player-iptv/flix.pro.tv) · [AppBrain (Edgecode)](https://www.Appbrain.Com/app/flix-pro-player-iptv/flix.pro.tv) · [AppBrain (Logic Titans — the other app)](https://www.appbrain.com/app/flix-pro-player/flix.pro.player) · [chrome-stats](https://chrome-stats.com/d/flix.pro.tv) · [urlscan flixproplayer.com](https://urlscan.io/result/5d7228b7-cbd3-4fa0-88de-afba890e8d2c/) · full Xtream behavior: `flixpro.md` in this directory
**§2 XC M3U:** [iptv-clone XTREAM_API](https://github.com/gitgonewild/iptv-clone/blob/HEAD/docs/XTREAM_API.md) · [xtreampulsar](https://github.com/dearbulut/xtreampulsar) · [iptv-proxy xtreamHandles.go](https://github.com/alvarolobato/iptv-proxy/blob/HEAD/pkg/server/xtreamHandles.go) · [go.xtream-codes](https://github.com/tellytv/go.xtream-codes/blob/master/xtream-codes.go) · [KroozTV templates](https://krooztv.com/billing/knowledgebase/11/Krooz-IPTV---Krooz-Tv.html?language=hungarian) · [xteve-reborn v3.0.4 notes](https://github.com/theantipopau/xteve-reborn/blob/HEAD/tools/release/notes-v3.0.4.md) · [lumora#1](https://github.com/disclosurez/lumora/issues/1) · [tuliprox#830](https://github.com/euzu/tuliprox/pull/830) · [vodstrm#9](https://github.com/xaque8787/vodstrm/issues/9) · [sohva-tv catchup spec](https://github.com/macstered/sohva-tv/blob/HEAD/docs/rebuild/specs/22-catchup-and-reminders.md) · [InfiniTV#106](https://github.com/infinitel8p/Extreme-InfiniTV/pull/106) · [iptv-org playlist convention](https://github.com/hvs3yn/iptv/blob/HEAD/docs/playlists.md)
**§3 M3U/M3U8:** [RFC 8216 §4.1](https://www.rfc-editor.org/info/rfc8216/) · [m3uplayer.app](https://m3uplayer.app/m3u-file-format/m3u8-vs-m3u) · [file-extension.info](https://www.file-extension.info/conversion/m3u-to-m3u8) · [iptv-smarttv-player ARCHITECTURE](https://github.com/map4uk14/iptv-smarttv-player/blob/HEAD/ARCHITECTURE.md) · [101convert](https://www.101convert.com/convert/m3u-to-m3u8)
**§4 Stalker:** [stalkerhek wiki](https://github.com/CrazeeGhost/stalkerhek/wiki) · [PureFusionIPTV STALKER_PORTAL](https://github.com/eliminater74/purefusioniptv_documentation/blob/HEAD/STALKER_PORTAL.md) · [blammytv stalker-implementation](https://github.com/adam-edword/blammytv/blob/HEAD/docs/stalker-implementation.md) · [stalkerhek](https://github.com/kidpoleon/stalkerhek) · [iptv-manager-pro KB](https://github.com/phantomlimb717/iptv-manager-pro/blob/HEAD/stalker-knowledge-base.md) · [iptv-manager-pro playback](https://github.com/phantomlimb717/iptv-manager-pro/blob/HEAD/Stalker-Portal-Playback-Features.md) · [iptvnator stalker](https://github.com/4gray/iptvnator/blob/HEAD/docs/architecture/stalker-portal.md) · [stalker-portal-proxy](https://github.com/selva005/stalker-portal-proxy) · [stalker-portal-proxy VOD spec](https://github.com/selva005/stalker-portal-proxy/blob/HEAD/docs/superpowers/specs/2026-07-14-vod-series-support-design.md) · [iptvproxystream](https://github.com/Abhaikumar007/iptvproxystream) · [Infomir REST API v1 (operator-side, NOT the STB protocol)](https://wiki.infomir.eu/eng/ministra-tv-platform/ministra-setup-guide/rest-api-v1) · [TiviGlass comparison](https://tiviglass.com/learn/xtream-stalker-m3u-explained)
**§5 Niche:** [Xiph XSPF](http://fileformats.archiveteam.org/wiki/XML_Sharable_Playlist) · [aiptv.bundle](https://github.com/manfer/aiptv.bundle/blob/HEAD/manfer_aiptv.bundle/README.md) · [playlist notes](https://helpful.knobs-dials.com/index.php/Playlist_file_notes) · [luna_player](https://github.com/diamondstar35/luna_player/commit/ea0e2e0910fe80c7c5bd2d0b71574ddd8c5a87a0) · [e2m3u2bouquet](https://github.com/su1s/e2m3u2bouquet/blob/master/e2m3u2bouquet.py) · [OpenPLi forums](https://forums.openpli.org/topic/96833-epg-for-iptv-channels/)
**§6 EPG:** [XMLTV DTD](https://raw.githubusercontent.com/XMLTV/xmltv/master/xmltv.dtd) · [XMLTV/xmltv](https://github.com/XMLTV/xmltv) · [iptv-org/epg](https://github.com/iptv-org/epg) · [TiviMate EPG fixes](https://tivimateplayer.co.uk/tivimate-epg-not-updating-fixes/) · [fbtv EMBY_SETUP](https://github.com/cbodden/fbtv/blob/HEAD/docs/EMBY_SETUP.md) · [emby.fastiptv CLAUDE.md](https://github.com/danielalmering/emby.fastiptv/blob/HEAD/CLAUDE.md) · [emby.media 39378](https://emby.media/community/topic/39378-does-xmltv-work/) · [emby.media 39111](https://emby.media/community/index.php?/topic/39111-refresh-schedule-data-no-longer-working/) · [xc_vm API docs](https://github.com/marsiratv/xc_vm/blob/HEAD/docs/en/api/xtreamcodes_api.md) · [blipty Xtream API](https://github.com/burggraf/blipty/blob/HEAD/Xtream%20Codes%20API.md) · [arjunze v2 doc](https://github.com/arjunze/xtream-codes-api-v2-doc) · [kamleong JTV](https://github.com/kamleong/kamleong.github.io) · [iptv.example url-tvg](https://github.com/bdaalsar1-bot/iptv.example) · [iptv-manager lcn](https://github.com/dreed47/iptv-manager) · [gjhayes/epg](https://github.com/gjhayes/epg) · [Emby Item Information wiki](https://github.com/MediaBrowser/Emby/wiki/Item-Information)

---

## Honest gaps (what no public source covers)

1. **Flix Pro (`flix.pro.tv`) M3U mode**: EPG field location, honored/ignored `#EXTINF` attributes, `x-tvg-url` requirement, gzip, size limits, catchup support — zero public sources; needs on-device testing or its `/manage-playlists/` web flow.
2. **Stock Xtream/XUI `get.php` exact bytes**: header (bare vs `url-tvg`), line endings, Content-Type, VOD `#EXTINF` duration (`-1` vs `0`) — inferred from reimplementations and samples, not original PHP.
3. **Official Emby XMLTV day-cap / `.xml.gz` support / preferred `<rating system>`**: community-reported, not officially documented.
4. **Infomir's exact token TTL** and strict-portal extra auth fields (`sn`/`device_id`/`signature`): vary by deployment; test against the real client.
