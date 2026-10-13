#!/usr/bin/env python3
"""Mocked test suite for the connections layer. No real network, no real
secrets, no production touch. Run: python3 -m unittest discover tests"""
import datetime
import json
import os
import plistlib
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from connection import (  # noqa: E402
    load_registry, register, validate_spec, SpecError, REGISTRY_PATH)
from oauth2 import OAuth2Flow, OAuthError, _CallbackHandler, _pkce_pair  # noqa: E402
from secret_store import (  # noqa: E402
    SecretStore, FileSecretBackend, DPAPISecretBackend, SecretNotFound,
    redact)
from manager import ConnectionManager  # noqa: E402
from http.server import HTTPServer  # noqa: E402

GCAL_OAUTH = {
    "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
    "token_url": "https://oauth2.googleapis.com/token",
    "scopes": ["https://www.googleapis.com/auth/calendar.readonly"],
    "use_pkce": True,
}
GCAL_SPEC = {"name": "gcal", "type": "oauth2", "oauth": GCAL_OAUTH}


class FakeHttp:
    def __init__(self):
        self.posts = []
        self.gets = []
        self.post_resp = (200, "{}")
        self.get_resp = (200, "{}")
        self.get_fn = None  # optional: fn(url) -> (status, body)

    def post(self, url, data, headers=None):
        self.posts.append((url, dict(data), dict(headers or {})))
        return self.post_resp

    def get(self, url, headers=None):
        self.gets.append((url, dict(headers or {})))
        if self.get_fn is not None:
            return self.get_fn(url)
        return self.get_resp


def fresh_manager():
    tmp = tempfile.mkdtemp()
    store = SecretStore(FileSecretBackend(os.path.join(tmp, "s.json")))
    http = FakeHttp()
    mgr = ConnectionManager(registry_path=REGISTRY_PATH, store=store,
                            http=http,
                            profile_dir=os.path.join(tmp, "profiles"))
    mgr._tmp = tmp
    return mgr


def seed_oauth(mgr, name="gcal", expired=False):
    import time
    mgr.store.put(name, "client_id", "cid")
    mgr.store.put(name, "client_secret", "csec")
    mgr.store.put(name, "refresh_token", "rt-token")
    mgr.store.put(name, "access_token", "old-access")
    mgr.store.put(name, "expires_at",
                  str(int(time.time()) + (-10 if expired else 3600)))


class RegistryTests(unittest.TestCase):
    def test_registry_loads_and_validates(self):
        specs = load_registry()
        self.assertIn("gcal", specs)
        self.assertIn("apple_music", specs)
        self.assertIn("gmail", specs)
        self.assertIn("drive", specs)
        self.assertEqual(specs["gcal"]["type"], "oauth2")
        self.assertEqual(specs["apple_music"]["type"], "file_import")
        self.assertEqual(
            specs["gmail"]["oauth"]["scopes"],
            ["https://www.googleapis.com/auth/gmail.readonly"])
        self.assertEqual(
            specs["drive"]["oauth"]["scopes"],
            ["https://www.googleapis.com/auth/drive.readonly"])

    def test_register_rejects_bad_spec(self):
        bad = {"name": "x", "type": "oauth2", "capabilities": ["c"],
               "oauth": {"auth_url": "https://x", "scopes": ["s"]}}
        self.assertTrue(validate_spec(bad))  # missing token_url
        with self.assertRaises(SpecError):
            register(bad, path=os.path.join(tempfile.mkdtemp(), "r.json"))

    def test_register_accepts_lwa_style_spec(self):
        """A future Login-with-Amazon adapter is purely declarative."""
        tmp = tempfile.mkdtemp()
        dest = os.path.join(tmp, "r.json")
        shutil.copy(REGISTRY_PATH, dest)
        spec = {
            "name": "amazon_music", "display": "Amazon Music",
            "type": "oauth2", "description": "conditional future",
            "capabilities": ["search"],
            "oauth": {
                "auth_url": "https://www.amazon.com/ap/oa",
                "token_url": "https://api.amazon.com/auth/o2/token",
                "scopes": ["profile"],
                "use_pkce": False, "token_auth": "basic",
                "api_headers": {"x-api-key": "api_key"},
            },
            "credential_refs": ["conn-amazon_music-api_key"],
        }
        self.assertEqual(register(spec, path=dest), "amazon_music")
        specs = load_registry(dest)
        self.assertIn("amazon_music", specs)


class OAuthFlowTests(unittest.TestCase):
    def test_authorization_url(self):
        flow = OAuth2Flow(GCAL_SPEC, FakeHttp())
        url, state = flow.authorization_url(
            "cid", "http://127.0.0.1:9/callback",
            state="st", code_challenge="ch")
        self.assertIn("client_id=cid", url)
        self.assertIn("code_challenge=ch", url)
        self.assertIn("code_challenge_method=S256", url)
        self.assertIn("state=st", url)
        self.assertIn("calendar.readonly", url)

    def test_pkce_pair(self):
        verifier, challenge = _pkce_pair()
        self.assertTrue(len(verifier) > 40 and len(challenge) > 40)

    def test_loopback_captures_code(self):
        server = HTTPServer(("127.0.0.1", 0), _CallbackHandler)
        server.got_callback = threading.Event()
        server.captured = None
        port = server.server_address[1]
        t = threading.Thread(target=server.handle_request, daemon=True)
        t.start()
        with urllib.request.urlopen(
                "http://127.0.0.1:%d/callback?code=abc&state=xyz" % port,
                timeout=10) as resp:
            self.assertEqual(resp.status, 200)
        self.assertTrue(server.got_callback.wait(5))
        self.assertEqual(server.captured["code"], "abc")
        self.assertEqual(server.captured["state"], "xyz")
        server.server_close()

    def test_wait_for_code_timeout(self):
        flow = OAuth2Flow(GCAL_SPEC, FakeHttp())
        with self.assertRaises(OAuthError):
            flow.wait_for_code(timeout=0.2)

    def test_exchange_code(self):
        http = FakeHttp()
        http.post_resp = (200, json.dumps(
            {"access_token": "at", "refresh_token": "rt",
             "expires_in": 3600}))
        flow = OAuth2Flow(GCAL_SPEC, http)
        tokens = flow.exchange_code("code1", "cid", "csec",
                                    "http://127.0.0.1:9/callback",
                                    code_verifier="v")
        self.assertEqual(tokens["access_token"], "at")
        url, data, _ = http.posts[0]
        self.assertIn("oauth2.googleapis.com", url)
        self.assertEqual(data["grant_type"], "authorization_code")
        self.assertEqual(data["code_verifier"], "v")

    def test_token_auth_basic(self):
        spec = {"name": "m", "type": "oauth2",
                "oauth": dict(GCAL_OAUTH, token_auth="basic")}
        http = FakeHttp()
        http.post_resp = (200, json.dumps({"access_token": "at"}))
        flow = OAuth2Flow(spec, http)
        flow.refresh("cid", "csec", "rt")
        _, data, headers = http.posts[0]
        self.assertTrue(headers["Authorization"].startswith("Basic "))
        self.assertNotIn("client_id", data)
        self.assertEqual(data["grant_type"], "refresh_token")

    def test_exchange_failure_structured(self):
        http = FakeHttp()
        http.post_resp = (400, json.dumps({"error": "invalid_grant"}))
        flow = OAuth2Flow(GCAL_SPEC, http)
        with self.assertRaises(OAuthError):
            flow.exchange_code("bad", "cid", "csec", "http://x/")


class SecretStoreTests(unittest.TestCase):
    def test_file_backend_roundtrip_and_mode(self):
        tmp = tempfile.mkdtemp()
        be = FileSecretBackend(os.path.join(tmp, "s.json"))
        be.save("conn-gcal-refresh_token", "super-secret-value")
        self.assertEqual(be.load("conn-gcal-refresh_token"),
                         "super-secret-value")
        self.assertTrue(be.exists("conn-gcal-refresh_token"))
        self.assertTrue(be.mode_ok())
        be.delete("conn-gcal-refresh_token")
        self.assertFalse(be.exists("conn-gcal-refresh_token"))
        with self.assertRaises(SecretNotFound):
            be.load("conn-gcal-refresh_token")

    def test_secrets_never_in_repr_or_logs(self):
        tmp = tempfile.mkdtemp()
        store = SecretStore(
            FileSecretBackend(os.path.join(tmp, "s.json")))
        store.put("gcal", "refresh_token", "rt-SECRET-VALUE-123")
        self.assertNotIn("SECRET-VALUE", repr(store))
        self.assertNotIn("SECRET-VALUE", redact("rt-SECRET-VALUE-123"))

    def test_dpapi_backend_mocked(self):
        be = DPAPISecretBackend.__new__(DPAPISecretBackend)
        be.vault_dir = tempfile.mkdtemp()
        be._protect = lambda b: b"ENC:" + b  # noqa: E731
        be._unprotect = lambda b: b[4:]  # noqa: E731
        be.save("conn-x-k", "shh")
        self.assertEqual(be.load("conn-x-k"), "shh")
        self.assertTrue(be.exists("conn-x-k"))
        be.delete("conn-x-k")
        self.assertFalse(be.exists("conn-x-k"))

    def test_dpapi_refuses_non_windows(self):
        if os.name != "nt":
            with self.assertRaises(OSError):
                DPAPISecretBackend()


class ManagerTests(unittest.TestCase):
    def test_call_not_connected_never_hallucinates(self):
        mgr = fresh_manager()
        result = mgr.call("gcal", "list_events")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "not_connected")
        self.assertIn("connect gcal", result["message"])

    def test_call_unknown_capability(self):
        mgr = fresh_manager()
        seed_oauth(mgr)
        result = mgr.call("gcal", "nope")
        self.assertEqual(result["error"], "unknown_capability")

    def test_status_reports_no_secrets(self):
        mgr = fresh_manager()
        seed_oauth(mgr)
        st = json.dumps(mgr.status("gcal"))
        self.assertNotIn("rt-token", st)
        self.assertTrue(mgr.status("gcal")["connected"])
        self.assertFalse(fresh_manager().status("gcal")["connected"])

    def test_call_list_events(self):
        mgr = fresh_manager()
        seed_oauth(mgr)
        mgr.http.get_resp = (200, json.dumps({"items": [
            {"id": "e1", "summary": "Dentist",
             "start": {"dateTime": "2026-10-14T09:00:00-04:00"},
             "end": {"dateTime": "2026-10-14T10:00:00-04:00"}}]}))
        result = mgr.call("gcal", "list_events", max_results="5")
        self.assertTrue(result["ok"])
        self.assertEqual(result["events"][0]["summary"], "Dentist")
        _, headers = mgr.http.gets[0]
        self.assertEqual(headers["Authorization"], "Bearer old-access")

    def test_token_refresh_on_expiry(self):
        mgr = fresh_manager()
        seed_oauth(mgr, expired=True)
        mgr.http.post_resp = (200, json.dumps(
            {"access_token": "new-access", "expires_in": 3600}))
        mgr.http.get_resp = (200, json.dumps({"items": []}))
        result = mgr.call("gcal", "list_events")
        self.assertTrue(result["ok"])
        self.assertEqual(mgr.store.get("gcal", "access_token"), "new-access")
        _, data, _ = mgr.http.posts[0]
        self.assertEqual(data["grant_type"], "refresh_token")

    def test_api_headers_injected(self):
        """Future LWA-style x-api-key flows ride the same path."""
        mgr = fresh_manager()
        seed_oauth(mgr)
        mgr.specs["gcal"]["oauth"]["api_headers"] = {"x-api-key": "api_key"}
        mgr.store.put("gcal", "api_key", "KEY123")
        mgr.http.get_resp = (200, json.dumps({"items": []}))
        result = mgr.call("gcal", "list_events")
        self.assertTrue(result["ok"])
        _, headers = mgr.http.gets[0]
        self.assertEqual(headers["x-api-key"], "KEY123")
        self.assertNotIn("KEY123", json.dumps(mgr.status("gcal")))

    def test_disconnect_clears_credentials(self):
        mgr = fresh_manager()
        seed_oauth(mgr)
        self.assertTrue(mgr.status("gcal")["connected"])
        mgr.disconnect("gcal")
        self.assertFalse(mgr.status("gcal")["connected"])


def sample_library_xml(path):
    day = datetime.datetime(2026, 10, 1, 12, 0, 0)
    lib = {
        "Major Version": 1, "Minor Version": 1,
        "Tracks": {
            "1": {"Track ID": 1, "Name": "Static Bloom",
                  "Artist": "The Artful Dodger", "Album": "Night Tapes",
                  "Genre": "Drum & Bass", "Play Count": 42, "Rating": 100,
                  "Loved": True, "Date Added": day,
                  "Play Date UTC": day + datetime.timedelta(hours=2)},
            "2": {"Track ID": 2, "Name": "Wire Hum",
                  "Artist": "The Artful Dodger", "Album": "Night Tapes",
                  "Genre": "Techno", "Play Count": 17, "Rating": 80,
                  "Date Added": day},
            "3": {"Track ID": 3, "Name": "Quiet Track",
                  "Artist": "Someone Else", "Album": "Misc",
                  "Genre": "Ambient", "Date Added": day},
        },
        "Playlists": [
            {"Name": "Gym", "Playlist Items": [{"Track ID": 1},
                                              {"Track ID": 2}]},
        ],
    }
    with open(path, "wb") as fh:
        plistlib.dump(lib, fh)


class AppleMusicTests(unittest.TestCase):
    def test_import_builds_taste_profile(self):
        mgr = fresh_manager()
        tmp = tempfile.mkdtemp()
        xml = os.path.join(tmp, "Library.xml")
        sample_library_xml(xml)
        result = mgr.import_file("apple_music", xml)
        self.assertTrue(result["ok"])
        self.assertEqual(result["total_tracks"], 3)
        self.assertTrue(os.path.exists(result["profile_path"]))
        with open(result["profile_path"], encoding="utf-8") as fh:
            profile = json.load(fh)
        self.assertEqual(profile["top_artists"][0][0], "The Artful Dodger")
        self.assertEqual(profile["top_artists"][0][1], 59)
        self.assertIn("The Artful Dodger", result["summary"])
        taste = mgr.taste("apple_music")
        self.assertTrue(taste["ok"])
        self.assertIn("Drum & Bass", taste["summary"])

    def test_import_bad_file_structured_error(self):
        mgr = fresh_manager()
        result = mgr.import_file("apple_music", "/nonexistent/Library.xml")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "import_failed")
        tmp = tempfile.mkdtemp()
        bad = os.path.join(tmp, "bad.xml")
        with open(bad, "w") as fh:
            fh.write("not xml at all")
        result = mgr.import_file("apple_music", bad)
        self.assertFalse(result["ok"])

    def test_taste_before_import(self):
        mgr = fresh_manager()
        result = mgr.taste("apple_music")
        self.assertEqual(result["error"], "not_imported")


# ---------------------------------------------------------------------------
# Synthetic fixtures only: no real mail, no real files, no real credentials.
# ---------------------------------------------------------------------------

GMAIL_LIST = {
    "messages": [{"id": "m1", "threadId": "t1"},
                 {"id": "m2", "threadId": "t2"}],
    "resultSizeEstimate": 2,
}


def _gmail_meta(mid, sender, subject):
    return {
        "id": mid, "threadId": "t1",
        "snippet": "synthetic snippet for tests",
        "labelIds": ["INBOX"],
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": sender},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": "Tue, 13 Oct 2026 09:00:00 -0400"},
            ],
        },
    }


def _gmail_full(mid):
    import base64 as _b64
    body = _b64.urlsafe_b64encode(
        b"Hello from the synthetic test message. Second line here.").decode()
    meta = _gmail_meta(mid, "Test Sender <test@example.com>",
                       "Synthetic subject")
    meta["payload"]["parts"] = [
        {"mimeType": "text/plain", "filename": "",
         "body": {"data": body, "size": 60}},
        {"mimeType": "application/pdf", "filename": "attach.pdf",
         "body": {"attachmentId": "att1", "size": 10}},
    ]
    return meta


def gmail_router(url):
    if "/messages?" in url and "format=" not in url:
        return 200, json.dumps(GMAIL_LIST)
    if "/messages/m1" in url:
        if "format=full" in url:
            return 200, json.dumps(_gmail_full("m1"))
        return 200, json.dumps(_gmail_meta(
            "m1", "Test Sender <test@example.com>", "Synthetic subject"))
    if "/messages/m2" in url:
        return 200, json.dumps(_gmail_meta(
            "m2", "Other Person <other@example.com>", "Another synthetic"))
    return 404, "{}"


class GmailTests(unittest.TestCase):
    def _mgr(self):
        mgr = fresh_manager()
        seed_oauth(mgr, "gmail")
        mgr.http.get_fn = gmail_router
        return mgr

    def test_search_messages_lists_and_summarizes(self):
        mgr = self._mgr()
        result = mgr.call("gmail", "search_messages", query="test",
                          max_results="10")
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["messages"]), 2)
        self.assertEqual(result["messages"][0]["subject"],
                         "Synthetic subject")
        self.assertEqual(result["messages"][0]["from"],
                         "Test Sender <test@example.com>")
        self.assertEqual(result["resultSizeEstimate"], 2)
        _, headers = mgr.http.gets[0]
        self.assertEqual(headers["Authorization"], "Bearer old-access")

    def test_get_message_decodes_text_body(self):
        mgr = self._mgr()
        result = mgr.call("gmail", "get_message", message_id="m1")
        self.assertTrue(result["ok"])
        msg = result["message"]
        self.assertEqual(msg["subject"], "Synthetic subject")
        self.assertIn("Hello from the synthetic test message",
                      msg["body_text"])
        self.assertLessEqual(len(msg["body_text"]), 4000)

    def test_get_message_requires_id(self):
        mgr = self._mgr()
        result = mgr.call("gmail", "get_message")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "provider_error")

    def test_not_connected_never_hallucinates(self):
        mgr = fresh_manager()
        result = mgr.call("gmail", "search_messages", query="x")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "not_connected")
        self.assertIn("connect gmail", result["message"])


DRIVE_LIST = {
    "files": [
        {"id": "f1", "name": "notes.txt", "mimeType": "text/plain",
         "modifiedTime": "2026-10-12T10:00:00.000Z", "size": "18"},
        {"id": "f2", "name": "photo.png", "mimeType": "image/png",
         "modifiedTime": "2026-10-11T10:00:00.000Z", "size": "999"},
    ]
}

DRIVE_META = {
    "f1": {"id": "f1", "name": "notes.txt", "mimeType": "text/plain",
           "modifiedTime": "2026-10-12T10:00:00.000Z", "size": "18",
           "parents": ["root"]},
    "f2": {"id": "f2", "name": "photo.png", "mimeType": "image/png",
           "modifiedTime": "2026-10-11T10:00:00.000Z", "size": "999",
           "parents": ["root"]},
    "f3": {"id": "f3", "name": "Doc", "mimeType":
           "application/vnd.google-apps.document",
           "modifiedTime": "2026-10-10T10:00:00.000Z", "parents": ["root"]},
    "f4": {"id": "f4", "name": "big.txt", "mimeType": "text/plain",
           "modifiedTime": "2026-10-09T10:00:00.000Z",
           "size": str(300 * 1024), "parents": ["root"]},
}


def drive_router(url):
    for fid, meta in DRIVE_META.items():
        if "/files/%s/export?" % fid in url:
            return 200, "exported doc text"
        if "/files/%s?alt=media" % fid in url:
            return 200, "hello text file"
        if "/files/%s?" % fid in url:
            return 200, json.dumps(meta)
    if "/files?" in url:
        return 200, json.dumps(DRIVE_LIST)
    return 404, "{}"


class DriveTests(unittest.TestCase):
    def _mgr(self):
        mgr = fresh_manager()
        seed_oauth(mgr, "drive")
        mgr.http.get_fn = drive_router
        return mgr

    def test_list_files(self):
        mgr = self._mgr()
        result = mgr.call("drive", "list_files", max_results="10")
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["files"]), 2)
        self.assertEqual(result["files"][0]["name"], "notes.txt")
        self.assertEqual(result["files"][0]["size"], 18)
        _, headers = mgr.http.gets[0]
        self.assertEqual(headers["Authorization"], "Bearer old-access")

    def test_get_file_metadata(self):
        mgr = self._mgr()
        result = mgr.call("drive", "get_file_metadata", file_id="f1")
        self.assertTrue(result["ok"])
        self.assertEqual(result["file"]["mimeType"], "text/plain")
        self.assertEqual(result["file"]["parents"], ["root"])

    def test_download_text_file(self):
        mgr = self._mgr()
        result = mgr.call("drive", "download_file_text", file_id="f1")
        self.assertTrue(result["ok"])
        self.assertEqual(result["text"], "hello text file")
        self.assertFalse(result["truncated"])
        self.assertTrue(any("alt=media" in u for u, _ in mgr.http.gets))

    def test_download_refuses_binary(self):
        mgr = self._mgr()
        result = mgr.call("drive", "download_file_text", file_id="f2")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "not_text")
        self.assertFalse(any("alt=media" in u for u, _ in mgr.http.gets))

    def test_google_doc_exports_to_text(self):
        mgr = self._mgr()
        result = mgr.call("drive", "download_file_text", file_id="f3")
        self.assertTrue(result["ok"])
        self.assertEqual(result["text"], "exported doc text")
        self.assertTrue(any("/export?" in u for u, _ in mgr.http.gets))

    def test_download_refuses_oversize(self):
        mgr = self._mgr()
        result = mgr.call("drive", "download_file_text", file_id="f4")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "too_large")
        self.assertFalse(any("alt=media" in u for u, _ in mgr.http.gets))

    def test_not_connected_never_hallucinates(self):
        mgr = fresh_manager()
        result = mgr.call("drive", "list_files")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "not_connected")
        self.assertIn("connect drive", result["message"])


if __name__ == "__main__":
    unittest.main()