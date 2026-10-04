#!/usr/bin/env python3
"""SethTV relay — LAN-side HTTP service on SETHS-PC (stdlib only).

Why it exists: the Fire TV Stick (Vega OS, home LAN) cannot reach the VM that
builds the schedules, and the Emby API key must never ship in a public web
page. The relay runs on SETHS-PC (10.0.0.98), holds the Emby key server-side,
and hands the TV app ready-to-play HLS URLs.

Endpoints (all JSON unless noted):
  GET /api/health                       -> {ok, version, channels, generated_at}
  GET /api/guide                        -> now/next for every channel (TV guide)
  GET /api/schedule                     -> full 7-day schedule
  GET /api/tune?channel=<n>             -> {hls_url, program, offset_ms, ...}
                                          hls_url is an Emby master.m3u8 with
                                          StartTimeTicks = the live edge.
  GET /api/img/<itemId>                 -> proxied Emby primary image (key added
                                          server-side so the key never leaks)
  GET /epg.xml                          -> XMLTV EPG
  HDHomeRun emulation (PHASE 2 - stubbed):
  GET /discover.json /lineup.json /lineup_status.json /device.xml
                                          -> 501 {error: phase_2}

Config: C:\\Users\\sethr\\sethtv\\config\\emby.key  (API key, written once by the
        VM via RVG; file ACL restricted to Seth; never logged)
        C:\\Users\\sethr\\sethtv\\config\\schedule.json (pushed by the VM)

Run: python3 relay.py [--port 8099]
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = r"C:\Users\sethr\sethtv"
CONFIG_DIR = os.path.join(BASE_DIR, "config")
KEY_FILE = os.path.join(CONFIG_DIR, "emby.key")
SCHEDULE_FILE = os.path.join(CONFIG_DIR, "schedule.json")
EMBY_HOST = "http://127.0.0.1:8096"  # relay runs ON the Emby box
VERSION = "0.1.0"


def load_key():
    with open(KEY_FILE) as f:
        return f.read().strip()


def load_schedule():
    with open(SCHEDULE_FILE) as f:
        return json.load(f)


def now_ms():
    return int(time.time() * 1000)


def slot_now_next(slots, at):
    import bisect
    starts = [s["start_ms"] for s in slots]
    i = bisect.bisect_right(starts, at) - 1
    if i < 0:
        return None, slots[0] if slots else None
    cur = dict(slots[i])
    cur["offset_ms"] = max(0, at - slots[i]["start_ms"])
    nxt = slots[i + 1] if i + 1 < len(slots) else None
    return cur, nxt


def tune_target(slots, at):
    cur, nxt = slot_now_next(slots, at)
    if cur and cur["kind"] == "program":
        return cur
    s = nxt
    starts = [x["start_ms"] for x in slots]
    import bisect
    while s and s["kind"] != "program":
        i = bisect.bisect_right(starts, s["start_ms"])
        s = slots[i] if i < len(slots) else None
    if s:
        r = dict(s)
        r["offset_ms"] = 0
        return r
    return None


def emby_hls_url(item_id, offset_ms, key):
    ticks = int(offset_ms * 10000)
    q = urllib.parse.urlencode({
        "api_key": key,
        "StartTimeTicks": ticks,
        "VideoCodec": "h264",
        "AudioCodec": "aac",
        "MaxStreamingBitrate": 12000000,
    })
    # LAN address of this box so the Fire Stick can reach it.
    return f"http://10.0.0.98:8096/emby/Videos/{item_id}/master.m3u8?{q}"


def program_info(slot):
    item = slot.get("item") or {}
    return {
        "title": item.get("name") or slot.get("title"),
        "series": item.get("series"),
        "season": item.get("season"),
        "episode": item.get("episode"),
        "year": item.get("year"),
        "genres": item.get("genres", []),
        "overview": item.get("overview"),
        "rating": item.get("rating"),
        "item_id": item.get("id"),
        "start_ms": slot["start_ms"],
        "stop_ms": slot["stop_ms"],
        "offset_ms": slot.get("offset_ms", 0),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "SethTV-Relay/" + VERSION

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[{datetime.now(timezone.utc).isoformat()}] {fmt % args}\n")

    def _send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj))

    def do_GET(self):
        try:
            u = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(u.query)
            path = u.path
            if path == "/api/health":
                sched = load_schedule()
                return self._json(200, {"ok": True, "version": VERSION,
                                        "channels": len(sched["channels"]),
                                        "generated_at_ms": sched["generated_at_ms"]})
            if path == "/api/guide":
                return self._json(200, self.guide())
            if path == "/api/schedule":
                return self._json(200, load_schedule())
            if path == "/api/tune":
                return self._json(200, self.tune(q))
            if path.startswith("/api/img/"):
                return self.proxy_img(path.rsplit("/", 1)[-1])
            if path == "/epg.xml":
                return self.epg()
            if path in ("/discover.json", "/lineup.json", "/lineup_status.json", "/device.xml"):
                return self._json(501, {"error": "phase_2",
                                        "detail": "HDHomeRun emulation lands in phase 2. See README."})
            return self._json(404, {"error": "not found"})
        except FileNotFoundError as e:
            return self._json(503, {"error": "not configured", "detail": str(e)})
        except Exception as e:  # noqa: BLE001 - relay must never die on a bad request
            return self._json(500, {"error": "internal", "detail": str(e)[:200]})

    def guide(self):
        sched = load_schedule()
        at = now_ms()
        out = {"at_ms": at, "channels": []}
        for ch in sched["channels"]:
            cur, nxt = slot_now_next(ch["slots"], at)
            out["channels"].append({
                "id": ch["id"], "number": ch["number"], "name": ch["name"],
                "tagline": ch.get("tagline"),
                "now": program_info(cur) if cur else None,
                "now_kind": cur["kind"] if cur else None,
                "next": program_info(nxt) if nxt else None,
            })
        return out

    def tune(self, q):
        num = int(q.get("channel", ["1"])[0])
        sched = load_schedule()
        ch = next((c for c in sched["channels"] if c["number"] == num), None)
        if not ch:
            return {"error": f"no channel {num}"}
        slot = tune_target(ch["slots"], now_ms())
        if not slot:
            return {"error": "nothing scheduled"}
        key = load_key()
        item = slot["item"]
        return {
            "channel": {"id": ch["id"], "number": ch["number"], "name": ch["name"]},
            "program": program_info(slot),
            "hls_url": emby_hls_url(item["id"], slot.get("offset_ms", 0), key),
            "note": "live edge: playback starts where the schedule says it should be",
        }

    def proxy_img(self, item_id):
        if not item_id.replace("-", "").replace("_", "").isalnum():
            return self._json(400, {"error": "bad item id"})
        key = load_key()
        url = f"{EMBY_HOST}/emby/Items/{item_id}/Images/Primary?maxWidth=400&api_key={key}"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                data = r.read()
            self._send(200, data, r.headers.get("Content-Type", "image/jpeg"))
        except Exception as e:  # noqa: BLE001
            self._json(502, {"error": "image fetch failed", "detail": str(e)[:120]})

    def epg(self):
        # EPG XML is generated by the VM engine; relay serves the pushed copy.
        epg_path = os.path.join(CONFIG_DIR, "epg.xml")
        with open(epg_path, "rb") as f:
            data = f.read()
        self._send(200, data, "application/xml")


def main():
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8099
    for p in (KEY_FILE, SCHEDULE_FILE):
        if not os.path.exists(p):
            sys.stderr.write(f"missing {p} — run the VM deploy script first\n")
            sys.exit(2)
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"SethTV relay {VERSION} on :{port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
