# Live App Testing (LAT) — deep dive

All claims checked 2026-10-05. Confidence: [O] = verified-official (Amazon
docs), [C] = verified-community (real project/doc, not Amazon), [P] =
plausible-unverified (strong inference, do not present as fact).

## What LAT is
- Distribute an app to a **pre-defined set of testers** (by email) before it
  goes live. Testers exercise the full production Appstore environment
  (incl. IAP at zero cost). [O]
  https://developer.amazon.com/docs/app-testing/live-app-testing-faq.html
- Only invited testers can see/install the test build; general customers
  cannot browse it. [O] (same FAQ: "Can any customer see my Live App Testing
  app's APK? — No.")
- Free. Testers are supplied by the developer, not Amazon. [O] (same FAQ)
- No Appstore review gate is documented anywhere in the LAT workflow — the
  whole point is testing *before* review. Treat "no review before LAT
  distribution" as [P] (absence of evidence in the official workflow).

## Limits
- **Max 1,500 testers** per test. [O]
  https://developer.amazon.com/docs/app-testing/live-app-testing-faq.html
- **Up to 5 parallel tests per app** (Vega docs: "You can test additional
  packages of your app (up to five) in parallel by creating new tests"). [O]
  https://developer.amazon.com/docs/vega/0.21/live-app-testing-understanding.html
- **LAT invitations expire 30 days after sending** — the *invitation*, not
  the test. Resend to re-invite. [O]
  https://developer.amazon.com/docs/vega/0.23/manage-testers.html
- Tests themselves persist until **ended manually** (then listed under Past
  Tests / Test history). No auto-expiry of an active test is documented —
  indefinite private distribution via a perpetually-open LAT test is [P],
  not a documented feature.
- **Not supported for the Mexico marketplace** (amazon.mx invites carry no
  LAT links; use US links). [O]
  http://developer.amazon.com/docs/app-testing/live-app-testing-getting-started.html
- Amazon imposes **no confidentiality** on testers. [O] (LAT FAQ)

## Console workflow (developer side)
1. Developer Console → **My Apps** → app's menu → **Live App Testing**. [O]
   http://developer.amazon.com/docs/app-testing/live-app-testing-getting-started.html
2. **Create a new Live App Test** (optionally copy details from the live
   version or a previous test). [O] (same)
3. Upload the app binary (**APK and/or VPKG** — can submit one type first,
   add the second later by editing the test; **cannot edit/replace a binary
   already submitted** — changes require a new live app test). [O]
   https://developer.amazon.com/docs/vega/0.21/live-app-testing-understanding.html
4. Add testers / tester groups (email addresses). For IAP testing across
   Fire OS *and* Vega OS, use **mutually exclusive groups** (no shared
   emails) to avoid entitlement conflicts. [O] (same)
5. In the test's **Actions** column, click **Submit**. Invitation emails can
   take **up to several hours** to arrive. [O]
   http://developer.amazon.com/docs/app-testing/live-app-testing-getting-started.html
6. Required per test: binary, targeted devices, app icon, text metadata
   (title, category, language support), content rating, tester emails. [O]
   https://developer.amazon.com/docs/vega/0.21/understanding-appstore-devtest-iap.html

## Promote to Upcoming (the LAT → release bridge)
- With a **single binary type** in the test, **Actions → Promote to
  Upcoming** submits straight toward Appstore publication — no binary
  re-upload needed; metadata from the test **replaces** live metadata
  (review/edit it before submitting). [O]
  https://developer.amazon.com/docs/vega/0.21/manage-test.html
- With **both APK and VPKG** attached, Promote to Upcoming is **not
  available** (remove one binary type, or use the standard submission
  flow). [O]
  https://developer.amazon.com/docs/vega/0.21/live-app-testing-understanding.html
- Promoting a test over an existing live version requires binary version
  codes **>=** the live version's. [O] (same manage-test page)
- Package name must be unique to the app; if a partner ever submitted the
  same package for LAT, they must end their test first. [O]
  https://developer.amazon.com/docs/app-submission/publish-app-upload-app-files.html

## Tester side (what Seth does on his stick)
- **Recommended: Appstore Beta Hub.** Official Amazon app; testers search
  "Appstore Beta Hub" in the Appstore and install it. Supports **Fire TV on
  Vega OS and Fire OS 7+**. Lets testers discover/redeem LAT invitations,
  install/launch test apps, check for updates, and switch LAT tracks —
  entirely on-device. [O]
  http://developer.amazon.com/docs/app-testing/prepare-app-testers.html
  (last updated Sep 28, 2026)
- Email flow (fallback): invitation email → marketplace link → Appstore
  retail page → **Get App** (web) or **Send to Device** (Vega) → on the
  Vega stick: "You are now a Tester for: <App>" → install. [O]
  https://developer.amazon.com/docs/vega/0.21/prepare-app-testers.html
  (last updated Feb 17, 2026)
- **The tester email must match the Amazon account signed into the Fire
  TV.** [C] https://help.ventunotech.com/en/articles/6907563-how-to-install-the-fire-tv-app-via-test-invitation
  (community help center; consistent with Amazon's "accepted the invitation
  with the Amazon account they are using for testing" [O] in the LAT FAQ)
- If the test doesn't appear: **Settings → My Account → Sync Amazon
  Content**, confirm the invite was accepted, confirm device compatibility.
  [O] https://developer.amazon.com/docs/app-testing/live-app-testing-faq.html
- Multiple LAT tracks of one app on one device: **uninstall** the current
  track's build before installing another. [O]
  http://developer.amazon.com/docs/app-testing/prepare-app-testers.html
- Test builds show a **"TEST n" badge** on the icon (matches the test number
  on the LAT dashboard). [O] (same)
- Tester Management console shows invitation status: Delivered / Failed /
  Pending / **Expired**; opt-out testers can be re-invited via the opt-in
  link under Tools & Services → Tester Management. [O]
  https://developer.amazon.com/docs/vega/0.23/manage-testers.html

## What LAT cannot do (hard limits)
- **No API access**: "You cannot use the API to create or update the LAT
  version of your app." [O]
  https://developer.amazon.com/docs/app-submission-api/overview.html
- Feedback has no in-console channel — testers report to the developer
  directly. [O] (LAT FAQ)

## Implication for Seth's private-KaviTV plan
LAT with a single tester (his own email) is the closest thing Amazon offers
to private distribution: no public listing, no review before testers
install, installable/updated on-device via Appstore Beta Hub. The open
question is whether Amazon tolerates a perpetually-open LAT test as a
permanent distribution channel — undocumented, so treat as [P] and keep the
public-listing fallback in mind.
