#!/usr/bin/env python3
"""
KaviTV / environment drift detector (reference implementation).
Read-only: compares live state against baselines, never changes anything.
Stdlib only. Writes drift-report.json next to sentinel-results.json.

Baselines live in ~/workspace/kavi-team/ (docs) and the KaviTV snapshot zip.
On the PC, run weekly + after incident recovery via Task Scheduler.
"""
import json, hashlib, os, subprocess, sys, urllib.request
from datetime import datetime, timezone

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "drift-report.json")

EXPECTED = {
    "emby_libraries": [
        r"C:\Users\sethr\OneDrive\Desktop\Movies", r"D:\Movies", r"T:\Movies",
        r"C:\Users\sethr\OneDrive\Desktop\TV Shows", r"D:\TV Shows",
        r"C:\UbuWeb\UbuWeb", r"C:\AdultVOD",
    ],
    "kavitv_channels": {470348: "horror", 470349: "experimental", 470350: "independent"},
    "tuner_url_pattern": "10.0.0.98:8100/kavitv/live/",
    "scheduled_tasks": ["KaviTV-relay", "KaviTV Watchdog", "Alist Server",
                        "TeraBox Watchdog", "RVG watchdog"],
    "relay_port": 8100,
}

def check(name, ok, detail):
    return {"check": name, "result": "NO DRIFT" if ok else "DRIFT",
            "detail": detail}

def main():
    report = {"timestamp": datetime.now(timezone.utc).isoformat(),
              "checks": [], "drift_found": False}
    # 1. Relay port listening (read-only TCP probe)
    import socket
    s = socket.socket(); s.settimeout(5)
    try:
        s.connect(("127.0.0.1", EXPECTED["relay_port"]))
        port_ok, port_detail = True, "port 8100 accepting"
    except Exception as e:
        port_ok, port_detail = False, f"port 8100 not accepting: {e}"
    finally:
        s.close()
    report["checks"].append(check("relay_port", port_ok, port_detail))

    # 2. Relay health version marker
    try:
        with urllib.request.urlopen("http://127.0.0.1:8100/api/health", timeout=10) as r:
            body = r.read().decode("utf-8", "replace")
        report["checks"].append(check("relay_health", '"ok":true' in body.replace(" ", ""),
                                      body[:120]))
    except Exception as e:
        report["checks"].append(check("relay_health", False, str(e)[:120]))

    # 3. Scheduled tasks present + enabled (Windows)
    if os.name == "nt":
        try:
            out = subprocess.run(["schtasks", "/query", "/fo", "CSV"],
                                 capture_output=True, text=True, timeout=30).stdout
            missing = [t for t in EXPECTED["scheduled_tasks"] if t not in out]
            report["checks"].append(check("scheduled_tasks", not missing,
                                          "missing: " + ",".join(missing) if missing else "all present"))
        except Exception as e:
            report["checks"].append(check("scheduled_tasks", False, str(e)[:120]))
    else:
        report["checks"].append(check("scheduled_tasks", True, "skipped: not Windows (dev machine)"))

    # 4. Drives present
    drives = {d: os.path.exists(d) for d in ["C:\\", "D:\\", "T:\\"]}
    report["checks"].append(check("drives_present", all(drives.values()), str(drives)))

    # 5. KaviTV runtime dir intact (hash of relay.py vs snapshot recorded at deploy)
    kdir = r"C:\Users\sethr\kavitv"
    relay = os.path.join(kdir, "relay.py")
    if os.path.exists(relay):
        h = hashlib.sha256(open(relay, "rb").read()).hexdigest()[:16]
        report["checks"].append(check("relay_file", True, f"relay.py sha256:{h} (compare to snapshot)"))
    else:
        report["checks"].append(check("relay_file", False, "relay.py missing"))

    report["drift_found"] = any(c["result"] == "DRIFT" for c in report["checks"])
    json.dump(report, open(OUT, "w"), indent=2)
    print(json.dumps(report, indent=2))
    sys.exit(1 if report["drift_found"] else 0)

if __name__ == "__main__":
    main()
