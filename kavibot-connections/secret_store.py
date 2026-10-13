#!/usr/bin/env python3
"""Vault-backed secret storage for the connections layer.

Secrets (OAuth client secrets, refresh tokens, API keys) are NEVER logged,
NEVER returned by status calls, and NEVER leave the machine that holds them.

Backends:
  - DPAPISecretBackend (production, Windows/PC only): DPAPI LocalMachine
    scope, same boundary as the existing C:\\AI\\vault. Any local process can
    unprotect LocalMachine blobs; the ACL on the directory keeps it to
    SYSTEM + Administrators.
  - FileSecretBackend (staging/dev): JSON file with mode 0600. Mirrors the
    existing ~/.kavi-secrets pattern. NEVER for production tokens.

The manager picks DPAPI on Windows, file backend elsewhere.
"""
import base64
import ctypes
import json
import os
import stat

SECRET_PREFIX = "conn"


class SecretNotFound(KeyError):
    pass


def redact(value, keep=4):
    """Safe for logs: first chars + ellipsis. Never the full value."""
    if value is None:
        return None
    s = str(value)
    if len(s) <= keep:
        return "****"
    return s[:keep] + "\u2026[%d chars]" % len(s)


class SecretBackend:
    def save(self, name, value):
        raise NotImplementedError

    def load(self, name):
        raise NotImplementedError

    def delete(self, name):
        raise NotImplementedError

    def exists(self, name):
        raise NotImplementedError


class FileSecretBackend(SecretBackend):
    """0600 JSON file. Staging/dev only."""

    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        if not os.path.exists(path):
            self._write({})
        os.chmod(path, 0o600)

    def _read(self):
        with open(self.path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _write(self, data):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)

    def save(self, name, value):
        data = self._read()
        data[name] = value
        self._write(data)

    def load(self, name):
        data = self._read()
        if name not in data:
            raise SecretNotFound(name)
        return data[name]

    def delete(self, name):
        data = self._read()
        data.pop(name, None)
        self._write(data)

    def exists(self, name):
        return name in self._read()

    def mode_ok(self):
        return bool(os.stat(self.path).st_mode & 0o777 == 0o600)


class DPAPISecretBackend(SecretBackend):
    """Windows DPAPI (LocalMachine). Raises on non-Windows."""

    def __init__(self, vault_dir=r"C:\AI\vault\connections"):
        if os.name != "nt":
            raise OSError("DPAPI backend is Windows-only")
        self.vault_dir = vault_dir
        os.makedirs(vault_dir, exist_ok=True)

    def _path(self, name):
        safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in name)
        return os.path.join(self.vault_dir, safe + ".bin")

    def _protect(self, plaintext: bytes) -> bytes:
        crypt32 = ctypes.windll.crypt32

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", ctypes.c_ulong),
                        ("pbData", ctypes.POINTER(ctypes.c_byte))]

        def blob(buf: bytes):
            b = DATA_BLOB()
            b.cbData = len(buf)
            b.pbData = ctypes.cast(ctypes.create_string_buffer(buf),
                                  ctypes.POINTER(ctypes.c_byte))
            return b

        out = DATA_BLOB()
        ok = crypt32.CryptProtectData(
            ctypes.byref(blob(plaintext)), None, None, None, None,
            0x04,  # CRYPTPROTECT_LOCAL_MACHINE
            ctypes.byref(out))
        if not ok:
            raise OSError("CryptProtectData failed")
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            crypt32.LocalFree(out.pbData)

    def _unprotect(self, blob_bytes: bytes) -> bytes:
        crypt32 = ctypes.windll.crypt32

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", ctypes.c_ulong),
                        ("pbData", ctypes.POINTER(ctypes.c_byte))]

        def blob(buf: bytes):
            b = DATA_BLOB()
            b.cbData = len(buf)
            b.pbData = ctypes.cast(ctypes.create_string_buffer(buf),
                                  ctypes.POINTER(ctypes.c_byte))
            return b

        out = DATA_BLOB()
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(blob(blob_bytes)), None, None, None, None,
            0x04, ctypes.byref(out))
        if not ok:
            raise OSError("CryptUnprotectData failed")
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            crypt32.LocalFree(out.pbData)

    def save(self, name, value):
        with open(self._path(name), "wb") as fh:
            fh.write(self._protect(str(value).encode("utf-8")))

    def load(self, name):
        path = self._path(name)
        if not os.path.exists(path):
            raise SecretNotFound(name)
        with open(path, "rb") as fh:
            return self._unprotect(fh.read()).decode("utf-8")

    def delete(self, name):
        try:
            os.remove(self._path(name))
        except FileNotFoundError:
            pass

    def exists(self, name):
        return os.path.exists(self._path(name))


class SecretStore:
    """Facade: namespaced keys per connection. Values never appear in repr."""

    def __init__(self, backend):
        self.backend = backend

    def _key(self, connection, item):
        return "%s-%s-%s" % (SECRET_PREFIX, connection, item)

    def put(self, connection, item, value):
        self.backend.save(self._key(connection, item), value)

    def get(self, connection, item):
        return self.backend.load(self._key(connection, item))

    def delete(self, connection, item):
        self.backend.delete(self._key(connection, item))

    def has(self, connection, item):
        return self.backend.exists(self._key(connection, item))

    def __repr__(self):
        return "SecretStore(backend=%s)" % type(self.backend).__name__


def default_backend(staging_dir=None):
    """DPAPI on Windows (the PC); 0600 file backend elsewhere (staging)."""
    if os.name == "nt":
        return DPAPISecretBackend()
    path = os.path.join(
        staging_dir or os.path.dirname(os.path.abspath(__file__)),
        ".secrets.json")
    return FileSecretBackend(path)


def basic_auth_header(client_id, client_secret):
    raw = ("%s:%s" % (client_id, client_secret)).encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")
