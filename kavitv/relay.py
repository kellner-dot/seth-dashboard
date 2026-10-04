#!/usr/bin/env python3
"""KaviTV relay v1.0 — clean rewrite, no duct tape.

Architecture (validated against dizquetv / ErsatzTV / Tunarr, 2026-10-04):
  The relay OWNS ffmpeg. Emby is a dumb byte source via
  /emby/Videos/<id>/stream?static=true (original file, Range-capable,
  no transcode, no session). Per tune-in the relay spawns Emby's bundled
  ffmpeg with a SINGLE input -ss (plain seconds), stream-copy to MPEG-TS,
  and pipes stdout to the tuner as video/mp2t.

  Why not Emby HLS: Emby's variant playlist is gated on its transcode job
  producing segment 0; a seek (StartTimeTicks) restarts the transcode and
  the playlist request hangs FOREVER if ffmpeg wedges. Owning ffmpeg
  removes the HLS session machinery, PlaySessionId juggling, playlist
  parsing, double transcode, and unbounded waits in one move.

Endpoints:
  GET /kavitv/live/<id>  -> 200 video/mp2t, live MPEG-TS of current program
                             (id = horror | experimental | independent;
                              .m3u8 suffix accepted for M3U compat)
  GET /api/health        -> {ok, version, ffmpeg, date, channels, now}

Config (C:\\Users\\sethr\\kavitv\\config\\):
  emby.key       API key (written once via RVG; never logged)
  schedules.json {"date": "YYYY-MM-DD",
                  "channels": {"30": {"items": [{"ref": "emby:movie:<id>",
                    "title": ..., "start": "HH:MM", "end": "HH:MM"}, ...]}}}

Run: pythonw relay.py  (port 8100)
"""
import json
import os
import queue
import subprocess
import sys
import threading
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = r"C:\Users\sethr\kavitv"
CONFIG_DIR = os.path.join(BASE_DIR, "config")
KEY_FILE = os.path.join(CONFIG_DIR, "emby.key")
TIMELINE_FILE = os.path.join(CONFIG_DIR, "timeline.json")
FFMPEG = (r"C:\Users\sethr\AppData\Roaming\Emby-Server\system\ffmpeg.exe")
EMBY = "http://127.0.0.1:8096"          # relay runs ON the Emby box
VERSION = "1.2.0"

# slug -> timeline channel id
CHANNELS = {
    "horror": "kavitv.horror",
    "experimental": "kavitv.experimental",
    "independent": "kavitv.independent",
}

# Watchdog: if ffmpeg emits no bytes within this long, the tune is dead.
FIRST_BYTE_TIMEOUT = 12
CHUNK = 65536


def load_key():
    with open(KEY_FILE) as f:
        return f.read().strip()


def load_timeline():
    with open(TIMELINE_FILE) as f:
        return json.load(f)


def current_program(timeline, cid):
    """(slot, offset_sec) for what's airing now on timeline channel `cid`.

    Half-open: start <= now < end. SLACK=10s at boundaries: if within
    10s of a slot's end, advance to the next slot at offset 0.
    """
    slots = timeline["channels"][cid]["slots"]
    now = datetime.now(timezone.utc)
    lo, hi = 0, len(slots) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        s = datetime.fromisoformat(slots[mid]["start"])
        e = datetime.fromisoformat(slots[mid]["end"])
        if e <= now:
            lo = mid + 1
        elif s > now:
            hi = mid - 1
        else:
            if (e - now).total_seconds() < 10 and mid + 1 < len(slots):
                return slots[mid + 1], 0.0
            dur = (e - s).total_seconds()
            offset = max(0.0, min((now - s).total_seconds(), dur - 10.0))
            return slots[mid], offset
    return None, 0.0


def static_url(item_id, api_key):
    q = urllib.parse.urlencode({"static": "true", "api_key": api_key})
    return f"{EMBY}/emby/Videos/{item_id}/stream?{q}"


def spawn_ffmpeg(src_url, offset_sec):
    """Start ffmpeg: input-seek, stream-copy, MPEG-TS to stdout pipe."""
    cmd = [
        FFMPEG,
        "-hide_banner", "-nostats", "-loglevel", "error",
        "-fflags", "+genpts+discardcorrupt+igndts",
        "-ss", f"{offset_sec:.1f}",
        "-i", src_url,
        "-map", "0:v:0", "-map", "0:a:0",
        "-c:v", "copy", "-c:a", "copy",
        # Reset timestamps to start at zero after seek (prevents player
        # confusion from non-zero start timestamps in stream-copy mode)
        "-copyts", "-start_at_zero",
        "-f", "mpegts",
        "-mpegts_flags", "resend_headers",
        "-flush_packets", "1",
        "pipe:1",
    ]
    return subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL)


def stop_ffmpeg(proc):
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


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

    def _now_map(self, tl):
        out = {}
        for slug, cid in CHANNELS.items():
            try:
                slot, off = current_program(tl, cid)
            except Exception:
                slot, off = None, 0.0
            out[slug] = {"title": slot["title"] if slot else None,
                         "offset_sec": round(off, 1)}
        return out

    def _serve_ffmpeg(self, src, offset_sec):
        """Stream ffmpeg's MPEG-TS output to the client.

        Raises TimeoutError if no bytes arrive promptly, RuntimeError
        if ffmpeg exits early. Caller decides whether to retry.
        """
        proc = spawn_ffmpeg(src, offset_sec)
        # Pump stdout through a queue so the watchdog can time out on
        # Windows (select() doesn't work on pipes there).
        q: "queue.Queue" = queue.Queue()

        def _pump():
            try:
                while True:
                    chunk = proc.stdout.read(CHUNK)
                    q.put(chunk if chunk else None)
                    if not chunk:
                        break
            except Exception as e:  # noqa: BLE001
                q.put(e)

        threading.Thread(target=_pump, daemon=True).start()
        try:
            try:
                first = q.get(timeout=FIRST_BYTE_TIMEOUT)
            except queue.Empty:
                raise TimeoutError("ffmpeg produced no output")
            if first is None or isinstance(first, Exception):
                raise RuntimeError("ffmpeg exited early")
            self.send_response(200)
            self.send_header("Content-Type", "video/mp2t")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(first)
            self.wfile.flush()
            while True:
                chunk = q.get()
                if chunk is None or isinstance(chunk, Exception):
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # tuner went away; normal
        finally:
            stop_ffmpeg(proc)

    def do_GET(self):
        try:
            path = urllib.parse.urlsplit(self.path).path
            if path == "/api/health":
                try:
                    tl = load_timeline()
                    now = self._now_map(tl)
                    gen = tl.get("generated_at")
                    chs = sorted(tl["channels"].keys())
                    # date for backward compat (kavi2 supervisor expects YYYY-MM-DD)
                    try:
                        date_str = gen[:10] if gen else None
                    except Exception:
                        date_str = None
                except FileNotFoundError:
                    now, gen, chs, date_str = {}, None, [], None
                return self._json(200, {
                    "ok": True, "version": VERSION,
                    "ffmpeg": os.path.exists(FFMPEG),
                    "generated_at": gen,
                    "date": date_str,  # backward compat for supervisors
                    "channels": chs, "now": now,
                })
            if path.startswith("/kavitv/live/"):
                slug = path.split("/")[3].split(".")[0]
                cid = CHANNELS.get(slug)
                if not cid:
                    return self._json(400, {"error": "bad channel"})
                tl = load_timeline()
                slot, offset_sec = current_program(tl, cid)
                if not slot:
                    return self._json(404, {"error": "nothing scheduled"})
                item_id = slot["emby_id"]
                api_key = load_key()
                src = static_url(item_id, api_key)

                # Try at the computed offset; if ffmpeg fails (bad seek,
                # duration mismatch), retry once from the beginning.
                # Never serve a 502 if offset 0 works.
                last_err = None
                for attempt, off in enumerate([offset_sec, 0.0]):
                    if attempt == 1 and offset_sec == 0.0:
                        break
                    try:
                        self._serve_ffmpeg(src, off)
                        return
                    except (TimeoutError, RuntimeError) as e:
                        last_err = e
                        if attempt == 0 and offset_sec > 1.0:
                            continue
                        raise
                raise last_err if last_err else RuntimeError("no attempts")
            return self._json(404, {"error": "not found"})
        except FileNotFoundError as e:
            return self._json(503, {"error": "not configured",
                                    "detail": str(e)})
        except (TimeoutError, RuntimeError) as e:
            return self._json(502, {"error": "transcode failed",
                                    "detail": str(e)[:200]})
        except Exception as e:  # relay must never die on a bad request
            return self._json(500, {"error": "internal",
                                    "detail": str(e)[:200]})


def main():
    port = 8100
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    if not os.path.exists(FFMPEG):
        print(f"FATAL: ffmpeg not found at {FFMPEG}", flush=True)
        sys.exit(2)
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"KaviTV relay {VERSION} on :{port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
