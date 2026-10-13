#!/usr/bin/env python3
"""Mocked test suite for the connections layer. No real network, no real
secrets, no production touch. Run: python3 -m unittest discover tests"""
import base64
import builtins
import datetime
import getpass
import imaplib
import json
import os
import plistlib
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.request
from unittest import mock

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from connection import (  # noqa: E402
    load_registry, register, validate_spec, SpecError, AuthError,
    REGISTRY_PATH)
from oauth2 import OAuth2Flow, OAuthError, _CallbackHandler, _pkce_pair  # noqa: E402
from secret_store import (  # noqa: E402
    SecretStore, FileSecretBackend, DPAPISecretBackend, SecretNotFound,
    redact)
from manager import ConnectionManager  # noqa: E402
from http.server import HTTPServer  # noqa: E402
import icloud  # noqa: E402

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


# ---------------------------------------------------------------------------
# iCloud pilot (type: app_password). Synthetic fixtures only: no real Apple
# ID, no real app-specific password, no real network.
# ---------------------------------------------------------------------------

ICLOUD_USER = "user@icloud.com"
ICLOUD_PASS = "good-password"


def _basic(user, pw):
    return "Basic " + base64.b64encode(
        ("%s:%s" % (user, pw)).encode("utf-8")).decode("ascii")


GOOD_AUTH = _basic(ICLOUD_USER, ICLOUD_PASS)


def seed_icloud(mgr, password=ICLOUD_PASS, user=ICLOUD_USER):
    mgr.store.put("icloud", "apple_id", user)
    mgr.store.put("icloud", "app_password", password)


IMAP_HEADER_101 = (b"From: Test Sender <test@example.com>\r\n"
                   b"Subject: Dentist reminder\r\n"
                   b"Date: Tue, 13 Oct 2026 09:00:00 -0400\r\n"
                   b"\r\n")
IMAP_TEXT_101 = (b"Hi, just reminding you about the dentist "
                 b"tomorrow at 9am. Cheers.")
IMAP_HEADER_102 = (b"From: Other Person <other@example.com>\r\n"
                   b"Subject: Lunch plans\r\n"
                   b"Date: Mon, 12 Oct 2026 12:00:00 -0400\r\n"
                   b"\r\n")
IMAP_TEXT_102 = b"Want to grab lunch on Friday?"
IMAP_FULL_101 = (
    b"MIME-Version: 1.0\r\n"
    b"From: Test Sender <test@example.com>\r\n"
    b"Subject: With attachment\r\n"
    b"Date: Tue, 13 Oct 2026 10:00:00 -0400\r\n"
    b'Content-Type: multipart/mixed; boundary="BOUND"\r\n'
    b"\r\n"
    b"--BOUND\r\n"
    b'Content-Type: text/plain; charset="utf-8"\r\n'
    b"\r\n"
    b"Hello, this is the body text of the synthetic message.\r\n"
    b"--BOUND\r\n"
    b"Content-Type: application/pdf\r\n"
    b'Content-Disposition: attachment; filename="doc.pdf"\r\n'
    b"Content-Transfer-Encoding: base64\r\n"
    b"\r\n"
    b"aGVsbG8=\r\n"
    b"--BOUND--\r\n"
)


class FakeImap:
    """imaplib.IMAP4_SSL-shaped fake. No network, synthetic mail only."""

    def __init__(self, password=ICLOUD_PASS):
        self.password = password
        self.commands = []

    def login(self, user, pw):
        self.commands.append(("LOGIN", user))
        if pw != self.password:
            raise imaplib.IMAP4.error("authentication failed")
        return "OK", [b"logged in"]

    def select(self, mailbox, readonly=True):
        self.commands.append(("SELECT", mailbox))
        return "OK", [b"2"]

    def uid(self, command, *args):
        self.commands.append((command,) + args)
        if command == "SEARCH":
            return "OK", [b"101 102"]
        if command == "FETCH":
            uid, spec = args[0], args[1]
            uid_s = uid.decode("ascii") if isinstance(uid, bytes) else str(uid)
            headers = {"101": IMAP_HEADER_101, "102": IMAP_HEADER_102}
            texts = {"101": IMAP_TEXT_101, "102": IMAP_TEXT_102}
            if "HEADER.FIELDS" in spec:
                data = headers[uid_s]
                tag = (b"%s (UID %s BODY[HEADER.FIELDS (FROM SUBJECT DATE)]"
                       b" {%d}\r\n" % (uid_s.encode(), uid_s.encode(),
                                       len(data)))
                return "OK", [(tag, data), b")"]
            if "TEXT" in spec:
                data = texts[uid_s]
                tag = b"%s (BODY[TEXT]<0> {%d}\r\n" % (uid_s.encode(),
                                                       len(data))
                return "OK", [(tag, data), b")"]
            data = (IMAP_FULL_101 if uid_s == "101"
                    else headers[uid_s] + texts[uid_s])
            tag = b"%s (BODY[] {%d}\r\n" % (uid_s.encode(), len(data))
            return "OK", [(tag, data), b")"]
        return "BAD", [b"unsupported"]

    def logout(self):
        self.commands.append(("LOGOUT",))
        return "BYE", [b"bye"]


def fake_imap_factory(password=ICLOUD_PASS):
    return lambda: FakeImap(password=password)


def _dav_multistatus(inner, extra_ns=""):
    return ("<?xml version=\"1.0\" encoding=\"utf-8\"?>"
            "<d:multistatus xmlns:d=\"DAV:\"%s>%s</d:multistatus>"
            % (extra_ns, inner))


def _dav_response(href, prop_inner):
    return ("<d:response><d:href>%s</d:href><d:propstat><d:prop>%s</d:prop>"
            "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
            % (href, prop_inner))


CALDAV_NS = " xmlns:c=\"urn:ietf:params:xml:ns:caldav\""
CARDDAV_NS = " xmlns:card=\"urn:ietf:params:xml:ns:carddav\""

CALDAV_PRINCIPAL_XML = _dav_multistatus(_dav_response(
    "/", "<d:current-user-principal><d:href>/12345/principal/</d:href>"
         "</d:current-user-principal>"))
CALDAV_HOMESET_XML = _dav_multistatus(_dav_response(
    "/12345/principal/",
    "<d:calendar-home-set><d:href>/12345/calendars/</d:href>"
    "</d:calendar-home-set>"))
CALDAV_CALENDARS_XML = _dav_multistatus(
    _dav_response("/12345/calendars/",
                  "<d:resourcetype><d:collection/></d:resourcetype>") +
    _dav_response("/12345/calendars/work/",
                  "<d:resourcetype><d:collection/>"
                  "<c:calendar xmlns:c=\"urn:ietf:params:xml:ns:caldav\"/>"
                  "</d:resourcetype><d:displayname>Work</d:displayname>") +
    _dav_response("/12345/calendars/personal/",
                  "<d:resourcetype><d:collection/>"
                  "<c:calendar xmlns:c=\"urn:ietf:params:xml:ns:caldav\"/>"
                  "</d:resourcetype><d:displayname>Personal</d:displayname>"),
    CALDAV_NS)

VCAL_1 = ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
          "BEGIN:VEVENT\r\nUID:evt-1\r\nDTSTAMP:20261013T120000Z\r\n"
          "DTSTART:20261014T130000Z\r\nDTEND:20261014T140000Z\r\n"
          "SUMMARY:Dentist appointment\r\nLOCATION:Main St\r\n"
          "END:VEVENT\r\nEND:VCALENDAR\r\n")

CALDAV_EVENTS_XML = _dav_multistatus(_dav_response(
    "/12345/calendars/work/evt-1.ics",
    "<d:getetag>\"abc\"</d:getetag><c:calendar-data>" + VCAL_1 +
    "</c:calendar-data>"), CALDAV_NS)

CARDDAV_PRINCIPAL_XML = _dav_multistatus(_dav_response(
    "/", "<d:current-user-principal><d:href>/54321/principal/</d:href>"
         "</d:current-user-principal>"))
CARDDAV_HOMESET_XML = _dav_multistatus(_dav_response(
    "/54321/principal/",
    "<d:addressbook-home-set><d:href>/54321/carddavhome/</d:href>"
    "</d:addressbook-home-set>"))
CARDDAV_BOOKS_XML = _dav_multistatus(
    _dav_response("/54321/carddavhome/",
                  "<d:resourcetype><d:collection/></d:resourcetype>") +
    _dav_response("/54321/carddavhome/Default/",
                  "<d:resourcetype><d:collection/>"
                  "<card:addressbook "
                  "xmlns:card=\"urn:ietf:params:xml:ns:carddav\"/>"
                  "</d:resourcetype><d:displayname>Default</d:displayname>"),
    CARDDAV_NS)

VCARD_1 = ("BEGIN:VCARD\r\nVERSION:3.0\r\nFN:Chelsea Crawford\r\n"
           "N:Crawford;Chelsea;;;\r\n"
           "EMAIL;TYPE=HOME:chelsea@example.com\r\n"
           "TEL;TYPE=CELL:+15551234567\r\nEND:VCARD\r\n")
VCARD_2 = ("BEGIN:VCARD\r\nVERSION:3.0\r\nFN:Sam Warner\r\n"
           "N:Warner;Sam;;;\r\n"
           "EMAIL:sam@example.com\r\nEND:VCARD\r\n")

CARDDAV_VCARDS_XML = _dav_multistatus(
    _dav_response("/54321/carddavhome/Default/c1.vcf",
                  "<d:getetag>\"e1\"</d:getetag><card:address-data>" +
                  VCARD_1 + "</card:address-data>") +
    _dav_response("/54321/carddavhome/Default/c2.vcf",
                  "<d:getetag>\"e2\"</d:getetag><card:address-data>" +
                  VCARD_2 + "</card:address-data>"),
    CARDDAV_NS)


class FakeDav:
    """CalDAV/CardDAV-shaped fake. Routes on (method, url); 401s on a
    wrong Authorization header, like iCloud."""

    def __init__(self, password=ICLOUD_PASS):
        self.expected_auth = _basic(ICLOUD_USER, password)
        self.calls = []

    def request(self, method, url, body=None, headers=None):
        headers = dict(headers or {})
        self.calls.append((method, url, body, headers))
        if headers.get("Authorization") != self.expected_auth:
            return 401, ""
        if method == "PROPFIND" and url == "https://caldav.icloud.com/":
            return 207, CALDAV_PRINCIPAL_XML
        if (method == "PROPFIND"
                and url == "https://caldav.icloud.com/12345/principal/"):
            return 207, CALDAV_HOMESET_XML
        if (method == "PROPFIND"
                and url == "https://caldav.icloud.com/12345/calendars/"):
            return 207, CALDAV_CALENDARS_XML
        if method == "REPORT" and url in (
                "https://caldav.icloud.com/12345/calendars/work/",
                "https://caldav.icloud.com/12345/calendars/personal/"):
            return 207, CALDAV_EVENTS_XML
        if method == "PROPFIND" and url == "https://contacts.icloud.com/":
            return 207, CARDDAV_PRINCIPAL_XML
        if (method == "PROPFIND"
                and url == "https://contacts.icloud.com/54321/principal/"):
            return 207, CARDDAV_HOMESET_XML
        if (method == "PROPFIND"
                and url == "https://contacts.icloud.com/54321/carddavhome/"):
            return 207, CARDDAV_BOOKS_XML
        if (method == "PROPFIND" and url ==
                "https://contacts.icloud.com/54321/carddavhome/Default/"):
            return 207, CARDDAV_VCARDS_XML
        return 404, ""


class ICloudRegistryTests(unittest.TestCase):
    def test_icloud_registered_as_app_password(self):
        specs = load_registry()
        self.assertIn("icloud", specs)
        spec = specs["icloud"]
        self.assertEqual(spec["type"], "app_password")
        self.assertEqual(spec["auth"]["method"], "app_specific_password")
        self.assertEqual(spec["credential_refs"],
                         ["conn-icloud-apple_id", "conn-icloud-app_password"])
        for cap in ("search_messages", "get_message", "list_events",
                    "list_contacts"):
            self.assertIn(cap, spec["capabilities"])

    def test_app_password_spec_validation(self):
        bad = {"name": "x", "type": "app_password", "capabilities": ["c"],
               "auth": {"method": "oauth"}}
        self.assertTrue(validate_spec(bad))
        no_auth = {"name": "x", "type": "app_password",
                   "capabilities": ["c"]}
        self.assertTrue(validate_spec(no_auth))
        tmp = tempfile.mkdtemp()
        dest = os.path.join(tmp, "r.json")
        shutil.copy(REGISTRY_PATH, dest)
        good = {"name": "x", "type": "app_password", "capabilities": ["c"],
                "auth": {"method": "app_specific_password"}}
        self.assertEqual(register(good, path=dest), "x")
        self.assertIn("x", load_registry(dest))


class ICloudMailTests(unittest.TestCase):
    def test_verify_success(self):
        self.assertTrue(icloud.verify(ICLOUD_USER, ICLOUD_PASS,
                                      imap_factory=fake_imap_factory()))

    def test_verify_bad_password_raises_auth(self):
        with self.assertRaises(AuthError):
            icloud.verify(ICLOUD_USER, "wrong",
                          imap_factory=fake_imap_factory())

    def test_search_messages_returns_summaries(self):
        res = icloud.search_messages(FakeDav(), ICLOUD_USER, ICLOUD_PASS,
                                     imap_factory=fake_imap_factory(),
                                     query="dentist", max_results=10)
        self.assertTrue(res["ok"])
        self.assertEqual(len(res["messages"]), 2)
        # newest uid first
        self.assertEqual(res["messages"][0]["uid"], "102")
        self.assertIn("lunch", res["messages"][0]["snippet"])
        subjects = [m["subject"] for m in res["messages"]]
        self.assertIn("Dentist reminder", subjects)

    def test_search_escapes_imap_quotes(self):
        imap = FakeImap()
        icloud.search_messages(FakeDav(), ICLOUD_USER, ICLOUD_PASS,
                               imap_factory=lambda: imap, query='say "hi"')
        searches = [c for c in imap.commands if c[0] == "SEARCH"]
        self.assertEqual(len(searches), 1)
        self.assertIn('\\"hi\\"', searches[0][2])

    def test_get_message_skips_attachments(self):
        res = icloud.get_message(FakeDav(), ICLOUD_USER, ICLOUD_PASS,
                                 imap_factory=fake_imap_factory(), uid="101")
        self.assertTrue(res["ok"])
        self.assertIn("body text of the synthetic message",
                      res["message"]["body"])
        self.assertNotIn("aGVsbG8", res["message"]["body"])
        self.assertLessEqual(len(res["message"]["body"]), 4000)

    def test_get_message_requires_uid(self):
        with self.assertRaises(ValueError):
            icloud.get_message(FakeDav(), ICLOUD_USER, ICLOUD_PASS,
                               imap_factory=fake_imap_factory())

    def test_bad_password_raises_auth(self):
        with self.assertRaises(AuthError):
            icloud.search_messages(FakeDav(), ICLOUD_USER, "wrong",
                                   imap_factory=fake_imap_factory())


class ICloudCalTests(unittest.TestCase):
    def test_list_events_discovers_and_parses(self):
        dav = FakeDav()
        res = icloud.list_events(dav, ICLOUD_USER, ICLOUD_PASS)
        self.assertTrue(res["ok"])
        # one fixture event per discovered calendar (work + personal)
        self.assertEqual(len(res["events"]), 2)
        event = res["events"][0]
        self.assertEqual(event["summary"], "Dentist appointment")
        self.assertEqual(event["location"], "Main St")
        self.assertIn("2026-10-14", event["start"])
        methods = [c[0] for c in dav.calls]
        self.assertIn("PROPFIND", methods)
        self.assertIn("REPORT", methods)
        # every DAV call carried Basic auth (never logged anywhere)
        auths = {c[3]["Authorization"] for c in dav.calls}
        self.assertEqual(auths, {GOOD_AUTH})

    def test_list_events_401_raises_auth(self):
        with self.assertRaises(AuthError):
            icloud.list_events(FakeDav(), ICLOUD_USER, "wrong")


class ICloudContactsTests(unittest.TestCase):
    def test_list_contacts_parses_name_email_phone(self):
        dav = FakeDav()
        res = icloud.list_contacts(dav, ICLOUD_USER, ICLOUD_PASS)
        self.assertTrue(res["ok"])
        self.assertEqual(len(res["contacts"]), 2)
        chelsea = [c for c in res["contacts"]
                   if c["name"] == "Chelsea Crawford"][0]
        self.assertEqual(chelsea["emails"], ["chelsea@example.com"])
        self.assertEqual(chelsea["phones"], ["+15551234567"])
        sam = [c for c in res["contacts"]
               if c["name"] == "Sam Warner"][0]
        self.assertEqual(sam["emails"], ["sam@example.com"])
        self.assertEqual(sam["phones"], [])

    def test_list_contacts_401_raises_auth(self):
        with self.assertRaises(AuthError):
            icloud.list_contacts(FakeDav(), ICLOUD_USER, "wrong")


class ICloudManagerTests(unittest.TestCase):
    def test_call_not_connected_never_hallucinates(self):
        mgr = fresh_manager()
        result = mgr.call("icloud", "list_events")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "not_connected")
        self.assertIn("connect icloud", result["message"])

    def test_call_unknown_capability(self):
        mgr = fresh_manager()
        seed_icloud(mgr)
        result = mgr.call("icloud", "nope")
        self.assertEqual(result["error"], "unknown_capability")

    def test_status_reports_no_secrets(self):
        mgr = fresh_manager()
        seed_icloud(mgr)
        st = json.dumps(mgr.status("icloud"))
        self.assertNotIn(ICLOUD_PASS, st)
        self.assertTrue(mgr.status("icloud")["connected"])
        self.assertEqual(mgr.status("icloud")["type"], "app_password")
        self.assertFalse(fresh_manager().status("icloud")["connected"])

    def test_call_search_messages_via_manager(self):
        mgr = fresh_manager()
        seed_icloud(mgr)
        result = mgr.call("icloud", "search_messages",
                          imap_factory=fake_imap_factory(), max_results=5)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["messages"]), 2)

    def test_call_list_events_via_manager(self):
        mgr = fresh_manager()
        seed_icloud(mgr)
        mgr.http.request = FakeDav().request
        result = mgr.call("icloud", "list_events")
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["events"]), 2)

    def test_call_auth_failure_structured(self):
        mgr = fresh_manager()
        seed_icloud(mgr, password="wrong")
        mgr.http.request = FakeDav().request  # server expects the good one
        result = mgr.call("icloud", "list_events")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "auth_failed")

    def test_disconnect_clears_credentials(self):
        mgr = fresh_manager()
        seed_icloud(mgr)
        self.assertTrue(mgr.status("icloud")["connected"])
        mgr.disconnect("icloud")
        self.assertFalse(mgr.status("icloud")["connected"])

    def test_connect_app_password_success(self):
        mgr = fresh_manager()
        with mock.patch.object(icloud, "verify", return_value=True), \
                mock.patch.object(builtins, "input",
                                  return_value=ICLOUD_USER), \
                mock.patch.object(getpass, "getpass",
                                  return_value=ICLOUD_PASS):
            result = mgr.connect("icloud")
        self.assertTrue(result["ok"])
        self.assertTrue(mgr.status("icloud")["connected"])
        self.assertEqual(mgr.store.get("icloud", "apple_id"), ICLOUD_USER)

    def test_connect_app_password_bad_password_discarded(self):
        mgr = fresh_manager()

        def bad_verify(apple_id, app_password, imap_factory=None):
            raise AuthError("rejected")

        with mock.patch.object(icloud, "verify", side_effect=bad_verify), \
                mock.patch.object(builtins, "input",
                                  return_value=ICLOUD_USER), \
                mock.patch.object(getpass, "getpass",
                                  return_value="wrong"):
            result = mgr.connect("icloud")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "auth_failed")
        self.assertFalse(mgr.store.has("icloud", "app_password"))


if __name__ == "__main__":
    unittest.main()