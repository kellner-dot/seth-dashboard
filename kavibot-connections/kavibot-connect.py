#!/usr/bin/env python3
"""kavibot-connect: CLI for the KaviBOT connections layer (staging).

  kavibot-connect.py list
  kavibot-connect.py status <name>
  kavibot-connect.py connect <name>        # interactive OAuth2 (opens browser)
  kavibot-connect.py disconnect <name>
  kavibot-connect.py call <name> <capability> [key=value ...]
  kavibot-connect.py import <name> <path>  # file_import connections
  kavibot-connect.py taste <name>          # speakable summary of last import
  kavibot-connect.py selftest

Never pass secrets as CLI args - connect prompts for them interactively.
"""
import argparse
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from manager import ConnectionManager  # noqa: E402
from secret_store import SecretStore, FileSecretBackend  # noqa: E402


def _manager():
    store = SecretStore(FileSecretBackend(os.path.join(BASE, ".secrets.json")))
    return ConnectionManager(store=store)


def _print(obj):
    print(json.dumps(obj, indent=2, default=str))


def main(argv=None):
    ap = argparse.ArgumentParser(description="KaviBOT connections (staging)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list")
    p = sub.add_parser("status"); p.add_argument("name")
    p = sub.add_parser("connect"); p.add_argument("name")
    p = sub.add_parser("disconnect"); p.add_argument("name")
    p = sub.add_parser("call"); p.add_argument("name"); p.add_argument("capability")
    p.add_argument("params", nargs="*", help="key=value")
    p = sub.add_parser("import"); p.add_argument("name"); p.add_argument("path")
    p = sub.add_parser("taste"); p.add_argument("name")
    sub.add_parser("selftest")

    args = ap.parse_args(argv)
    mgr = _manager()

    if args.cmd == "list":
        _print(mgr.list_all())
    elif args.cmd == "status":
        _print(mgr.status(args.name))
    elif args.cmd == "connect":
        _print(mgr.connect(args.name))
    elif args.cmd == "disconnect":
        _print(mgr.disconnect(args.name))
    elif args.cmd == "call":
        params = {}
        for kv in args.params:
            k, _, v = kv.partition("=")
            params[k] = v
        _print(mgr.call(args.name, args.capability, **params))
    elif args.cmd == "import":
        _print(mgr.import_file(args.name, args.path))
    elif args.cmd == "taste":
        _print(mgr.taste(args.name))
    elif args.cmd == "selftest":
        import unittest
        suite = unittest.defaultTestLoader.discover(
            os.path.join(BASE, "tests"))
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
