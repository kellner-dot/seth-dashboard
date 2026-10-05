#!/usr/bin/env python3
"""KaviTV relay watchdog — external supervisor.

Polls the relay's /api/deep-health every 30s. Silent on success
(a watchdog that messages every check gets muted within a day).
On 3 consecutive failures: kills the relay process tree and restarts it.

Idempotent: never starts a second relay (checks port + process first).
Test it once by hand: kill the relay, run this, confirm restart + log line.

Logs: C:\\Users\\sethr\\kavitv\\logs\\watchdog.log
Run:  pythonw watchdog.py   (or its own NSSM service / scheduled task)
"""

import json
import logging
import logging.handlers
import os
import socket
import subprocess
import sys
import time
import urllib.request

BASE_DIR = r"C:\Users\sethr\kavitv"
LOG_DIR = os.path.join(BASE_DIR, "logs")
RELAY_PY = os.path.join(BASE_DIR, "relay.py")
PYTHONW = sys.executable.replace("python.exe", "pythonw.exe")

HEALTH_URL = "http://127.0.0.1:8100/api/deep-health"
INTERVAL = 30
FAIL_THRESHOLD = 3
PORT = 8100


def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger("kavi-watchdog")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")
    fh = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, "watchdog.log"),
        maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


log = setup_logging()


def port_open():
    s = socket.socket()
    s.settimeout(2)
    try:
        s.connect(("127.0.0.1", PORT))
        return True
    except OSError:
        return False
    finally:
        s.close()


def deep_health_ok():
    try:
        req = urllib.request.Request(HEALTH_URL, method="GET")
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.status != 200:
                return False
            body = json.loads(r.read().decode("utf-8", "replace"))
            return bool(body.get("ok"))
    except Exception as e:  # noqa: BLE001
        log.debug("health probe failed: %s", e)
        return False


def relay_pids():
    """PIDs of pythonw running relay.py (via WMIC, stdlib-only)."""
    pids = []
    try:
        out = subprocess.run(
            ["wmic", "process", "where",
             "name='pythonw.exe'", "get", "ProcessId,CommandLine",
             "/format:csv"],
            capture_output=True, text=True, timeout=15).stdout
        for line in out.splitlines():
            if "relay.py" in line:
                parts = [p.strip() for p in line.split(",")]
                for p in parts:
                    if p.isdigit():
                        pids.append(int(p))
    except Exception as e:  # noqa: BLE001
        log.warning("could not enumerate relay processes: %s", e)
    return pids


def kill_relay():
    for pid in relay_pids():
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                           capture_output=True, timeout=15)
            log.info("killed relay pid=%s", pid)
        except Exception as e:  # noqa: BLE001
            log.warning("kill pid=%s failed: %s", pid, e)
    # Also kill orphaned ffmpeg children of the relay
    try:
        out = subprocess.run(
            ["wmic", "process", "where", "name='ffmpeg.exe'",
             "get", "ProcessId,CommandLine", "/format:csv"],
            capture_output=True, text=True, timeout=15).stdout
        for line in out.splitlines():
            if "pipe:1" in line:  # our streaming ffmpegs use pipe:1
                parts = [p.strip() for p in line.split(",")]
                for p in parts:
                    if p.isdigit():
                        subprocess.run(["taskkill", "/PID", p, "/F"],
                                       capture_output=True, timeout=10)
                        log.info("killed orphan ffmpeg pid=%s", p)
    except Exception as e:  # noqa: BLE001
        log.warning("orphan ffmpeg sweep failed: %s", e)
    time.sleep(3)


def start_relay():
    if port_open():
        log.warning("port %d already open, not starting a second relay", PORT)
        return False
    if relay_pids():
        log.warning("relay process already exists, not starting another")
        return False
    exe = PYTHONW if os.path.exists(PYTHONW) else sys.executable
    subprocess.Popen([exe, RELAY_PY],
                     cwd=BASE_DIR,
                     stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL,
                     stdin=subprocess.DEVNULL)
    log.info("relay start requested")
    time.sleep(8)
    if deep_health_ok():
        log.info("relay restarted OK")
        return True
    log.error("relay restart did not come healthy")
    return False


def main():
    log.info("watchdog started (interval=%ds, threshold=%d)",
             INTERVAL, FAIL_THRESHOLD)
    fails = 0
    while True:
        try:
            if deep_health_ok():
                fails = 0  # silent on success
            else:
                fails += 1
                log.warning("health FAIL %d/%d", fails, FAIL_THRESHOLD)
                if fails >= FAIL_THRESHOLD:
                    log.error("threshold reached — restarting relay")
                    kill_relay()
                    start_relay()
                    fails = 0
        except Exception as e:  # noqa: BLE001
            log.exception("watchdog loop error: %s", e)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
