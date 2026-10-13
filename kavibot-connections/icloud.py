#!/usr/bin/env python3
"""iCloud pilot connection (type: app_password, read-only).

Apple offers no OAuth for iCloud services, so auth is the user's Apple ID
plus an **app-specific password** generated at appleid.apple.com (requires
Apple ID two-factor authentication; revocable there at any time). The
password is vaulted via SecretStore exactly like OAuth refresh tokens -
prompted interactively, never logged, never in code/git/chat.

Capabilities:
  search_messages(query="", max_results=10)   # iCloud Mail, IMAP
  get_message(uid)                            # iCloud Mail, IMAP
  list_events(time_min=None, time_max=None, max_results=20)  # CalDAV
  list_contacts(max_results=50)               # CardDAV

Network goes through injectable adapters (mocked in tests, synthetic
fixtures only):
  - IMAP: `imap_factory()` -> imaplib.IMAP4_SSL-like object.
  - CalDAV/CardDAV: the `http` adapter's `.request(method, url, body,
    headers)`; when the adapter lacks it (the default UrllibHttp only does
    GET/POST), the module falls back to its own urllib-based DavHttp.
"""
import base64
import datetime
import email
import email.policy
import imaplib
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from connection import AuthError

SPEC_NAME = "icloud"

IMAP_HOST = "imap.apple.com"
CALDAV_BASE = "https://caldav.icloud.com/"
CARDDAV_BASE = "https://contacts.icloud.com/"

BODY_CAP = 4000
SNIPPET_CAP = 160


def _basic_auth(apple_id, app_password):
    raw = ("%s:%s" % (apple_id, app_password)).encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


class DavHttp:
    """urllib adapter with arbitrary HTTP methods (PROPFIND/REPORT)."""

    def request(self, method, url, body=None, headers=None):
        data = body.encode("utf-8") if isinstance(body, str) else body
        req = urllib.request.Request(url, data=data,
                                     headers=headers or {}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")


def _dav_request(http, method, url, apple_id, app_password, body=None,
                 depth=None):
    headers = {"Authorization": _basic_auth(apple_id, app_password),
               "Content-Type": "application/xml; charset=utf-8"}
    if depth is not None:
        headers["Depth"] = depth
    transport = http.request if hasattr(http, "request") else DavHttp().request
    status, resp_body = transport(method, url, body, headers)
    if status == 401:
        raise AuthError(
            "iCloud rejected the Apple ID / app-specific password (401). "
            "Generate a fresh one at appleid.apple.com (Sign-In and Security "
            "-> App-Specific Passwords) and reconnect.")
    if status not in (200, 207):
        raise RuntimeError("iCloud DAV error: %s %s -> http %s"
                           % (method, url, status))
    return resp_body


# ---------------------------------------------------------------------------
# CalDAV / CardDAV discovery + XML helpers
# ---------------------------------------------------------------------------

_NS = {"d": "DAV:",
       "c": "urn:ietf:params:xml:ns:caldav",
       "card": "urn:ietf:params:xml:ns:carddav"}


def _propfind_body(props):
    """props: list of (namespace_uri, localname)."""
    inner = "".join("<%s xmlns=\"%s\"/>" % (tag, ns) for ns, tag in props)
    return ("<?xml version=\"1.0\" encoding=\"utf-8\"?>"
            "<d:propfind xmlns:d=\"DAV:\"><d:prop>%s</d:prop></d:propfind>"
            % inner)


def _hrefs_of(xml_text, xpath):
    """All <d:href> texts under elements matching xpath."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    out = []
    for elem in root.findall(xpath, _NS):
        href = elem.find("d:href", _NS)
        if href is not None and href.text:
            out.append(href.text.strip())
    return out


def _discover_collections(http, apple_id, app_password, base_url,
                          home_set_prop, collection_marker):
    """Standard DAV discovery: principal -> home set -> collections.

    collection_marker: ("c", "calendar") or ("card", "addressbook") -
    matched against the collection's <resourcetype>.
    """
    # 1. current-user-principal
    resp = _dav_request(http, "PROPFIND", base_url, apple_id, app_password,
                        _propfind_body([("DAV:", "current-user-principal")]),
                        depth="0")
    principals = _hrefs_of(resp, ".//d:prop/d:current-user-principal")
    if not principals:
        raise RuntimeError("iCloud DAV discovery: no current-user-principal")
    principal = urllib.parse.urljoin(base_url, principals[0])
    # 2. home set (calendar-home-set / addressbook-home-set)
    resp = _dav_request(http, "PROPFIND", principal, apple_id, app_password,
                        _propfind_body([("DAV:", home_set_prop)]), depth="0")
    homes = _hrefs_of(resp, ".//d:prop/d:%s" % home_set_prop)
    if not homes:
        raise RuntimeError("iCloud DAV discovery: no %s" % home_set_prop)
    home = urllib.parse.urljoin(base_url, homes[0])
    # 3. collections whose resourcetype carries the marker
    resp = _dav_request(
        http, "PROPFIND", home, apple_id, app_password,
        _propfind_body([("DAV:", "resourcetype"), ("DAV:", "displayname")]),
        depth="1")
    collections = []
    try:
        root = ET.fromstring(resp)
    except ET.ParseError:
        return []
    ns_uri, marker = collection_marker
    for response in root.findall("d:response", _NS):
        rtype = response.find("d:propstat/d:prop/d:resourcetype", _NS)
        if rtype is None:
            continue
        if rtype.find("{%s}%s" % (ns_uri, marker)) is None:
            continue
        href = response.find("d:href", _NS)
        if href is not None and href.text:
            url = urllib.parse.urljoin(base_url, href.text.strip())
            if url.rstrip("/") != home.rstrip("/"):
                collections.append(url)
    return collections


# ---------------------------------------------------------------------------
# Minimal vCard / iCalendar parsers (dependency-free)
# ---------------------------------------------------------------------------

def _unfold(text):
    lines = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line[:1] in (" ", "\t") and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def _parse_vcard(card_text):
    """Return {name, emails[], phones[]} - name/email/phone only."""
    name, emails, phones = None, [], []
    for line in _unfold(card_text):
        if ":" not in line:
            continue
        prop, _, value = line.partition(":")
        pname = prop.split(";")[0].strip().upper()
        value = value.strip()
        if pname == "FN" and not name:
            name = value
        elif pname == "EMAIL" and value and value not in emails:
            emails.append(value)
        elif pname == "TEL" and value and value not in phones:
            phones.append(value)
    return {"name": name, "emails": emails[:5], "phones": phones[:5]}


def _parse_dt(value):
    """Parse an iCalendar DATE-TIME/DATE value to ISO-ish string."""
    v = value.strip()
    try:
        if v.endswith("Z"):
            dt = datetime.datetime.strptime(v, "%Y%m%dT%H%M%SZ")
            return dt.replace(tzinfo=datetime.timezone.utc).isoformat()
        if "T" in v:
            return datetime.datetime.strptime(
                v[:15], "%Y%m%dT%H%M%S").isoformat()
        return datetime.datetime.strptime(v, "%Y%m%d").date().isoformat()
    except ValueError:
        return v


def _parse_vevent(block):
    event = {}
    for line in _unfold(block):
        if ":" not in line:
            continue
        prop, _, value = line.partition(":")
        pname = prop.split(";")[0].strip().upper()
        if pname == "UID":
            event["id"] = value.strip()
        elif pname == "SUMMARY":
            event["summary"] = value.strip()
        elif pname == "DTSTART":
            event["start"] = _parse_dt(value)
        elif pname == "DTEND":
            event["end"] = _parse_dt(value)
        elif pname == "LOCATION":
            event["location"] = value.strip()
    return event


def _extract_vevents(calendar_data):
    events = []
    blocks, current = [], None
    for line in _unfold(calendar_data):
        if line.strip().upper() == "BEGIN:VEVENT":
            current = []
        elif line.strip().upper() == "END:VEVENT" and current is not None:
            blocks.append("\n".join(current))
            current = None
        elif current is not None:
            current.append(line)
    for block in blocks:
        event = _parse_vevent(block)
        if event.get("summary") or event.get("start"):
            events.append(event)
    return events


# ---------------------------------------------------------------------------
# IMAP (iCloud Mail)
# ---------------------------------------------------------------------------

def _default_imap_factory():
    return imaplib.IMAP4_SSL(IMAP_HOST)


def _imap_login(apple_id, app_password, imap_factory=None):
    factory = imap_factory or _default_imap_factory
    try:
        conn = factory()
    except Exception as exc:
        raise RuntimeError("Could not reach iCloud Mail (IMAP): %s" % exc)
    try:
        conn.login(apple_id, app_password)
    except imaplib.IMAP4.error as exc:
        raise AuthError("iCloud Mail login failed: %s" % exc)
    return conn


def verify(apple_id, app_password, imap_factory=None):
    """Cheap credential check: IMAP login + logout. True on success."""
    conn = _imap_login(apple_id, app_password, imap_factory)
    try:
        conn.logout()
    except Exception:
        pass
    return True


def _imap_bytes(parts):
    """Collect raw message bytes from an imaplib FETCH response.

    Real FETCH responses look like
    ``[(b'1 (UID 1 BODY[] {1234}\\r\\n', b'<message bytes>'), b')']`` -
    the first element of each tuple is the response header line, not
    message content, so it is skipped."""
    chunks = []
    for part in parts or []:
        if isinstance(part, tuple):
            items = list(part)
            if items and isinstance(items[0], bytes):
                items = items[1:]  # FETCH response header line
            for item in items:
                if isinstance(item, bytes) and item != b")":
                    chunks.append(item)
        elif isinstance(part, bytes) and part != b")":
            chunks.append(part)
    return b"".join(chunks)


def _escape_imap(text):
    return text.replace("\\", "\\\\").replace('"', '\\"')


def search_messages(http, apple_id, app_password, imap_factory=None,
                    query="", max_results=10):
    """Search INBOX. Returns From/Subject/Date/snippet per hit."""
    max_results = max(1, min(int(max_results), 20))
    conn = _imap_login(apple_id, app_password, imap_factory)
    try:
        conn.select("INBOX", readonly=True)
        if query:
            q = _escape_imap(query)
            criteria = '(OR SUBJECT "%s" FROM "%s")' % (q, q)
        else:
            criteria = "ALL"
        typ, data = conn.uid("SEARCH", None, criteria)
        if typ != "OK":
            raise RuntimeError("iCloud Mail SEARCH failed")
        uids = (data[0] or b"").split()
        messages = []
        for uid in reversed(uids[-max_results:]):
            typ, parts = conn.uid(
                "FETCH", uid,
                "(UID BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if typ != "OK":
                continue
            msg = email.message_from_bytes(
                _imap_bytes(parts), policy=email.policy.default)
            typ, parts = conn.uid("FETCH", uid, "(BODY.PEEK[TEXT]<0.512>)")
            snippet = ""
            if typ == "OK":
                text = _imap_bytes(parts).decode("utf-8", "replace")
                snippet = " ".join(text.split())[:SNIPPET_CAP]
            messages.append({
                "uid": uid.decode("ascii", "replace"),
                "from": str(msg.get("From", "")),
                "subject": str(msg.get("Subject", "")),
                "date": str(msg.get("Date", "")),
                "snippet": snippet,
            })
        return {"ok": True, "messages": messages}
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def _text_body(msg):
    """First text/plain part, attachments skipped, capped."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_disposition() in ("attachment",):
                continue
            if part.get_content_type() == "text/plain":
                try:
                    return part.get_content()
                except Exception:
                    return ""
        return ""
    try:
        return msg.get_content()
    except Exception:
        return ""


def get_message(http, apple_id, app_password, imap_factory=None, uid=None):
    """Full headers + text body (4000-char cap, attachments skipped)."""
    if not uid:
        raise ValueError("uid is required")
    conn = _imap_login(apple_id, app_password, imap_factory)
    try:
        conn.select("INBOX", readonly=True)
        uid_b = uid.encode("ascii") if isinstance(uid, str) else uid
        typ, parts = conn.uid("FETCH", uid_b, "(BODY.PEEK[])")
        if typ != "OK":
            raise RuntimeError("iCloud Mail FETCH failed for uid %s" % uid)
        raw = _imap_bytes(parts)
        if not raw:
            raise RuntimeError("iCloud Mail: no such message (uid %s)" % uid)
        msg = email.message_from_bytes(raw, policy=email.policy.default)
        body = " ".join(str(_text_body(msg)).split())
        return {"ok": True, "message": {
            "uid": str(uid),
            "from": str(msg.get("From", "")),
            "subject": str(msg.get("Subject", "")),
            "date": str(msg.get("Date", "")),
            "body": body[:BODY_CAP],
        }}
    finally:
        try:
            conn.logout()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# CalDAV (iCloud Calendar)
# ---------------------------------------------------------------------------

def _dav_time_range(time_min, time_max):
    now = datetime.datetime.now(datetime.timezone.utc)
    start = time_min or now
    end = time_max or (now + datetime.timedelta(days=30))
    if isinstance(start, str):
        start = datetime.datetime.fromisoformat(start)
    if isinstance(end, str):
        end = datetime.datetime.fromisoformat(end)
    fmt = "%Y%m%dT%H%M%SZ"
    return (start.strftime(fmt), end.strftime(fmt))


def list_events(http, apple_id, app_password, time_min=None, time_max=None,
                max_results=20):
    """Events across all iCloud calendars in the time window."""
    max_results = max(1, min(int(max_results), 50))
    start, end = _dav_time_range(time_min, time_max)
    calendars = _discover_collections(
        http, apple_id, app_password, CALDAV_BASE,
        "calendar-home-set", ("urn:ietf:params:xml:ns:caldav", "calendar"))
    if not calendars:
        return {"ok": True, "events": []}
    report = ("<?xml version=\"1.0\" encoding=\"utf-8\"?>"
              "<c:calendar-query xmlns:d=\"DAV:\" "
              "xmlns:c=\"urn:ietf:params:xml:ns:caldav\">"
              "<d:prop><d:getetag/><c:calendar-data/></d:prop>"
              "<c:filter><c:comp-filter name=\"VCALENDAR\">"
              "<c:comp-filter name=\"VEVENT\">"
              "<c:time-range start=\"%s\" end=\"%s\"/>"
              "</c:comp-filter></c:comp-filter></c:filter>"
              "</c:calendar-query>" % (start, end))
    events = []
    for cal_url in calendars:
        resp = _dav_request(http, "REPORT", cal_url, apple_id, app_password,
                            report, depth="1")
        try:
            root = ET.fromstring(resp)
        except ET.ParseError:
            continue
        for cdata in root.findall(
                ".//d:prop/c:calendar-data", _NS):
            if cdata.text:
                events.extend(_extract_vevents(cdata.text))
    events.sort(key=lambda e: e.get("start") or "")
    return {"ok": True, "events": events[:max_results]}


# ---------------------------------------------------------------------------
# CardDAV (iCloud Contacts)
# ---------------------------------------------------------------------------

def list_contacts(http, apple_id, app_password, max_results=50):
    """Name/email/phone per contact across all iCloud address books."""
    max_results = max(1, min(int(max_results), 200))
    books = _discover_collections(
        http, apple_id, app_password, CARDDAV_BASE,
        "addressbook-home-set",
        ("urn:ietf:params:xml:ns:carddav", "addressbook"))
    contacts = []
    propfind = ("<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                "<d:propfind xmlns:d=\"DAV:\" "
                "xmlns:card=\"urn:ietf:params:xml:ns:carddav\">"
                "<d:prop><d:getetag/><card:address-data/></d:prop>"
                "</d:propfind>")
    for book_url in books:
        resp = _dav_request(http, "PROPFIND", book_url, apple_id,
                            app_password, propfind, depth="1")
        try:
            root = ET.fromstring(resp)
        except ET.ParseError:
            continue
        for adata in root.findall(".//d:prop/card:address-data", _NS):
            if adata.text and "BEGIN:VCARD" in adata.text.upper():
                contacts.append(_parse_vcard(adata.text))
                if len(contacts) >= max_results:
                    return {"ok": True, "contacts": contacts}
    return {"ok": True, "contacts": contacts}


CAPABILITIES = {
    "search_messages": search_messages,
    "get_message": get_message,
    "list_events": list_events,
    "list_contacts": list_contacts,
}
