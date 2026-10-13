# KaviBOT connections layer - design (staging)

**Status:** staging only. Not deployed. Production deploy needs Seth's separate per-case approval.
**Ordered by Seth:** 2026-10-13 ~09:32 EDT ("build the layer for other app and site connections").

## Problem

Seth asked KaviBOT to "link to" his music to learn his tastes, the way cloud
assistants connect to accounts. KaviBOT honestly said it can't - it has no
account-connection plumbing. This layer gives it one: a generic framework for
connecting external apps/sites, plus pilots that prove it.

## Design: one framework, many connections

Adding a connection is **declarative config, not new plumbing**:

- `connections.json` holds one entry per connection: name, type, endpoints,
  scopes, capabilities, setup notes.
- Two connector types:
  - `oauth2` - account connections via OAuth 2.0 authorization-code flow with
    PKCE and an ephemeral `127.0.0.1` loopback listener on the PC. One shared
    `oauth2.py` handler serves all OAuth connections.
  - `file_import` - local file drops (export from the app, KaviBOT parses).
    No network, no credentials, no cost. For services whose APIs are paywalled
    or closed but whose apps export data.
- `manager.py` is the single surface the bridge calls:
  `status / connect / disconnect / call / import_file`.
- Capability functions live in one small module per connection (`gcal.py`,
  `apple_music.py`). The framework handles auth, tokens, refresh, and the
  not-connected fallback.

## Secrets (operator-credential invariant - permanent)

- Tokens live in `SecretStore`. On the PC the backend is DPAPI
  (`DPAPISecretBackend`, LocalMachine scope - same boundary as the existing
  `C:\AI\vault`): secrets never leave the PC, never touch logs/git/chat.
- Staging/dev uses `FileSecretBackend` (0600 file). The manager picks the
  backend by platform automatically.
- Token *values* are never logged; `repr`s and audit lines carry names and
  metadata only. `connect` takes the client ID/secret via interactive prompt,
  never as CLI args (args land in shell history/logs).

## Honesty rule

If a connection isn't set up, `call` returns a structured `not_connected`
error telling Seth exactly how to connect - it never invents data. This is
the same bar as the rest of KaviBOT's honesty work.

## Pilots (all free, all read-only)

### 1. Google Calendar (`gcal`, type `oauth2`)

Why: Seth's literal first test prompt was "plan my day" - calendar read
access serves daily use directly. Free Google Cloud project, free Calendar
API, no paywall, no Premium-style gate.

- Scope: `https://www.googleapis.com/auth/calendar.readonly` only.
- Google classifies calendar scopes as **sensitive, not restricted** - no
  CASA security assessment, no paid verification needed for single-user use.
- Client type: **Desktop app**. Google auto-permits loopback
  (`http://127.0.0.1:<ephemeral port>`) redirects for this type - nothing to
  pre-register. PKCE; the issued client secret is non-confidential for
  installed apps but is still vaulted.
- **The 7-day trap (documented, with fix):** Google invalidates refresh
  tokens after 7 days while the OAuth consent screen is in **Testing** mode.
  Fix is free and instant: Audience -> **Publish app** (Testing -> In
  production). Verification review is NOT required for token longevity -
  "in production" and "verified" are separate axes. Publishing needs branding
  fields (homepage + privacy-policy URLs + authorized domain); a minimal
  GitHub Pages site satisfies it. At consent, Seth clicks through the
  one-time "Google hasn't verified this app" warning (Advanced -> Continue).
- Capabilities: `list_events` (time window, default next 7 days),
  `get_event`.

### 2. Apple Music library import (`apple_music`, type `file_import`)

Why: Seth asked for exactly this ("learn about me and my tastes"). A live
API is impossible (see Excluded below), but the desktop apps export the full
library - artists, albums, tracks, play counts, ratings, dates - as XML.
Zero cost, zero network, zero credentials.

- Seth: **File -> Library -> Export Library** -> save `Library.xml`.
  - Mac: Music app. Windows: iTunes (the newer Apple Music app for Windows
    does not document a full-library export; iTunes remains a free download).
- KaviBOT parses it into a **taste profile** (top artists/albums/tracks by
  play count, genre mix, loved tracks, recently played/added, playlist
  inventory) stored as JSON in its knowledge area, plus a one-paragraph
  summary it can speak naturally.
- The XML never leaves the PC; only the derived profile enters KaviBOT.

### 3. Gmail (`gmail`, type `oauth2`)

Why: Seth asked "can we do anything other than calendar while in there" and
picked Gmail + Drive (2026-10-13 ~10:15 EDT). Mail triage and "what did X
say" are core daily-use questions for a personal AI.

- Scope: `https://www.googleapis.com/auth/gmail.readonly` only.
- Honest scope note: Google classifies `gmail.readonly` as a **restricted**
  scope (stricter than calendar's sensitive). For a single-user personal app
  this still works without verification or a CASA assessment - the owner
  clicks through the one-time "Google hasn't verified this app" warning
  (Advanced -> Continue), same as the Calendar pilot. If Google ever tightens
  restricted-scope access for unverified apps, this pilot degrades to a clear
  `auth_failed` error, never silent breakage.
- Capabilities: `search_messages` (query + From/Subject/Date/snippet per
  hit, max 20), `get_message` (full headers + decoded text body, 4000-char
  cap). Bodies are returned to the caller, never logged.

### 4. Google Drive (`drive`, type `oauth2`)

Why: same Seth decision as Gmail. "Find that file" / "what's in my notes"
without leaving the chat.

- Scope: `https://www.googleapis.com/auth/drive.readonly` only
  (**sensitive**, not restricted - same posture as Calendar).
- Capabilities: `list_files` (Drive query syntax, newest-first, max 50),
  `get_file_metadata`, `download_file_text` (text-ish files only,
  200 KB cap, 4000-char return cap; Google Docs/Sheets/Slides auto-export
  to text/csv; binaries refused with a structured `not_text` error and are
  never dumped to chat).

Both new pilots reuse the same Google Cloud project, the same Desktop OAuth
client, and the same consent screen as `gcal` - the phone driver enabled the
Gmail/Drive APIs and added both scopes in the same console session, so there
is nothing extra for Seth to configure. Each still needs its own
`kavibot-connect.py connect <name>` to complete the OAuth loop and vault its
own refresh token.

### 5. iCloud (`icloud`, type `app_password`)

Why: Seth asked "can we add an apple connector too" (2026-10-13 ~10:44 EDT).
The live Apple Music API is excluded (paid Developer Program), but iCloud
Mail/Calendar/Contacts are reachable with plain IMAP/CalDAV/CardDAV - no
developer account, no fee.

- Apple offers **no OAuth for iCloud** - auth is the Apple ID plus an
  **app-specific password** generated at appleid.apple.com (Sign-In and
  Security -> App-Specific Passwords). The Apple ID must have two-factor
  authentication on. The password is vaulted via SecretStore exactly like
  OAuth refresh tokens: pasted once into the PC `connect` prompt, never in
  code/logs/git/chat. Revocable anytime at appleid.apple.com.
- New framework capability: the `app_password` connection type (username +
  vaulted password, no OAuth dance). `connect` prompts for both, then
  verifies with a cheap IMAP login; a rejected password is discarded, never
  kept. `call` routes to the module with the vaulted credentials; a 401 or
  IMAP auth failure surfaces as a structured `auth_failed`, never silence.
- Capabilities: `search_messages` / `get_message` (IMAP, `imap.apple.com:993`,
  From/Subject/Date/snippet, 4000-char body cap, attachments skipped),
  `list_events` (CalDAV REPORT time-range, default next 30 days, standard
  principal -> home-set -> calendar discovery), `list_contacts` (CardDAV,
  name/email/phone only).
- Honest note: this is the one pilot that asks Seth to generate a credential
  himself (Apple's design, not ours) - but it's a 2-minute, free, revocable
  step, and the password never leaves his PC's vault.

## Evaluated and EXCLUDED (do not build)

- **Spotify** - excluded 2026-10-12, confirmed 2026-10-13. Since Feb 2026,
  Spotify requires an **active Premium subscription** for every Development
  Mode app's Web API access. Seth: no Premium. Parked permanently under the
  free-only rule.
- **Apple Music API / MusicKit** - excluded 2026-10-13. Requires paid Apple
  Developer Program membership ($99/yr); a personal Apple Music subscription
  does not grant API access. The XML-import pilot above is the sanctioned
  music-taste path instead.
- **Amazon Music** - CONDITIONAL future connection (2026-10-13 ~09:36 EDT).
  The Amazon Music Web API is in **closed beta**, limited to already-approved
  developers - no public access at any price, and Amazon Music offers no
  library-export feature, so there is no file-based path either. Seth IS an
  Amazon developer, which re-opens the path conditionally: if Amazon enables
  Music API access on his security profile, an adapter can slot in. The
  framework is ready for it (see "Login-with-Amazon readiness" below).
  Gated on Seth confirming Music API access in his Amazon developer console -
  his action item in the handoff doc. Until then: nothing to build.

## Login-with-Amazon readiness

The shared OAuth2 handler already accommodates LWA-style flows with no
rework: a connection spec may declare `api_headers` (e.g.
`{"x-api-key": "conn-amazonmusic-api-key"}` mapping header -> vault
credential ref) and `token_auth` (`"basic"` for client_id:client_secret
basic-auth on the token exchange, as Amazon's token endpoint expects).
When Amazon enables Music scopes on Seth's security profile, the Amazon
Music adapter is one declarative spec + one capability module.

## Where this lands at deploy time (Seth's approval required)

- `staging/connections/*.py` -> `phase2/integrations/` as the implemented
  `oauth2` and `file_import` connector types (both were on the integrations
  README's "Planned" list).
- `connections.json` entries -> appended to `phase2/integrations/registry.json`
  (credential refs by name only, per the existing convention).
- Tool surface (`list_events`, taste-profile query) -> exposed to the bridge
  through the existing tool/capability wiring, read-only (L1) to start, per
  the authorization ladder.
- No changes to `phase2/releases/`, no service restarts, in this staging
  drop. Deploy is a separate Seth-approved step with its own checklist.

## Test strategy

Fully mocked: fake HTTP adapter for OAuth + Google API, real loopback
listener against itself, sample `Library.xml` generated in-test, 0600
file backend on disk. DPAPI backend tested via mocked decrypt (Windows-only
code path). 18 tests, all must pass.
