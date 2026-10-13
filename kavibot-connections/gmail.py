#!/usr/bin/env python3
"""Gmail pilot connection (type: oauth2, read-only).

Capabilities:
  search_messages(query="", max_results=10)   # list + From/Subject/Date
  get_message(message_id)                     # full headers + text body

All HTTP goes through the injected adapter (mocked in tests). Token values
are never logged. Message bodies are returned to the caller, never logged.
"""
import base64
import json
import urllib.parse

API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
SPEC_NAME = "gmail"


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
        raise RuntimeError("Gmail API error http=%s" % status)
    return json.loads(body)


def search_messages(http, access_token, headers=None, query="",
                    max_results=10):
    """Search mail; returns From/Subject/Date/snippet per hit (no bodies)."""
    n = max(1, min(int(max_results), 20))
    params = {"maxResults": str(n)}
    if query:
        params["q"] = query
    data = _get(http, access_token, "/messages", params,
                extra_headers=headers)
    out = []
    for m in data.get("messages", []):
        meta = _get(http, access_token,
                    "/messages/" + urllib.parse.quote(m["id"]),
                    {"format": "metadata",
                     "metadataHeaders": ["From", "Subject", "Date"]},
                    extra_headers=headers)
        out.append(_summarize(meta))
    return {"ok": True, "messages": out,
            "resultSizeEstimate": data.get("resultSizeEstimate", len(out))}


def get_message(http, access_token, headers=None, message_id=None):
    """One message: headers plus decoded text body (size-capped)."""
    if not message_id:
        raise ValueError("message_id is required")
    data = _get(http, access_token,
                "/messages/" + urllib.parse.quote(message_id),
                {"format": "full"}, extra_headers=headers)
    out = _summarize(data)
    out["body_text"] = _body_text(data.get("payload") or {})[:4000]
    return {"ok": True, "message": out}


def _header_map(payload):
    out = {}
    for h in payload.get("headers", []):
        out[h.get("name", "").lower()] = h.get("value", "")
    return out


def _summarize(msg):
    headers = _header_map(msg.get("payload", {}))
    return {
        "id": msg.get("id"),
        "threadId": msg.get("threadId"),
        "from": headers.get("from", ""),
        "subject": headers.get("subject", "(no subject)"),
        "date": headers.get("date", ""),
        "snippet": msg.get("snippet", ""),
        "labelIds": msg.get("labelIds", []),
    }


def _b64d(data):
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad).decode("utf-8",
                                                      errors="replace")


def _body_text(payload):
    """First text/plain part found, base64url-decoded. Attachments skipped."""
    mime = payload.get("mimeType", "")
    body = payload.get("body") or {}
    if body.get("data") and mime.startswith("text/"):
        return _b64d(body["data"])
    for part in payload.get("parts") or []:
        if part.get("filename"):
            continue  # attachment, not body text
        text = _body_text(part)
        if text:
            return text
    return ""


CAPABILITIES = {
    "search_messages": search_messages,
    "get_message": get_message,
}
