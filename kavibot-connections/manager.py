#!/usr/bin/env python3
"""ConnectionManager: the single surface for the connections layer.

  status(name)                 -> connection state (no secrets, ever)
  connect(name)                -> interactive OAuth2 connect (oauth2 type)
  disconnect(name)             -> revoke local credentials
  call(name, capability, **p)  -> invoke a capability (oauth2 type)
  import_file(name, path)       -> run a file import (file_import type)

If a connection isn't set up, call/import_file return a structured
`not_connected` / `not_imported` error with setup instructions - they never
invent data.
"""
import getpass
import importlib
import os
import time
import webbrowser

from connection import load_registry, AuthError
from oauth2 import OAuth2Flow, OAuthError, UrllibHttp, _pkce_pair
from secret_store import SecretStore, default_backend

BASE = os.path.dirname(os.path.abspath(__file__))

NOT_CONNECTED_MSG = {
    "gcal": ("Google Calendar isn't connected yet. Run: "
             "kavibot-connect.py connect gcal"),
    "gmail": ("Gmail isn't connected yet. Run: "
              "kavibot-connect.py connect gmail"),
    "drive": ("Google Drive isn't connected yet. Run: "
              "kavibot-connect.py connect drive"),
    "apple_music": ("No Apple Music library imported yet. Export it "
                    "(File > Library > Export Library) then run: "
                    "kavibot-connect.py import apple_music <Library.xml>"),
    "icloud": ("iCloud isn't connected yet. Generate an app-specific "
               "password at appleid.apple.com (Sign-In and Security -> "
               "App-Specific Passwords), then run: "
               "kavibot-connect.py connect icloud"),
}


def _module_for(name):
    return importlib.import_module(name)


class ConnectionManager:
    def __init__(self, registry_path=None, store=None, http=None,
                 profile_dir=None):
        self.specs = load_registry(registry_path or
                                   os.path.join(BASE, "connections.json"))
        self.store = store or SecretStore(default_backend(BASE))
        self.http = http or UrllibHttp()
        self.profile_dir = profile_dir or os.path.join(BASE, "profiles")

    # -- status ---------------------------------------------------------
    def status(self, name):
        spec = self._spec(name)
        if spec["type"] == "oauth2":
            connected = self.store.has(name, "refresh_token")
            return {"ok": True, "name": name, "type": "oauth2",
                    "connected": connected,
                    "scopes": spec["oauth"]["scopes"],
                    "capabilities": spec["capabilities"]}
        imported = self.store.has(name, "profile_path")
        if spec["type"] == "app_password":
            connected = self.store.has(name, "app_password")
            return {"ok": True, "name": name, "type": "app_password",
                    "connected": connected,
                    "capabilities": spec["capabilities"]}
        return {"ok": True, "name": name, "type": "file_import",
                "connected": imported,
                "capabilities": spec["capabilities"]}

    def list_all(self):
        return [self.status(n) for n in self.specs]

    # -- app-password connect ---------------------------------------------
    def connect_app_password(self, name, spec):
        """Apple-ID style connect: id via input, password via getpass.

        Saves both to the vault, then verifies with a cheap IMAP login.
        A rejected password is deleted, never kept."""
        apple_id = self._get_or_prompt(name, "apple_id",
                                       "Apple ID (email)", secret=False)
        if not apple_id:
            return {"ok": False, "error": "cancelled",
                    "message": "No Apple ID entered; nothing saved."}
        app_password = getpass.getpass(
            "App-specific password (appleid.apple.com -> Sign-In and "
            "Security -> App-Specific Passwords): ").strip()
        if not app_password:
            return {"ok": False, "error": "cancelled",
                    "message": "No password entered; nothing saved."}
        self.store.put(name, "apple_id", apple_id)
        self.store.put(name, "app_password", app_password)
        module = _module_for(name)
        try:
            module.verify(apple_id, app_password)
        except AuthError as exc:
            self.store.delete(name, "app_password")
            return {"ok": False, "error": "auth_failed",
                    "message": "%s The bad password was discarded; "
                               "generate a fresh one and retry." % exc}
        except Exception as exc:  # network blip: keep creds, warn honestly
            return {"ok": True, "warning": "unverified",
                    "message": ("%s saved, but the check login could not "
                                "reach iCloud (%s). The first call will "
                                "confirm the password.") % (spec["display"],
                                                            exc)}
        return {"ok": True,
                "message": "%s connected." % spec["display"]}

    # -- oauth2 connect ---------------------------------------------------
    def connect(self, name):
        """Interactive connect. Secrets via prompt only, never CLI args."""
        spec = self._spec(name)
        if spec["type"] == "app_password":
            return self.connect_app_password(name, spec)
        if spec["type"] != "oauth2":
            return {"ok": False, "error": "wrong_type",
                    "message": "%s is not an OAuth connection" % name}
        client_id = self._get_or_prompt(name, "client_id",
                                        "Client ID", secret=False)
        client_secret = self._get_or_prompt(name, "client_secret",
                                            "Client secret (Enter if none)",
                                            secret=True)
        flow = OAuth2Flow(spec, self.http)
        verifier, challenge = _pkce_pair() if spec["oauth"].get("use_pkce") \
            else (None, None)
        # Ephemeral loopback listener first, so we know the redirect URI.
        import threading
        from http.server import HTTPServer
        from oauth2 import _CallbackHandler
        server = HTTPServer(("127.0.0.1", 0), _CallbackHandler)
        server.got_callback = threading.Event()
        server.captured = None
        port = server.server_address[1]
        redirect_uri = "http://127.0.0.1:%d/callback" % port
        auth_url, state = flow.authorization_url(
            client_id, redirect_uri, code_challenge=challenge)
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()
        try:
            webbrowser.open(auth_url)
        except Exception:
            pass
        print("A browser window should have opened. If not, visit:\n%s\n"
              % auth_url)
        print("Waiting for you to approve in the browser...")
        if not server.got_callback.wait(300):
            server.server_close()
            return {"ok": False, "error": "timeout",
                    "message": "No approval received within 5 minutes."}
        server.server_close()
        captured = server.captured or {}
        if captured.get("error") or not captured.get("code"):
            return {"ok": False, "error": "denied",
                    "message": "Authorization was not granted."}
        if captured.get("state") != state:
            return {"ok": False, "error": "state_mismatch",
                    "message": "State mismatch - possible CSRF, aborting."}
        try:
            tokens = flow.exchange_code(
                captured["code"], client_id, client_secret or None,
                redirect_uri, code_verifier=verifier)
        except OAuthError as exc:
            return {"ok": False, "error": "token_exchange_failed",
                    "message": str(exc)}
        self._save_tokens(name, tokens)
        # Optional per-connection API keys (e.g. x-api-key for LWA-style).
        for header, item in spec["oauth"].get("api_headers", {}).items():
            if not self.store.has(name, item):
                val = getpass.getpass("API credential for %s (%s): "
                                      % (name, header))
                if val:
                    self.store.put(name, item, val)
        return {"ok": True,
                "message": "%s connected." % spec["display"]}

    def _get_or_prompt(self, name, item, prompt, secret):
        if self.store.has(name, item):
            return self.store.get(name, item)
        val = (getpass.getpass(prompt + ": ") if secret
               else input(prompt + ": ")).strip()
        if val:
            self.store.put(name, item, val)
        return val or None

    def _save_tokens(self, name, tokens):
        if tokens.get("refresh_token"):
            self.store.put(name, "refresh_token", tokens["refresh_token"])
        self.store.put(name, "access_token", tokens["access_token"])
        expires_in = int(tokens.get("expires_in") or 3600)
        self.store.put(name, "expires_at", str(int(time.time()) + expires_in))

    # -- disconnect -------------------------------------------------------
    def disconnect(self, name):
        spec = self._spec(name)
        items = ["client_id", "client_secret", "access_token",
                 "refresh_token", "expires_at", "profile_path",
                 "apple_id", "app_password"]
        items += list(spec.get("oauth", {}).get("api_headers", {}).values())
        for item in items:
            self.store.delete(name, item)
        return {"ok": True, "message": "%s disconnected; local credentials "
                                       "removed." % spec["display"]}

    # -- capability calls ---------------------------------------------------
    def call(self, name, capability, **params):
        spec = self._spec(name)
        ctype = spec["type"]
        if ctype not in ("oauth2", "app_password"):
            return {"ok": False, "error": "wrong_type",
                    "message": "%s has no live capabilities" % name}
        if capability not in spec["capabilities"]:
            return {"ok": False, "error": "unknown_capability",
                    "message": "Unknown capability %r for %s"
                               % (capability, name)}
        if ctype == "app_password":
            return self._call_app_password(name, spec, capability, params)
        if not self.store.has(name, "refresh_token"):
            return {"ok": False, "error": "not_connected",
                    "message": NOT_CONNECTED_MSG.get(
                        name, "Not connected. Run: kavibot-connect.py "
                              "connect %s" % name)}
        try:
            access = self._fresh_access_token(name, spec)
            headers = self._api_headers(name, spec)
            module = _module_for(name)
            func = module.CAPABILITIES[capability]
            result = func(self.http, access, headers=headers, **params)
            if isinstance(result, dict):
                result.setdefault("ok", True)
            return result
        except OAuthError as exc:
            return {"ok": False, "error": "auth_failed",
                    "message": "Re-authorization needed: %s" % exc}
        except Exception as exc:  # provider errors stay structured
            return {"ok": False, "error": "provider_error",
                    "message": "%s" % exc}

    def _call_app_password(self, name, spec, capability, params):
        if not (self.store.has(name, "apple_id")
                and self.store.has(name, "app_password")):
            return {"ok": False, "error": "not_connected",
                    "message": NOT_CONNECTED_MSG.get(
                        name, "Not connected. Run: kavibot-connect.py "
                              "connect %s" % name)}
        try:
            module = _module_for(name)
            func = module.CAPABILITIES[capability]
            result = func(self.http,
                          self.store.get(name, "apple_id"),
                          self.store.get(name, "app_password"),
                          **params)
            if isinstance(result, dict):
                result.setdefault("ok", True)
            return result
        except AuthError as exc:
            return {"ok": False, "error": "auth_failed",
                    "message": "%s" % exc}
        except Exception as exc:  # provider errors stay structured
            return {"ok": False, "error": "provider_error",
                    "message": "%s" % exc}

    def _fresh_access_token(self, name, spec):
        try:
            expires_at = int(self.store.get(name, "expires_at"))
        except Exception:
            expires_at = 0
        if time.time() < expires_at - 60:
            return self.store.get(name, "access_token")
        flow = OAuth2Flow(spec, self.http)
        tokens = flow.refresh(
            self.store.get(name, "client_id"),
            self.store.get(name, "client_secret")
            if self.store.has(name, "client_secret") else None,
            self.store.get(name, "refresh_token"))
        self._save_tokens(name, tokens)
        return tokens["access_token"]

    def _api_headers(self, name, spec):
        headers = {}
        for header, item in spec.get("oauth", {}).get("api_headers",
                                                      {}).items():
            if self.store.has(name, item):
                headers[header] = self.store.get(name, item)
        return headers

    # -- file imports -------------------------------------------------------
    def import_file(self, name, path):
        spec = self._spec(name)
        if spec["type"] != "file_import":
            return {"ok": False, "error": "wrong_type",
                    "message": "%s is not a file-import connection" % name}
        try:
            module = _module_for(name)
            result = module.import_library(path, self.profile_dir)
            if result.get("ok"):
                self.store.put(name, "profile_path",
                               result["profile_path"])
            return result
        except Exception as exc:
            return {"ok": False, "error": "import_failed",
                    "message": "%s" % exc}

    def taste(self, name):
        """Speakable summary of the last import (file_import type)."""
        spec = self._spec(name)
        if not self.store.has(name, "profile_path"):
            return {"ok": False, "error": "not_imported",
                    "message": NOT_CONNECTED_MSG.get(name, "")}
        module = _module_for(name)
        return module.taste_summary(self.store.get(name, "profile_path"))

    def _spec(self, name):
        if name not in self.specs:
            raise KeyError("unknown connection: %r" % name)
        return self.specs[name]

    def audit_line(self, action, name, result):
        # Names and outcomes only - never secret values.
        return "%s connection=%s ok=%s" % (action, name,
                                          bool(result.get("ok")))
