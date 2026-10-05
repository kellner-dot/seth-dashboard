#!/usr/bin/env python3
"""
amazon.py -- Amazon Appstore App Submission API CLI.

Read ~/workspace/skills/amazon-appstore/SKILL.md before use.

Never prints credentials. All authenticated traffic goes only to
api.amazon.com (Login with Amazon token endpoint) and developer.amazon.com
(App Submission API). Secrets are referenced via authd surrogates only.

Requires: an LWA Security Profile (client_id + client_secret, scope
appstore::apps:readwrite) stored as credential "custom.amazon-appstore".
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (  # noqa: E402
    DynamicCredentialError,
    dynamic_credential_entry,
    ensure_allowed_url,
    read_json_response,
    read_response_body,
)

CRED_NAME = "custom.amazon-appstore"
TOKEN_URL = "https://api.amazon.com/auth/o2/token"
API_BASE = "https://developer.amazon.com/api/appstore/v1"
ALLOWED_HOSTS = ["api.amazon.com", "developer.amazon.com"]
SCOPE = "appstore::apps:readwrite"

_token: tuple[str, float] | None = None


class CliError(RuntimeError):
    pass


def _surrogate(entry_name: str) -> str:
    return dynamic_credential_entry(CRED_NAME, entry_name)["surrogate"].strip()


def get_token() -> str:
    """OAuth client_credentials token from Login with Amazon (cached ~1h)."""
    global _token
    if _token and _token[1] > time.time() + 60:
        return _token[0]
    client_id = _surrogate("client_id")
    client_secret = _surrogate("client_secret")
    ensure_allowed_url(TOKEN_URL, ALLOWED_HOSTS)
    # Build the form body by hand so the hsurr: surrogates are NOT
    # percent-encoded (authd replaces them verbatim on approved egress).
    body = (
        "grant_type=client_credentials"
        "&client_id=" + client_id +
        "&client_secret=" + client_secret +
        "&scope=" + urllib.parse.quote(SCOPE, safe="")
    ).encode("ascii")
    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as e:
        detail = e.read(400).decode("utf-8", "replace")
        raise CliError(f"LWA token request failed: HTTP {e.code}: {detail}")
    except DynamicCredentialError:
        raise
    except Exception as e:  # noqa: BLE001
        raise CliError(f"LWA token request failed: {e}")
    data = read_json_response(resp)
    if "access_token" not in data:
        raise CliError(f"LWA token response missing access_token: {data}")
    _token = (data["access_token"], time.time() + int(data.get("expires_in", 3600)) - 120)
    return _token[0]


def api(method: str, path: str, body_obj=None, etag: str | None = None,
        raw: bytes | None = None, content_type: str | None = None,
        timeout: int = 120):
    """Low-level API call. Returns (status, body_bytes, headers). Refreshes token once on 401/403."""
    url = API_BASE + path
    ensure_allowed_url(url, ALLOWED_HOSTS)
    data = None
    headers: dict[str, str] = {}
    if raw is not None:
        data = raw
        headers["Content-Type"] = content_type or "application/octet-stream"
    elif body_obj is not None:
        data = json.dumps(body_obj).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if etag:
        headers["If-Match"] = etag

    def _do(tok: str):
        req = urllib.request.Request(
            url, data=data, method=method,
            headers={"Authorization": "Bearer " + tok, **headers},
        )
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
            return resp.status, read_response_body(resp), resp.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read(65536), e.headers

    token = get_token()
    status, payload, hdrs = _do(token)
    if status in (401, 403):
        global _token
        _token = None  # force refresh; token may have expired (hourly)
        status, payload, hdrs = _do(get_token())
    return status, payload, hdrs


def api_json(method: str, path: str, **kw):
    status, payload, hdrs = api(method, path, **kw)
    text = payload.decode("utf-8", "replace")
    if not 200 <= status < 300:
        raise CliError(f"{method} {path} -> HTTP {status}: {text[:600]}")
    try:
        return json.loads(text) if text.strip() else {}, hdrs
    except json.JSONDecodeError:
        raise CliError(f"{method} {path} -> HTTP {status} (non-JSON): {text[:300]}")


def open_edit(app_id: str):
    """Return (edit_dict, etag) for the currently open edit, or (None, None)."""
    status, payload, hdrs = api("GET", f"/applications/{app_id}/edits")
    text = payload.decode("utf-8", "replace")
    if status == 404:
        return None, None
    if not 200 <= status < 300:
        raise CliError(f"GET edits -> HTTP {status}: {text[:600]}")
    try:
        edit = json.loads(text) if text.strip() else None
    except json.JSONDecodeError:
        raise CliError(f"GET edits -> non-JSON: {text[:300]}")
    if not edit:
        return None, None
    return edit, hdrs.get("ETag")


def ensure_edit(app_id: str):
    edit, etag = open_edit(app_id)
    if edit:
        return edit, etag
    edit, hdrs = api_json("POST", f"/applications/{app_id}/edits", body_obj={})
    return edit, hdrs.get("ETag")


def edit_id_of(edit: dict) -> str:
    return str(edit.get("id") or edit.get("editId") or "")


# ---------------------------------------------------------------- commands

def cmd_check(args):
    get_token()  # raises if auth is broken
    edit, _ = open_edit(args.app)
    out = {"auth": "ok", "app": args.app,
           "open_edit": edit_id_of(edit) if edit else None,
           "edit_state": (edit.get("state") if isinstance(edit, dict) else None)}
    return out


def cmd_edit_create(args):
    edit, _ = open_edit(args.app)
    if edit:
        raise CliError(f"an edit is already open ({edit_id_of(edit)}); Amazon allows only one at a time")
    edit, _ = api_json("POST", f"/applications/{args.app}/edits", body_obj={})
    return {"created_edit": edit_id_of(edit), "state": edit.get("state")}


def cmd_edit_discard(args):
    edit, etag = open_edit(args.app)
    if not edit:
        return {"discarded": None, "note": "no open edit"}
    eid = edit_id_of(edit)
    status, payload, _ = api("DELETE", f"/applications/{args.app}/edits/{eid}", etag=etag)
    if status not in (200, 204):
        raise CliError(f"DELETE edit -> HTTP {status}: {payload.decode('utf-8','replace')[:400]}")
    return {"discarded": eid}


def _multipart(field: str, filename: str, data: bytes, ctype: str):
    boundary = "----amazform" + os.urandom(16).hex()
    head = (f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n").encode("ascii")
    tail = f"\r\n--{boundary}--\r\n".encode("ascii")
    return head + data + tail, f"multipart/form-data; boundary={boundary}"


def cmd_upload(args):
    if not os.path.isfile(args.file):
        raise CliError(f"file not found: {args.file}")
    with open(args.file, "rb") as f:
        blob = f.read()
    size_mb = len(blob) / (1024 * 1024)
    edit, _ = ensure_edit(args.app)
    eid = edit_id_of(edit)
    filename = os.path.basename(args.file)
    ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    body, ctype_full = _multipart("file", filename, blob, ctype)
    status, payload, _ = api("POST", f"/applications/{args.app}/edits/{eid}/apks",
                             raw=body, content_type=ctype_full, timeout=600)
    text = payload.decode("utf-8", "replace")
    if not 200 <= status < 300:
        raise CliError(f"APK upload -> HTTP {status}: {text[:600]}")
    try:
        info = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError:
        info = {"raw": text[:300]}
    return {"uploaded": filename, "size_mb": round(size_mb, 1), "edit": eid,
            "apk": info.get("id") or info}


def cmd_listing_get(args):
    edit, _ = ensure_edit(args.app)
    eid = edit_id_of(edit)
    data, _ = api_json("GET", f"/applications/{args.app}/edits/{eid}/listings/{args.lang}")
    return data


def cmd_listing_put(args):
    with open(args.file, "r", encoding="utf-8") as f:
        updates = json.load(f)
    edit, _ = ensure_edit(args.app)
    eid = edit_id_of(edit)
    current, hdrs = api_json("GET", f"/applications/{args.app}/edits/{eid}/listings/{args.lang}")
    merged = dict(current)
    merged.update(updates)  # Amazon has no PATCH; PUT replaces the whole listing
    put_hdrs = {"ETag": hdrs.get("ETag")} if hdrs.get("ETag") else {}
    status, payload, _ = api("PUT", f"/applications/{args.app}/edits/{eid}/listings/{args.lang}",
                             body_obj=merged, etag=put_hdrs.get("ETag"))
    text = payload.decode("utf-8", "replace")
    if not 200 <= status < 300:
        raise CliError(f"PUT listing -> HTTP {status}: {text[:600]}")
    return {"updated_listing": args.lang, "edit": eid, "fields": sorted(updates.keys())}


def cmd_commit(args):
    if not args.yes:
        raise CliError("refusing to commit without --yes: commit submits the edit for Amazon review immediately")
    edit, etag = open_edit(args.app)
    if not edit:
        raise CliError("no open edit to commit")
    eid = edit_id_of(edit)
    status, payload, _ = api("POST", f"/applications/{args.app}/edits/{eid}/commit", etag=etag)
    text = payload.decode("utf-8", "replace")
    if not 200 <= status < 300:
        raise CliError(f"commit -> HTTP {status}: {text[:600]}")
    try:
        info = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError:
        info = {"raw": text[:300]}
    return {"committed_edit": eid, "result": info}


def cmd_targeting_get(args):
    edit, _ = open_edit(args.app)
    if not edit:
        raise CliError("no open edit; upload a binary first")
    eid = edit_id_of(edit)
    data, _ = api_json("GET", f"/applications/{args.app}/edits/{eid}/apks/{args.apk}/targeting")
    return data


def cmd_targeting_put(args):
    with open(args.file, "r", encoding="utf-8") as f:
        targeting = json.load(f)
    edit, _ = open_edit(args.app)
    if not edit:
        raise CliError("no open edit")
    eid = edit_id_of(edit)
    _, hdrs = api_json("GET", f"/applications/{args.app}/edits/{eid}/apks/{args.apk}/targeting")
    etag = hdrs.get("ETag")
    status, payload, _ = api("PUT", f"/applications/{args.app}/edits/{eid}/apks/{args.apk}/targeting",
                             body_obj=targeting, etag=etag)
    text = payload.decode("utf-8", "replace")
    if not 200 <= status < 300:
        raise CliError(f"PUT targeting -> HTTP {status}: {text[:600]}")
    return {"updated_targeting": args.apk, "edit": eid}


# ---------------------------------------------------------------- main

def build_parser():
    p = argparse.ArgumentParser(description="Amazon Appstore App Submission API CLI")
    p.add_argument("--json", action="store_true", help="print raw JSON result")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="verify auth and show open-edit state (read-only)")
    c.add_argument("--app", required=True, help="App ID (amzn1.devportal.mobileapp...)")
    c.set_defaults(fn=cmd_check)

    c = sub.add_parser("edit-create", help="open a new edit (upcoming version)")
    c.add_argument("--app", required=True)
    c.set_defaults(fn=cmd_edit_create)

    c = sub.add_parser("edit-discard", help="discard the open edit")
    c.add_argument("--app", required=True)
    c.set_defaults(fn=cmd_edit_discard)

    c = sub.add_parser("upload", help="upload APK/binary into the open edit (creates one if needed; never commits)")
    c.add_argument("--app", required=True)
    c.add_argument("--file", required=True, help="path to APK/VPKG")
    c.set_defaults(fn=cmd_upload)

    c = sub.add_parser("listing-get", help="fetch a locale listing from the open edit")
    c.add_argument("--app", required=True)
    c.add_argument("--lang", default="en-US")
    c.set_defaults(fn=cmd_listing_get)

    c = sub.add_parser("listing-put", help="merge a JSON file into a locale listing (GET-merge + PUT)")
    c.add_argument("--app", required=True)
    c.add_argument("--lang", default="en-US")
    c.add_argument("--file", required=True, help="JSON file with listing fields to update")
    c.set_defaults(fn=cmd_listing_put)

    c = sub.add_parser("commit", help="SUBMIT the open edit for Amazon review (requires --yes)")
    c.add_argument("--app", required=True)
    c.add_argument("--yes", action="store_true", help="confirm immediate submission for review")
    c.set_defaults(fn=cmd_commit)

    c = sub.add_parser("targeting-get", help="fetch device targeting for an uploaded APK")
    c.add_argument("--app", required=True)
    c.add_argument("--apk", required=True, help="APK id from the upload response")
    c.set_defaults(fn=cmd_targeting_get)

    c = sub.add_parser("targeting-put", help="replace device targeting for an uploaded APK")
    c.add_argument("--app", required=True)
    c.add_argument("--apk", required=True)
    c.add_argument("--file", required=True, help="JSON file with targeting object")
    c.set_defaults(fn=cmd_targeting_put)

    return p


def main():
    args = build_parser().parse_args()
    try:
        result = args.fn(args)
    except CliError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except DynamicCredentialError as e:
        print(f"auth error: {e}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
