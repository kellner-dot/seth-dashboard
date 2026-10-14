#!/usr/bin/env python3
# voice-relay.py -- KaviBOT voice reverse-tunnel relay (PC side).
# Stdlib only. Binds 127.0.0.1:8092 (loopback ONLY; never on LAN).
# Exposed to the tailnet via `tailscale serve --https=8443` on the PC.
#
# Data plane: this VM cannot receive inbound connections, so the VM runs
# voice-tunnel-poller.py which long-polls GET /relay/poll. iPhone requests
# arriving here are queued; the poller picks them up, forwards them to the
# VM's KaviBOT API (127.0.0.1:8091), and POSTs the response to /relay/deliver,
# which completes the iPhone's waiting HTTP request. The KaviBOT API's own
# bearer auth is enforced end-to-end (the poller injects the voice caller
# bearer when the iPhone request carries none); this relay never sees or
# validates API secrets.
#
# Poll-channel auth: TOFU. The first poll presenting a non-empty
# X-Relay-Token pins that token (persisted in relay-pin.txt); later polls
# must match. Loudly logged. Re-pair by deleting relay-pin.txt + restart.
#
# Logs: method, path, status, ms only. Never headers, bodies, or tokens.
# ASCII only (Windows console safe).

import base64
import binascii
import json
import os
import queue
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

VERSION = "1.0.0"
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 8092
MAX_BODY = 25 * 1024 * 1024
IPHONE_WAIT_S = 120
POLL_DEFAULT_S = 40

HERE = os.path.dirname(os.path.abspath(__file__))
PIN_FILE = os.path.join(HERE, "relay-pin.txt")
LOG_FILE = os.path.join(HERE, "relay.log")

HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade",
}


def log(msg):
    line = "%s %s" % (time.strftime("%Y-%m-%dT%H:%M:%S"), msg)
    try:
        with open(LOG_FILE, "a", encoding="ascii", errors="replace") as f:
            f.write(line + "\n")
    except OSError:
        pass
    try:
        print(line, flush=True)
    except OSError:
        pass


class RelayState:
    def __init__(self):
        self.lock = threading.Lock()
        self.pending = []          # queued iPhone requests (FIFO)
        self.waiters = {}          # req_id -> {"event": Event, "resp": dict|None}
        self.pin = self._load_pin()

    def _load_pin(self):
        try:
            with open(PIN_FILE, "r", encoding="ascii") as f:
                pin = f.read().strip()
                if pin:
                    log("loaded pinned relay token (re-pair needs relay-pin.txt delete + restart)")
                    return pin
        except OSError:
            pass
        return None

    def check_token(self, token, src):
        """TOFU pin. Returns True if the poller is authorized."""
        token = (token or "").strip()
        if not token:
            return False
        with self.lock:
            if self.pin is None:
                self.pin = token
                try:
                    with open(PIN_FILE, "w", encoding="ascii") as f:
                        f.write(token + "\n")
                except OSError as e:
                    log("WARN: could not persist relay pin: %s" % e)
                log("PAIRED relay token (TOFU) from %s -- if this was not the VM poller, delete relay-pin.txt and restart" % src)
                return True
            return token == self.pin

    def enqueue(self, method, path, headers, body):
        req_id = uuid.uuid4().hex
        entry = {
            "id": req_id, "method": method, "path": path,
            "headers": headers, "body": body,
            "created": time.time(), "claimed": False,
        }
        ev = threading.Event()
        with self.lock:
            self.pending.append(entry)
            self.waiters[req_id] = {"event": ev, "resp": None}
        return req_id, ev

    def poll_next(self):
        """Claim the oldest unclaimed request. Returns entry or None."""
        with self.lock:
            for e in self.pending:
                if not e["claimed"]:
                    e["claimed"] = True
                    return e
        return None

    def deliver(self, req_id, status, headers, body):
        with self.lock:
            w = self.waiters.get(req_id)
            if not w:
                return False
            w["resp"] = {"status": status, "headers": headers, "body": body}
            w["event"].set()
            return True

    def drop(self, req_id):
        with self.lock:
            self.pending = [e for e in self.pending if e["id"] != req_id]
            self.waiters.pop(req_id, None)


STATE = RelayState()


def clean_headers(raw):
    """Drop hop-by-hop headers; return list of [name, value]."""
    out = []
    for k, v in raw:
        if k.lower() in HOP_BY_HOP:
            continue
        out.append([k, v])
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "KaviVoiceRelay/" + VERSION
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass  # we log our own one-liners

    # -- helpers ------------------------------------------------------
    def _send(self, status, body_bytes, ctype="application/json"):
        try:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body_bytes)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body_bytes)
        except (OSError, ConnectionError):
            pass

    def _json(self, status, obj):
        self._send(status, json.dumps(obj).encode("ascii"))

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except ValueError:
            length = 0
        if length > MAX_BODY:
            return None
        if length <= 0:
            return b""
        try:
            return self.rfile.read(length)
        except OSError:
            return b""

    def _poller_authed(self):
        token = self.headers.get("X-Relay-Token", "")
        src = self.client_address[0]
        if not STATE.check_token(token, src):
            self._json(403, {"error": "forbidden"})
            return False
        return True

    # -- relay control plane ------------------------------------------
    def _handle_relay(self, path, qs):
        if path == "/relay/health" and self.command == "GET":
            self._json(200, {"ok": True, "service": "kavi-voice-relay",
                             "version": VERSION})
            return True
        if path == "/relay/poll" and self.command == "GET":
            if not self._poller_authed():
                return True
            try:
                timeout = float((qs.get("timeout") or [POLL_DEFAULT_S])[0])
            except ValueError:
                timeout = POLL_DEFAULT_S
            timeout = max(1, min(timeout, 55))
            deadline = time.time() + timeout
            while time.time() < deadline:
                entry = STATE.poll_next()
                if entry:
                    payload = {
                        "id": entry["id"],
                        "method": entry["method"],
                        "path": entry["path"],
                        "headers": entry["headers"],
                        "body_b64": base64.b64encode(entry["body"]).decode("ascii"),
                    }
                    self._json(200, payload)
                    return True
                time.sleep(0.25)
            self._json(204, {})
            return True
        if path == "/relay/deliver" and self.command == "POST":
            if not self._poller_authed():
                return True
            body = self._read_body()
            if body is None:
                self._json(413, {"error": "body too large"})
                return True
            try:
                obj = json.loads(body.decode("utf-8"))
                req_id = obj["id"]
                status = int(obj.get("status", 502))
                headers = obj.get("headers", [])
                raw = base64.b64decode(obj.get("body_b64", ""))
            except (ValueError, KeyError, binascii.Error):
                self._json(400, {"error": "bad deliver payload"})
                return True
            ok = STATE.deliver(req_id, status, clean_headers(headers), raw)
            self._json(200 if ok else 404, {"ok": ok})
            return True
        return False

    # -- iPhone / data plane ------------------------------------------
    def _handle_proxy(self, path):
        if self.command not in ("GET", "POST", "HEAD"):
            self._json(405, {"error": "method not allowed"})
            return
        body = self._read_body()
        if body is None:
            self._json(413, {"error": "body too large"})
            return
        headers = clean_headers(list(self.headers.items()))
        req_id, ev = STATE.enqueue(self.command, path, headers, body)
        t0 = time.time()
        got = ev.wait(IPHONE_WAIT_S)
        ms = int((time.time() - t0) * 1000)
        with STATE.lock:
            w = STATE.waiters.get(req_id)
            resp = w["resp"] if w else None
        STATE.drop(req_id)
        if not got or resp is None:
            log("%s %s -> 504 timeout (%dms, id %s)" % (self.command, path, ms, req_id[:8]))
            self._json(504, {"error": "tunnel timeout: VM poller did not answer in time"})
            return
        status = resp["status"]
        log("%s %s -> %d (%dms, id %s)" % (self.command, path, status, ms, req_id[:8]))
        try:
            self.send_response(status)
            sent_ct = False
            for k, v in resp["headers"]:
                kl = k.lower()
                if kl in ("content-length", "connection", "transfer-encoding"):
                    continue
                if kl == "content-type":
                    sent_ct = True
                self.send_header(k, v)
            if not sent_ct:
                self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(resp["body"])))
            self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD" and resp["body"]:
                self.wfile.write(resp["body"])
        except (OSError, ConnectionError):
            pass

    def do_GET(self):
        self._route()

    def do_POST(self):
        self._route()

    def do_HEAD(self):
        self._route()

    def _route(self):
        parsed = urlparse(self.path)
        path = parsed.path or "/"
        qs = parse_qs(parsed.query)
        try:
            if path.startswith("/relay/"):
                if self._handle_relay(path, qs):
                    return
                self._json(404, {"error": "unknown relay path"})
                return
            self._handle_proxy(path)
        except (OSError, ConnectionError):
            pass
        except Exception as e:  # never leak internals
            log("ERROR route %s: %s" % (path, type(e).__name__))
            try:
                self._json(500, {"error": "relay error"})
            except OSError:
                pass


def main():
    srv = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    srv.daemon_threads = True
    log("kavi-voice-relay %s listening on %s:%d (loopback only)" % (VERSION, LISTEN_HOST, LISTEN_PORT))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
