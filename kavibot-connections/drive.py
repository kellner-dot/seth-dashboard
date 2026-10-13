#!/usr/bin/env python3
"""Google Drive pilot connection (type: oauth2, read-only).

Capabilities:
  list_files(query=None, order_by="modifiedTime desc", max_results=20)
  get_file_metadata(file_id)
  download_file_text(file_id, max_chars=4000)

Text only: binaries are refused with a structured error and never dumped.
Google Docs/Sheets/Slides export to text automatically. Downloads are
size-capped. All HTTP goes through the injected adapter (mocked in tests).
Token values and file contents are never logged.
"""
import json
import urllib.parse

API_BASE = "https://www.googleapis.com/drive/v3"
SPEC_NAME = "drive"

TEXT_MIMES = {
    "application/json", "application/xml", "application/javascript",
    "application/x-yaml", "application/yaml", "application/rtf",
}
# Google Workspace types export to text instead of downloading raw.
GOOGLE_EXPORTS = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}
MAX_DOWNLOAD_BYTES = 200 * 1024


def _headers(access_token, extra=None):
    headers = {"Authorization": "Bearer " + access_token}
    headers.update(extra or {})
    return headers


def _get(http, access_token, path, params, extra_headers=None):
    url = API_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    status, body = http.get(url, _headers(access_token, extra_headers))
    if status != 200:
        raise RuntimeError("Drive API error http=%s" % status)
    return json.loads(body)


def _get_raw(http, access_token, path, params, extra_headers=None):
    url = API_BASE + path + "?" + urllib.parse.urlencode(params, doseq=True)
    status, body = http.get(url, _headers(access_token, extra_headers))
    if status != 200:
        raise RuntimeError("Drive API error http=%s" % status)
    if isinstance(body, str):
        body = body.encode("utf-8")
    return body


def list_files(http, access_token, headers=None, query=None,
               order_by="modifiedTime desc", max_results=20):
    """Files, most-recently-modified first by default. Metadata only."""
    params = {
        "pageSize": str(max(1, min(int(max_results), 50))),
        "orderBy": order_by,
        "fields": "files(id,name,mimeType,modifiedTime,size)",
    }
    if query:
        params["q"] = query
    data = _get(http, access_token, "/files", params,
                extra_headers=headers)
    return {"ok": True,
            "files": [_summarize(f) for f in data.get("files", [])]}


def get_file_metadata(http, access_token, headers=None, file_id=None):
    if not file_id:
        raise ValueError("file_id is required")
    data = _get(http, access_token,
                "/files/" + urllib.parse.quote(file_id),
                {"fields": "id,name,mimeType,modifiedTime,size,parents"},
                extra_headers=headers)
    return {"ok": True, "file": _summarize(data, full=True)}


def download_file_text(http, access_token, headers=None, file_id=None,
                       max_chars=4000):
    """Download a text-ish file; refuse binaries with a structured error.

    Google Workspace files are exported to text/csv automatically."""
    if not file_id:
        raise ValueError("file_id is required")
    meta = get_file_metadata(http, access_token, headers=headers,
                             file_id=file_id)["file"]
    mime = meta.get("mimeType", "")
    name = meta.get("name", file_id)
    if mime in GOOGLE_EXPORTS:
        path = "/files/" + urllib.parse.quote(file_id) + "/export"
        params = {"mimeType": GOOGLE_EXPORTS[mime]}
    elif mime.startswith("text/") or mime in TEXT_MIMES:
        size = int(meta.get("size") or 0)
        if size > MAX_DOWNLOAD_BYTES:
            return {"ok": False, "error": "too_large",
                    "message": "Refusing to download %r (%d bytes > %d "
                               "byte cap)" % (name, size,
                                              MAX_DOWNLOAD_BYTES)}
        path = "/files/" + urllib.parse.quote(file_id)
        params = {"alt": "media"}
    else:
        return {"ok": False, "error": "not_text",
                "message": "Refusing to download non-text file %r (%s)"
                           % (name, mime or "unknown type")}
    raw = _get_raw(http, access_token, path, params,
                   extra_headers=headers)
    text = raw.decode("utf-8", errors="replace")
    limit = max(1, int(max_chars))
    return {"ok": True, "file_id": file_id, "name": name,
            "mimeType": mime, "text": text[:limit],
            "truncated": len(text) > limit}


def _summarize(f, full=False):
    out = {
        "id": f.get("id"),
        "name": f.get("name"),
        "mimeType": f.get("mimeType"),
        "modifiedTime": f.get("modifiedTime"),
    }
    size = f.get("size")
    if size is not None:
        out["size"] = int(size)
    if full:
        out["parents"] = f.get("parents", [])
    return out


CAPABILITIES = {
    "list_files": list_files,
    "get_file_metadata": get_file_metadata,
    "download_file_text": download_file_text,
}
