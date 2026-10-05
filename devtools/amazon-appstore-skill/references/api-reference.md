# App Submission API — reference

Base: `https://developer.amazon.com/api/appstore/v1`
Token: `POST https://api.amazon.com/auth/o2/token`
(`grant_type=client_credentials`, `scope=appstore::apps:readwrite`; ~1h)

Official docs: https://developer.amazon.com/docs/app-submission-api/overview.html
(Last verified against docs + a live-tested community implementation, Oct 2026.)

## Endpoints used by `bin/amazon.py`

| Call | Notes |
|---|---|
| `GET /applications/{appId}/edits` | active edit + ETag; 404/empty = none open |
| `POST /applications/{appId}/edits` | create edit (`{}` body) |
| `DELETE /applications/{appId}/edits/{editId}` | discard; needs If-Match ETag |
| `POST /applications/{appId}/edits/{editId}/apks` | multipart upload, field name `file` |
| `GET /applications/{appId}/edits/{editId}/apks/{apkId}/targeting` | device list + per-APK ETag |
| `PUT .../apks/{apkId}/targeting` | replace targeting; needs per-APK ETag |
| `GET /applications/{appId}/edits/{editId}/listings/{lang}` | listing + ETag |
| `PUT .../listings/{lang}` | **replaces whole listing** — GET-merge first; If-Match ETag |
| `POST /applications/{appId}/edits/{editId}/listings/{lang}/{type}/upload` | image upload (not in CLI v1) |
| `POST /applications/{appId}/edits/{editId}/commit` | If-Match ETag → SUBMITTED for review |

## Gotchas
1. **commit submits for review immediately** — no managed-publishing hold.
   Preview via `listing-get`; only `--commit` when final.
2. **One active edit at a time** across API *and* console. Committing while
   someone has console work open submits their work too.
3. **No PATCH** — listing PUT replaces the whole object; always GET-merge.
4. **ETags everywhere**: listings, images, edits, and per-APK targeting each
   have their own ETag; re-read before each mutation.
5. `keywords` is required and must be **single words** (else `400
   SINGLE_WORD`); missing array fails `required_data_absent`.
6. Token expires hourly — CLI refreshes once on 401/403 and retries.
7. **DRM cannot be set via API** — set it in the console before submitting,
   or commit fails with `error_apk_drm_value_missing`.
8. **Language Support cannot be set via API** — console checkboxes.
9. **Content rating / pricing / availability**: console only.
10. **Targeting**: API-uploaded APKs auto-target almost nothing. Fix via
    targeting-get/put (flip `NOT_TARGETING` with empty reason → `TARGETING`;
    leave `DISABLED` alone).
11. **Not supported by the API at all**: LAT versions, Web apps, AAB
    binaries. (Vega `.vpkg` is undocumented — treat as unsupported until
    Amazon says otherwise.)
