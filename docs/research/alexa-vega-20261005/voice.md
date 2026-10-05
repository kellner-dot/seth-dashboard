# Alexa / Voice Control for Sideloaded Vega Apps — Savant Research (2026-10-05)

Question: can Seth get "Alexa, open KaviTV", voice pause/play, or custom voice
commands for his sideloaded Vega apps?

## TL;DR

| Want | Sideloaded? | Path |
|---|---|---|
| "Alexa, pause / play / fast forward" (while playing) | ✅ YES | Vega Media Controls (KMC) — local, no cloud needed |
| "Alexa, open KaviTV" | ❌ NO (sideloaded) → ✅ via Live App Testing | Needs Amazon to map ASIN→package; works after LAT |
| "Alexa, watch X on KaviTV" (quick play) | ❌ | Requires commercial catalog integration |
| Custom voice commands ("Alexa, tune horror") | ❌ natively → workaround only | Alexa Routines / middle-man app / custom Alexa skill |
| AlexaManager capability agents | ⚠️ exists, wrong tool | It's for AVS smart-home integrations, not app voice |

## What WORKS for sideloaded apps

### 1. Transport control via Vega Media Controls (KMC) [O]
"Alexa, play / pause / fast forward / rewind / stop / resume" work while the
app is in the foreground playing media. This is a LOCAL media-session
mechanism — no Alexa cloud registry, no catalog, no Appstore needed.

- Apps using the **W3C Media API** get built-in KMC integration: it
  automatically creates the KMC server, publishes states, and handles voice
  transport commands. (Next/Previous excluded.)
- Apps NOT using W3C Media: integrate via the **Vega Media Controls API**.
- WebView apps: set `allowsDefaultMediaControl={true}` and register
  `navigator.mediaSession` action handlers (`play`, `pause`, `seekforward`,
  ...). Alexa commands route to the page's handlers; without handlers WebView
  falls back to default seek behavior.
- Source: https://developer.amazon.com/docs/vega/0.21/content-launcher-overview.html
  ("Voice capabilities in Fire TV apps", updated May 27, 2026) [O, 2026-05-27]
- Source: https://developer.amazon.com/docs/vega/0.23/develop-your-app-with-webview.html
  (mediaSession section) [O]

Code pattern (WebView):
```js
navigator.mediaSession.setActionHandler('pause', () => { video.pause(); });
navigator.mediaSession.setActionHandler('play',  () => { video.play(); });
```

### 2. Alexa interruptions handled by the OS [O]
During playback, an Alexa query ("what's the weather") pauses the app,
shows the card, TTS answers, then playback resumes. No app code needed —
but test it: Amazon's submission checklist requires no audio overlap and
clean resume.
Source: https://developer.amazon.com/docs/vega/0.23/test-before-submission.html [O]

## What does NOT work for sideloaded apps

### 3. "Alexa, open KaviTV" — sideloaded apps aren't in Alexa's registry [O]
Alexa's app-launch registry is cloud-side. Amazon's own VSK troubleshooting
states it plainly:

> "During development, your Fire TV application should be manually started
> (launch your app before saying utterances) to be able to receive Alexa
> directives. **After you push your app to Live App Testing and field
> engineers map your ASIN to your app's package name, then you can
> explicitly target your app's name in utterances.**"

Source: https://developer.amazon.com/docs/video-skills-fire-tv-apps/troubleshooting.html
("Alexa is not able to start application by voice") [O]

Translation for Seth: sideloaded KaviTV will NEVER answer "Alexa, open
KaviTV". But once it's in **Live App Testing** (already the distribution
plan), voice launch should start working after Amazon maps the package.
This is another reason LAT beats permanent sideloading.

### 4. Quick play ("Alexa, watch X on KaviTV") — commercial catalog required [O]
Requires EMBER catalog integration: describing all media in Amazon's schema
and uploading to Amazon's S3 regularly. Built for Netflix-scale services,
not personal media libraries. Not feasible for KaviTV.
Source: https://developer.amazon.com/docs/vega/0.21/content-launcher-overview.html
("Before you start") [O, 2026-05-27]

### 5. Video Skills Kit (VSK) — Fire OS only, heavy, commercial [O]
VSK gives app launching + quick play + search + transport, but demands:
a Lambda backend, Alexa Client Library, ADM (Amazon Device Messaging),
AND catalog integration. The docs say "You need a native Android app" —
it's the Fire OS path, not Vega's. Vega's equivalent is Content Launcher
(above), which has the same catalog requirement for the good parts.
Source: https://developer.amazon.com/docs/fire-tv/voice-enable-your-app-and-content.html [O]

### 6. AlexaManager API — exists in the SDK, wrong tool for this job [O]
`@amazon-devices/react-native-kepler` ships a full `AlexaManager`
TurboModule (directives, state providers, capabilities, AVS events).
But it's the AVS **capability-agent** API — for building Alexa Smart Home
integrations (the `com.amazon.category.caf` manifest category is "for
Alexa Capability Agents (voice skill backends), not for being
voice-launched"). Registering a capability agent requires the Alexa
developer console + a smart-home skill. It does not make Alexa open your
app or route "pause" to it.
Source: SDK source
`node_modules/@amazon-devices/react-native-kepler/Libraries/AlexaManager/`
[O, SDK 0.24]; genius guide [C]

## Workarounds (ranked)

### A. Ship via Live App Testing (the real fix) [O]
Per Amazon's troubleshooting doc, LAT + ASIN→package mapping enables
"Alexa, open KaviTV". Already Seth's distribution plan. No extra code.

### B. Middle-man launcher app (proven Fire OS pattern) [C]
AFTVnews documents it: remote-pro buttons and Alexa can't launch
sideloaded apps, so use a middle-man Appstore app ("App Opener",
"My Launcher") that IS voice-registered; "Alexa, open my launcher"
opens it, and it launches the sideloaded target. Seth's own
"Seth Launcher" Vega app could play this role once IT is in LAT —
"Alexa, open Seth Launcher" → D-pad to KaviTV. One voice hop instead
of zero, but it works today.
Source: https://www.aftvnews.com/new-sideloaded-app-launcher-for-fire-tv-pro-remote-and-alexa-is-currently-free-normally-1-00/ [C, 2025-01]

### C. Alexa Routines [P]
Fire OS Alexa Routines can include "open app" actions. Whether routines
can target sideloaded Vega apps is unverified — worth a 5-minute test
once KaviTV has its tile: create a routine "Alexa, movie time" → open
KaviTV. If the routine picker lists it, this is the cheapest custom
voice command path.

### D. Custom Alexa skill + KaviTV's tsnet endpoint [P]
A private Alexa custom skill ("Alexa, ask KaviTV to tune horror") whose
Lambda calls the KaviTV app's tailnet control endpoint (`/tune`).
Fully custom utterances, but: needs the Lambda always reachable, the
app open (tsnet endpoint is foreground-only), and skill invocation
phrasing ("ask KaviTV to..."). Most flexible, most moving parts.

### E. Alexa+ add-ons (future) [P]
The 2026 Fire TV Stick 4K ships with Alexa+; Amazon's new "Alexa+ for
Builders" add-on model (MCP-based) is a possible future path for custom
voice integrations. Too early — no Vega-app voice story published yet.
Source: aboutamazon.com Fire TV 2026 announcement [O, 2026-10];
github.com/novacorpai/agentpos-alexa, github.com/kaylerch/alexa-skill-mcp-bridge [C]

## What to build (recommendation)

1. **Now**: implement KMC transport control in the KaviTV rebuild (free
   with W3C Media API; one integration otherwise). "Alexa, pause" will
   work sideloaded, day one.
2. **With LAT**: "Alexa, open KaviTV" should light up once Amazon maps
   the package — verify with a voice test after the LAT build is live.
3. **Later**: test Alexa Routines for custom phrases; keep the custom-skill
   architecture in the back pocket for "tune horror"-style commands.
4. **Don't**: invest in VSK, EMBER catalog, or AlexaManager capability
   agents for this goal — all commercial/heavy/wrong-tool.
