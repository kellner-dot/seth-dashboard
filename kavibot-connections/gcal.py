#!/usr/bin/env python3
"""Google Calendar pilot connection (type: oauth2, read-only).

Capabilities:
  list_events(time_min=None, time_max=None, max_results=20)
  get_event(event_id)

All HTTP goes through the injected adapter (mocked in tests). Token values
are never logged.
"""
import datetime
import json
import urllib.parse

API_BASE = "https://www.googleapis.com/calendar/v3"
SPEC_NAME = "gcal"


def _headers(access_token, extra=None):
    headers = {"Authorization": "Bearer " + access_token}
    headers.update(extra or {})
    return headers


def _get(http, access_token, path, params, extra_headers=None):
    url = API_BASE + path + "?" + urllib.parse.urlencode(params)
    status, body = http.get(url, _headers(access_token, extra_headers))
    if status != 200:
        raise RuntimeError("Calendar API error http=%s" % status)
    return json.loads(body)


def _iso(dt):
    if isinstance(dt, datetime.datetime):
        return dt.isoformat()
    return dt


def list_events(http, access_token, headers=None, time_min=None,
               time_max=None, max_results=20):
    """Upcoming events on the primary calendar, ordered by start time."""
    now = datetime.datetime.now(datetime.timezone.utc)
    params = {
        "timeMin": _iso(time_min) or now.isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": str(max(1, min(int(max_results), 50))),
    }
    if time_max:
        params["timeMax"] = _iso(time_max)
    data = _get(http, access_token, "/calendars/primary/events", params,
                extra_headers=headers)
    return {"ok": True, "events": [_summarize(e)
                                  for e in data.get("items", [])]}


def get_event(http, access_token, headers=None, event_id=None):
    data = _get(http, access_token,
                "/calendars/primary/events/" + urllib.parse.quote(event_id),
                {}, extra_headers=headers)
    return {"ok": True, "event": _summarize(data, full=True)}


def _summarize(event, full=False):
    start = event.get("start", {})
    end = event.get("end", {})
    out = {
        "id": event.get("id"),
        "summary": event.get("summary", "(no title)"),
        "start": start.get("dateTime", start.get("date")),
        "end": end.get("dateTime", end.get("date")),
        "location": event.get("location"),
    }
    if full:
        out["description"] = (event.get("description") or "")[:500]
        out["attendees"] = [a.get("email")
                            for a in event.get("attendees", [])]
    return out


CAPABILITIES = {
    "list_events": list_events,
    "get_event": get_event,
}
