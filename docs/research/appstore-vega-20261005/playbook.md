# Amazon Appstore Review Playbook — Vega OS (.vpkg) TV Apps

Researched 2026-10-05. Confidence labels: [O] official Amazon docs,
[C] verified community (repo, press, dev report), [P] plausible/inferred.

---

## 1. What review actually tests (official test cases)

Amazon publishes the exact tests it runs. Vega-specific list:
https://developer.amazon.com/docs/vega/0.23/test-before-submission.html [O]

| Test | Expected |
|---|---|
| Back-button exit + relaunch | Back through playback → Back to launcher; relaunch works clean |
| Home-button exit + relaunch | No audio leak on launcher; relaunch works |
| App switching | No audio overlap/crash/blank screen between apps |
| HDMI hot plug / TV power off | Playback pauses on disconnect, resumes from same position |
| Device restart | App launches; login state retained |
| Screensaver | No app audio over screensaver; Back returns to app |
| Alexa interruption | Video pauses, TTS plays, no overlap, resumes correctly |
| Bluetooth audio | Routes correctly, A/V in sync |

General criteria (all Fire TV apps):
https://developer.amazon.com/docs/app-testing/test-criteria.html [O]
- **2.5 Performance**: ≥25 fps sustained (55–60 recommended); no crashes/hard locks
- **2.6 eMMC writes**: <50 MB/hr foreground — video/audio must NOT buffer on eMMC
- **2.11 UI highlighting**: visible focus indicator (D-pad, not touch)
- **2.13 Navigability**: never trap the user; never force Home-button exit
- **2.22 Exit time**: Home exit ≤2 seconds
- **2.18 Audio focus**: acquire/abandon correctly, no overlap
- **2.19 HDMI disconnect**: must pause; resume from same position
- 1080p design, 10-foot readability, minimal text entry
- Install ≤4 GB; loading >15 s needs a progress indicator

**Implication for KaviTV**: the native rebuild (not the WebView wrapper) is
required — Back-to-exit, audio focus, HDMI pause, and eMMC-safe buffering
are all tested behaviors.

## 2. Top rejection reasons

Amazon's own top-3 (applies to all Appstore submissions) [O]:
https://developer.amazon.com/apps-and-games/blogs/2025/02/navigating-app-submission-and-compliance
1. **Intellectual property violations** — app + metadata must not infringe
   copyright/trademark. All assets original or licensed.
2. **Non-compliant in-app purchases** — any digital purchase MUST use
   Amazon IAP. External paywalls = rejection.
3. **Mismatched content ratings** — rating questionnaire must match actual
   content; Amazon can re-rate at its discretion.

Vega/media-specific (from test criteria + community) [O/C]:
4. **"Minimum Functionality and Spam"** — apps must go "beyond a simple
   website" [O]
   (https://developer.amazon.com/docs/app-submission/presubmission-checklist.html).
   A thin WebView wrapper risks this rejection — another reason the
   native KaviTV rebuild is the right call.
5. **Performance**: first launch >5 s draws a performance rejection [C]
   (https://blog.webnexs.com/how-to-build-a-fire-tv-app/)
6. **D-pad navigability**: anything requiring touch = flagged [C] (same)
7. **Codec compliance**: H.264/AAC expected; exotic codecs = media rejection [C] (same)
8. **Missing privacy policy URL** = "incomplete submission" [C] (same)
9. **Blank screen on launch / unresponsive remote** [C] (same)
10. **No `com.amazon.category.main`** — fails submission outright [O]
    (https://developer.amazon.com/docs/app-submission/submitting-apps-to-amazon-appstore.html:
    "will fail the Amazon Appstore submission process")

## 3. Listing rules

- **Never write "Vega" in marketing copy.** Market as a Fire TV app.
  Corroborated by astra-tv's approved listing: title/short/long
  descriptions say "Fire TV" throughout; "Vega OS" appears only in the
  supported-devices field [C]
  (https://github.com/wangdangel/astra-tv/blob/HEAD/docs/amazon-submission-v1.0.md,
  2026-07-05). Rule origin: prior Amazon research [C].
- **Fire TV assets required**: app icon 1280×720 PNG (no transparency);
  3–10 screenshots 1920×1080 JPG/PNG landscape (no transparency);
  background image 1920×1080 [C] (astra-tv submission doc; also
  https://beacon-help.support.brightcove.com/publishing-apps/fire-tv/submitting-to-amazon.html).
- **Screenshots must not show personal information** — use dummy
  server/account data [C] (astra-tv).
- **Reviewer credentials**: if the app needs login (media server),
  provide a test account via the secure reviewer-credentials field —
  never in public metadata [C] (astra-tv: they provisioned a test
  Jellyfin server + account for reviewers).
- **Privacy policy URL**: mandatory; host it before submitting [C].
- **Content rating**: answer the questionnaire honestly; for a media
  client use the astra-tv template: "contains no media catalog;
  content supplied by the user's own server and may vary" [C].

## 4. Version / build-number requirements

- Fire OS version codes and Vega build numbers are **independent** [O].
- Every submission must bump **both** version and build number above
  the previous submission's [O]
  (https://developer.amazon.com/docs/app-submission/submitting-apps-to-amazon-appstore.html).
- **Build number 0 is rejected** — start at 1 [C] (astra-tv community).
- If multiple VPKGs in one version (e.g. armv7 + x86_64), each needs a
  **unique** build number [C] (astra-tv, 2026-07-05: they used
  date-based build numbers 202607051/52/53).
- Console behavior (2026-07-05): x86_64 mapped to supported Vega
  devices; armv7/aarch64 mapped to 0 devices at that time [C] (astra-tv).
  Verify current device mapping at submission time.

## 5. LAT → production path

Official workflow:
https://developer.amazon.com/docs/vega/0.21/live-app-testing-understanding.html [O]
1. Submit VPKG to LAT (up to **5 parallel tests** per app).
2. Add testers to tester groups; testers install via email/push invite.
3. Evaluate feedback; iterate with new versions in the same test
   (existing binaries can't be edited — upload new).
4. **Promote to Upcoming**: available when the test has only ONE binary
   type (VPKG-only is fine). Disabled if APK+VPKG both present.
5. Then publish via the normal app submission workflow.

LAT practical notes [C]:
- Testers install via the on-stick Appstore Beta Hub (Vega-compatible).
- Invites expire after 30 days; resendable. Tests persist until
  manually ended — a perpetually-open single-tester LAT is a plausible
  private distribution channel [P] (not explicitly guaranteed).
- LAT itself is **not reviewed** — it's pre-review testing. No evidence
  of minimum-tester requirements or scrutiny of private LATs [P].
- IAP testing in LAT needs separate tester groups per device type
  (Fire OS vs Vega) with no shared emails [O].

## 6. Content policy for media apps (the piracy angle)

Amazon is aggressive here [C]:
- Nov 2025: Amazon + ACE (Alliance for Creativity and Entertainment)
  began **blocking apps "identified as providing access to pirated
  content"** — including sideloaded ones, at device level
  (https://www.androidcentral.com/streaming-tv/amazon-fire-tv/fire-tv-cracking-down-piracy-apps;
  https://www.ladbible.com/news/technology/dodgy-iptv-firestick-warning-tv-133618-20260324).
- Kodi was removed from the Appstore in 2015 for "facilitating piracy"
  (still true in 2026) [C]
  (https://www.howtogeek.com/fire-tv-is-quickly-becoming-the-worst-streaming-option-for-homelabbers/).

**The safe template** (astra-tv, approved on the Appstore) [C]:
- "Astra does not provide, sell, rent, stream, host, or include any
  movies, shows, channels, subscriptions, or live content. All media
  comes from your own server. You are responsible for your own server,
  media files, accounts, network configuration, and content rights."
- No bundled catalog, no public channels, no hosted service.
- **KaviTV fits this template exactly** (personal Emby library client).
  Use equivalent language in the listing.

## 7. Embedded networking (tsnet) — review view

**Strongest signal: VPN apps are LIVE on the Vega Appstore.**
NordVPN, IPVanish, Surfshark, ExpressVPN, and Proton VPN all ship
native Vega OS apps whose entire purpose is encrypted tunneling [C]:
- https://www.xda-developers.com/vpn-apps-finally-work-on-the-fire-tv-stick-4k-select-vega-os/ (Nov 2025)
- https://dovpn.com/vega-os-vpn-complete-guide/ (Amazon enabled VPN APIs late Nov 2025; approved apps request the one-time system VPN permission)
- https://www.techradar.com/vpn/vpn-services/surfshark-launches-native-vpn-app-for-amazons-new-vega-os-fire-tv-sticks
- https://www.vpncompare.co.uk/proton-vega-os-fire-tv-stick/ (Sep 2026)

**Assessment**: Amazon has approved multiple apps whose core function is
network tunneling on Vega. An embedded tsnet listener (tailnet-only,
user's own network) is strictly less privileged than a system VPN.
No public precedent for tsnet-in-Vega specifically (jellyfin-vega-tailnet
states "this is not an Amazon Appstore listing") [C], but the VPN
precedent makes rejection on networking grounds unlikely [P].

**Risk mitigations anyway**:
- Ship KaviTV through **Live App Testing first** — private, full
  launcher integration, zero public-review exposure [P].
- tsnet needs **zero special manifest privileges** (runs in the normal
  app sandbox) [C] (jellyfin-vega-tailnet).
- Declare the networking purpose honestly in review notes
  (remote control of the user's own server), following the astra-tv
  pattern of stating what the app does NOT do.

## 8. Review timelines

- Brightcove (Fire TV apps): **suggest 3 weeks lead time** [C]
  (https://beacon-help.support.brightcove.com/publishing-apps/fire-tv/submitting-to-amazon.html)
- avsign-lite (Fire TV app, GitHub): **3–5 business days** [C]
  (https://github.com/sandriverfish/avsign-lite/releases/tag/v1.0.4)
- Downloader dev (Elias, Mar 2026): **"usually a few days"**; updates
  ~24 h [C] (via aftvnews/YouTube).
- No Vega-specific timeline published; expect the Fire TV range
  (days, not weeks, for clean submissions) [P].
- Metadata-only updates review faster than binary updates [O]
  (https://developer.amazon.com/docs/app-submission/update-published-app.html).

## 9. Pre-submit checklist (KaviTV)

From the astra-tv packet [C], adapted:
- [ ] Release VPKG built (armv7), `vpt validate` 0 errors
- [ ] `com.amazon.category.main` in manifest; 512×512 launcher icon
- [ ] Version AND build number bumped (build ≥1)
- [ ] Back-to-exit, Home relaunch, HDMI pause, audio focus, no eMMC buffering
- [ ] D-pad navigable throughout; visible focus; 10-foot readable
- [ ] First launch <5 s; loading >15 s shows progress
- [ ] Dev credentials removed; tokens redacted from logs
- [ ] Privacy policy URL live
- [ ] 1280×720 icon, 3–10 screenshots (1920×1080, dummy data), 1920×1080 background
- [ ] Listing says "Fire TV", never "Vega"; media-client disclaimer language
- [ ] Test account / server for reviewers (secure credentials field)
- [ ] Content rating questionnaire answered (client-only template)
- [ ] LAT round first (private), then promote

---

## Sources

Official:
- https://developer.amazon.com/docs/app-submission/submitting-apps-to-amazon-appstore.html (updated Sep 28, 2026)
- https://developer.amazon.com/docs/vega/0.23/test-before-submission.html (Oct 22, 2025)
- https://developer.amazon.com/docs/app-testing/test-criteria.html
- https://developer.amazon.com/docs/app-submission/presubmission-checklist.html (Oct 8, 2025)
- https://developer.amazon.com/docs/vega/0.21/live-app-testing-understanding.html (Sep 30, 2025)
- https://developer.amazon.com/docs/vega/0.21/manage-test.html (Sep 30, 2025)
- https://developer.amazon.com/docs/app-submission/update-published-app.html
- https://developer.amazon.com/apps-and-games/blogs/2025/02/navigating-app-submission-and-compliance

Community:
- https://github.com/wangdangel/astra-tv/blob/HEAD/docs/amazon-submission-v1.0.md (2026-07-05) — real Vega submission packet
- https://github.com/AmbientFlare/astra-tv (Appstore-listed Vega Jellyfin client)
- https://github.com/sandriverfish/avsign-lite/releases/tag/v1.0.4 (3–5 day approval datapoint)
- https://github.com/acerbetti/skills/blob/HEAD/amazon-appstore/SKILL.md (API: commit = immediate review)
- https://beacon-help.support.brightcove.com/publishing-apps/fire-tv/submitting-to-amazon.html (3-week lead time)
- https://blog.webnexs.com/how-to-build-a-fire-tv-app/ (rejection culprits)
- XDA, TechRadar, dovpn.com, vpncompare.co.uk (VPN apps on Vega)
- Android Central, LADbible (ACE piracy crackdown)
