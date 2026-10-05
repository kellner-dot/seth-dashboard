---
name: "amazon-appstore"
description: "Manage Amazon Appstore apps via the App Submission API: verify access, stage new versions, upload APKs, update store listings, fix device targeting, submit for review. Triggers on 'Amazon Appstore', 'app submission', 'upload APK to Amazon', 'Amazon developer console apps', 'push Amazon build', 'Amazon connector'."
---

# Amazon Appstore

## Purpose
Manage Seth's **existing Android apps** on the Amazon Appstore through the
official App Submission API. Read-only checks, edit lifecycle (upcoming
versions), APK uploads, listing text updates, device targeting fixes, and
review submission.

## Hard limits (from Amazon's docs — do not work around these)
- **Android apps only.** The API does not support Web apps, and Vega
  (`.vpkg`) apps are not documented — the KaviTV Vega app's uploads stay a
  manual Developer Console step.
- **No Live App Testing via API.** LAT versions can only be created/updated
  in the console. This skill stages the *upcoming public version* only.
- **First version of an app must be submitted in the console.** The API
  manages subsequent versions of existing apps.
- **`commit` = submit for review immediately.** There is no staged/publish
  hold. Never commit without the user's explicit go-ahead for that exact
  version (`--yes` is required by the CLI).

## Tooling
`bin/amazon.py` (Python 3, stdlib only — no venv/deps). Auth via authd
surrogates; see Auth. Never prints credentials.

```
bin/amazon.py check --app <APP_ID>            # read-only: auth + open-edit state
bin/amazon.py edit-create --app <APP_ID>      # open an upcoming version (fails if one is open)
bin/amazon.py edit-discard --app <APP_ID>     # discard the open edit
bin/amazon.py upload --app <APP_ID> --file app.apk   # into open edit (creates one); never commits
bin/amazon.py listing-get --app <APP_ID> --lang en-US
bin/amazon.py listing-put --app <APP_ID> --lang en-US --file listing.json  # GET-merge + PUT
bin/amazon.py targeting-get --app <APP_ID> --apk <APK_ID>
bin/amazon.py targeting-put --app <APP_ID> --apk <APK_ID> --file targeting.json
bin/amazon.py commit --app <APP_ID> --yes      # SUBMITS FOR REVIEW — user must approve first
```
App IDs look like `amzn1.devportal.mobileapp.…` — from the console App List
(Seth has already browsed his: "Remote" and others).

Reference: `references/api-reference.md` (endpoints, ETag rules, gotchas).

## Auth
Uses the stored `custom.amazon-appstore` credential (entries `client_id`,
`client_secret`), applied as surrogates via
`/opt/hatch/skills/skill-creator/bin/dynamic_credentials.py`. The CLI mints
a 1-hour LWA bearer token (`appstore::apps:readwrite`) per run; tokens live
in memory only and auto-refresh once on 401/403.

**One-time setup (Seth, in the Developer Console):** Tools & Services →
API Access → App Submission API → create a Security Profile, copy the
client id + client secret. Then connect them as the `custom.amazon-appstore`
credential through the secure API-access flow (ask in the main Muse chat —
it cannot be pasted here). Verify with `bin/amazon.py check --app <APP_ID>`.

A 401/403 is a question about the request before it is a question about
the key: confirm the surrogate was attached (a request built without the
helper looks exactly like a bad token). Only then treat it as a credential
problem.

## Operating Rules
1. Use this skill when the user asks about his Amazon Appstore apps or the
   Amazon connector. Read-only commands need no extra approval; anything
   that opens an edit, uploads, or edits a listing is a write — confirm
   with the user first unless already authorized for that exact change.
2. Never run `commit` without the user's explicit approval of that version.
   Default to staging (leave the edit open for console review).
3. One active edit per app. If one is already open (console or API), do not
   pile on — report it and ask how to proceed.
4. Restrict authenticated requests to `api.amazon.com` and
   `developer.amazon.com` (enforced in code).
5. Do not print, log, or persist tokens or secrets. `--json` prints API
   results only.
6. API cannot set: content rating, pricing, availability, DRM, language
   support — those stay console steps. Say so instead of trying.
7. After an API APK upload, check device targeting (`targeting-get`):
   API-uploaded APKs often auto-target almost nothing — flip
   `NOT_TARGETING` devices with empty reasons to `TARGETING` (leave
   `DISABLED` ones alone) via `targeting-put` with the per-APK ETag.
