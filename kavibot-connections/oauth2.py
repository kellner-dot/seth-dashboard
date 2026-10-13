#!/usr/bin/env python3
"""Shared OAuth 2.0 handler for the connections layer.

Authorization-code flow with PKCE + ephemeral 127.0.0.1 loopback listener.
Stdlib only (urllib / http.server) so it runs on the PC's plain Python.

All network goes through an injectable `http` adapter (default: urllib) so
tests can mock the provider without touching the network. Token VALUES are
never logged here.
"""
import base64
import hashlib
import json
import secrets
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer


class OAuthError(RuntimeError):
    pass


class UrllibHttp:
    """Default HTTP adapter: POST/GET with form or JSON bodies."""

    def post(self, url, data, headers=None):
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")

    def get(self, url, headers=None):
        req = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")


def _pkce_pair():
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - http.server naming
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        self.server.captured = {
            "code": (params.get("code") or [None])[0],
            "state": (params.get("state") or [None])[0],
            "error": (params.get("error") or [None])[0],
        }
        body = (b"<html><body style='font-family:sans-serif'>"
                b"<h3>KaviBOT connected.</h3>"
                b"<p>You can close this window and return to the setup.</p>"
                b"</body></html>")
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.server.got_callback.set()

    def log_message(self, *args):
        pass  # never log the callback line (it carries the code)


class OAuth2Flow:
    def __init__(self, spec, http=None):
        self.spec = spec
        self.oauth = spec["oauth"]
        self.http = http or UrllibHttp()

    # -- step 1: build the consent URL -------------------------------------
    def authorization_url(self, client_id, redirect_uri, state=None,
                          code_challenge=None, extra=None):
        if state is None:
            state = secrets.token_urlsafe(16)
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.oauth["scopes"]),
            "state": state,
        }
        if self.oauth.get("use_pkce"):
            if not code_challenge:
                raise OAuthError("PKCE required but no code_challenge given")
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
        params.update(self.oauth.get("extra_auth_params", {}))
        params.update(extra or {})
        return (self.oauth["auth_url"] + "?" + urllib.parse.urlencode(params),
                state)

    # -- step 2: catch the loopback redirect --------------------------------
    def wait_for_code(self, timeout=300):
        """Bind an ephemeral 127.0.0.1 port; return (port, (code, state)).

        Raises OAuthError on timeout or provider error. The listener shuts
        down after the first callback.
        """
        server = HTTPServer(("127.0.0.1", 0), _CallbackHandler)
        server.got_callback = threading.Event()
        server.captured = None
        port = server.server_address[1]
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()
        if not server.got_callback.wait(timeout):
            server.server_close()
            raise OAuthError("timed out waiting for the browser callback")
        server.server_close()
        captured = server.captured or {}
        if captured.get("error"):
            raise OAuthError("provider refused: %s" % captured["error"])
        if not captured.get("code"):
            raise OAuthError("no authorization code in callback")
        return port, captured["code"], captured["state"]

    # -- step 3: code -> tokens --------------------------------------------
    def exchange_code(self, code, client_id, client_secret, redirect_uri,
                      code_verifier=None):
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
        }
        if client_secret:
            data["client_secret"] = client_secret
        if code_verifier:
            data["code_verifier"] = code_verifier
        return self._token_request(data, client_id, client_secret)

    # -- refresh ------------------------------------------------------------
    def refresh(self, client_id, client_secret, refresh_token):
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        }
        if client_secret:
            data["client_secret"] = client_secret
        return self._token_request(data, client_id, client_secret)

    def _token_request(self, data, client_id=None, client_secret=None):
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        # Some providers (Login with Amazon) expect client auth via
        # HTTP Basic instead of POST body parameters.
        if self.oauth.get("token_auth") == "basic" and client_id is not None:
            raw = ("%s:%s" % (client_id, client_secret or "")).encode("utf-8")
            headers["Authorization"] = ("Basic " +
                                        base64.b64encode(raw).decode("ascii"))
            data = {k: v for k, v in data.items()
                    if k not in ("client_id", "client_secret")}
        status, body = self.http.post(self.oauth["token_url"], data, headers)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            raise OAuthError("token endpoint returned non-JSON (http %s)" % status)
        if status != 200 or "access_token" not in payload:
            raise OAuthError("token request failed: %s" %
                             payload.get("error_description",
                                         payload.get("error", "http %s" % status)))
        return payload
