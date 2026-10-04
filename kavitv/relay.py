#!/usr/bin/env python3
"""KaviTV relay — LAN-side HTTP service on SETHS-PC (stdlib only).

Why it exists: the M3U playlist (kavitv.m3u on GitHub Pages) is public and
credential-free. Each channel entry points here; the relay resolves the
channel's CURRENT program and serves Emby's HLS media playlist for it.

v0.3.0: full server-side HLS resolution. The relay mints a PlaySessionId,
fetches Emby's master playlist, follows to the media playlist, and returns
it with absolute segment URLs. Emby echoes the client-supplied PlaySessionId
into every segment URL — without it, segments come back with a blank
PlaySessionId and Emby 400s them, so playback can never start. (v0.2.0
proxied only the master playlist; the media playlist it pointed at still
carried a blank session.)

Endpoints:
  GET /kavitv/live/<id>.m3u8   -> 200 with the current program's HLS media
                                  playlist (id = horror | experimental |
                                  independent)
  GET /api/health              -> {ok, version, date, channels}

Config: C:\\Users\\sethr\\kavitv\\config\\emby.key      (API key, written once by
        the VM via RVG; file ACL restricted to Seth; never logged)
        C:\\Users\\sethr\\kavitv\\config\\schedules.json (pushed by the VM via
        RVG; {"date": "YYYY-MM-DD", "channels": {"30": {"items": [...]}, ...}})

Run: python relay.py [--port 8100]
Persist: Task Scheduler at logon, or `pythonw relay.py` (see DEPLOY.md).
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = r"C:\Users\sethr\kavitv"
CONFIG_DIR = os.path.join(BASE_DIR, "config")
KEY_FILE = os.path.join(CONFIG_DIR, "emby.key")
SCHEDULE_FILE = os.path.join(CONFIG_DIR, "schedules.json")
EMBY_HOST = "http://127.0.0.1:8096"  # relay runs ON the Emby box
LAN_HOST = "10.0.0.98"               # this box's LAN address for players
VERSION = "0.3.1"

CHANNELS = {"horror": "30", "experimental": "31", "independent": "32"}


def load_key():
    with open(KEY_FILE) as f:
        return f.read().strip()


def load_schedule():
    with open(SCHEDULE_FILE) as f:
        return json.load(f)


def now_local():
    return datetime.now()


def item_abs(date_str, hhmm):
    """Broadcast-day HH:MM (day runs 06:00 -> 06:00) -> local datetime."""
    h, m = (int(x) for x in hhmm.split(":"))
    d = datetime.strptime(date_str, "%Y-%m-%d")
    if h < 6:
        d += timedelta(days=1)
    return d.replace(hour=h, minute=m, second=0, microsecond=0)


def current_program(sched, key):
    """(item, offset_ms) for what's airing now on schedule channel `key`."""
    date_str = sched["date"]
    items = sched["channels"][key]["items"]
    now = now_local()
    for it in items:
        s = item_abs(date_str, it["start"])
        e = item_abs(date_str, it["end"])
        if e <= s:
            e += timedelta(days=1)
        if s <= now < e:
            offset_ms = int((now - s).total_seconds() * 1000)
            return it, offset_ms
    return None, 0


def with_query_param(url, name, value):
    parts = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    q = [(k, v) for (k, v) in q if k.lower() != name.lower()]
    q.append((name, value))
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path,
         urllib.parse.urlencode(q), parts.fragment))


def emby_master_url(item_id, offset_ms, key, session_id):
    ticks = int(offset_ms * 10000)
    q = urllib.parse.urlencode({
        "api_key": key,
        "PlaySessionId": session_id,
        "StartTimeTicks": ticks,
        "VideoCodec": "h264",
        "AudioCodec": "aac",
        "MaxStreamingBitrate": 12000000,
    })
    return f"http://{LAN_HOST}:8096/emby/Videos/{item_id}/master.m3u8?{q}"


def fetch_text(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": "KaviTV-relay/" + VERSION})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read().decode("utf-8", errors="replace")


def absolutize(url, base):
    if "://" in url:
        return url
    if url.startswith("/"):
        parts = urllib.parse.urlsplit(base)
        return f"{parts.scheme}://{parts.netloc}{url}"
    return base + url


def rewrite_playlist(body, base):
    """Make every segment/key/map URI absolute against `base`.

    Also strips #EXT-X-START: Emby emits TIME-OFFSET relative to the full
    movie, but the playlist we serve starts AT the offset already — a player
    honoring the hint seeks past the end of the playlist and shows nothing.
    """
    out = []
    for line in body.splitlines():
        s = line.strip()
        if not s:
            out.append(line)
            continue
        if s.startswith("#EXT-X-START"):
            continue
        if s.startswith("#"):
            s = re.sub(r'URI="([^"]+)"',
                       lambda m: 'URI="' + absolutize(m.group(1), base) + '"',
                       s)
            out.append(s)
        else:
            out.append(absolutize(s, base))
    return "\n".join(out) + "\n"


def resolve_media_playlist(master_url, session_id):
    """Follow master -> media playlist; return rewritten media playlist text.

    Raises on any fetch/parse failure.
    """
    master = fetch_text(master_url)
    variant = None
    for line in master.splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            variant = s
            break
    if not variant:
        raise ValueError("master playlist has no variant")
    vurl = absolutize(variant, master_url.rsplit("/", 1)[0] + "/")
    vurl = with_query_param(vurl, "PlaySessionId", session_id)
    media = fetch_text(vurl)
    if "#EXT-X-STREAM-INF" in media:
        # Unexpected second master level; hand it back with session attached.
        return rewrite_playlist(
            media, vurl.rsplit("/", 1)[0] + "/")
    base = vurl.rsplit("/", 1)[0] + "/"
    return rewrite_playlist(media, base)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            path = urllib.parse.urlsplit(self.path).path
            if path == "/api/health":
                try:
                    sched = load_schedule()
                    chs = list(sched["channels"].keys())
                    ds = sched["date"]
                except FileNotFoundError:
                    chs, ds = [], None
                return self._json(200, {"ok": True, "version": VERSION,
                                       "date": ds, "channels": chs})
            if path.startswith("/kavitv/live/") and path.endswith(".m3u8"):
                cid = path.split("/")[3].split(".")[0]
                key = CHANNELS.get(cid)
                if not key:
                    return self._json(400, {"error": "bad channel"})
                sched = load_schedule()
                item, offset_ms = current_program(sched, key)
                if not item:
                    return self._json(404, {"error": "nothing scheduled"})
                ref = item.get("ref", "")
                item_id = ref.split(":")[-1]  # ref = "emby:movie:<itemId>"
                session_id = uuid.uuid4().hex
                master_url = emby_master_url(item_id, offset_ms,
                                             load_key(), session_id)
                try:
                    body = resolve_media_playlist(master_url, session_id)
                except Exception as e:
                    return self._json(502, {"error": "emby fetch failed",
                                           "detail": str(e)[:200]})
                data = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type",
                                 "application/vnd.apple.mpegurl")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(data)
                return
            return self._json(404, {"error": "not found"})
        except FileNotFoundError as e:
            return self._json(503, {"error": "not configured",
                                    "detail": str(e)})
        except Exception as e:  # relay must never die on a bad request
            return self._json(500, {"error": "internal",
                                    "detail": str(e)[:200]})


def main():
    port = 8100
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"KaviTV relay {VERSION} on :{port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
