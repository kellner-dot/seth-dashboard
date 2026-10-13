#!/usr/bin/env python3
"""Connection specs: declarative registry for the KaviBOT connections layer.

Adding a connection = one JSON entry in connections.json (+ a small
capability module). No framework changes needed.
"""
import json
import os

SCHEMA = "connections-0.1"
BASE = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(BASE, "connections.json")

CONN_TYPES = ("oauth2", "file_import")


class SpecError(ValueError):
    pass


def load_registry(path=REGISTRY_PATH):
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("schema_version") != SCHEMA:
        raise SpecError("unsupported schema: %r" % (data.get("schema_version"),))
    specs = {}
    for entry in data.get("connections", []):
        errs = validate_spec(entry)
        if errs:
            raise SpecError("invalid spec %r: %s" % (entry.get("name"), "; ".join(errs)))
        specs[entry["name"]] = entry
    return specs


def validate_spec(entry):
    """Return a list of problems (empty = valid)."""
    errs = []
    if not entry.get("name"):
        errs.append("missing name")
    ctype = entry.get("type")
    if ctype not in CONN_TYPES:
        errs.append("type must be one of %s" % (CONN_TYPES,))
    if not entry.get("capabilities"):
        errs.append("missing capabilities")
    if ctype == "oauth2":
        oauth = entry.get("oauth") or {}
        for key in ("auth_url", "token_url", "scopes"):
            if not oauth.get(key):
                errs.append("oauth missing %r" % key)
        if "api_headers" in oauth:
            ah = oauth["api_headers"]
            if not isinstance(ah, dict) or not all(
                    isinstance(k, str) and isinstance(v, str)
                    for k, v in ah.items()):
                errs.append("oauth.api_headers must be {header: credential-ref}")
        if "token_auth" in oauth and oauth["token_auth"] not in ("post", "basic"):
            errs.append("oauth.token_auth must be 'post' or 'basic'")
    if ctype == "file_import":
        if not (entry.get("import") or {}).get("format"):
            errs.append("import missing format")
    return errs


def register(entry, path=REGISTRY_PATH):
    """Append a new connection spec after validation. Returns the name."""
    errs = validate_spec(entry)
    if errs:
        raise SpecError("; ".join(errs))
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    names = [c["name"] for c in data.get("connections", [])]
    if entry["name"] in names:
        raise SpecError("connection %r already registered" % entry["name"])
    data.setdefault("connections", []).append(entry)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    return entry["name"]
