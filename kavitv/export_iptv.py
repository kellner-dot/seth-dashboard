#!/usr/bin/env python3
"""KaviTV IPTV exporter — Flix Pro Player / Emby Live TV.

Generates from the three flagship 24/7 schedules (Horror 30, Experimental 31,
Independent 32):
  kavitv.m3u  — M3U playlist, EXTINF with tvg-id / tvg-logo / group-title.
                Stream URLs point at the PC-side KaviTV relay
                (http://<PC_LAN>:8100/kavitv/live/<id>.m3u8), which 302s to
                the current program's Emby HLS stream with the API key added
                server-side. No credentials in this file — ever.
  kavitv.xml  — full XMLTV: <channel> entries + <programme> entries
                (title/start/stop/desc) from the published schedules
                (today + tomorrow).

Public-safe: titles, years, genres, opaque refs only. The relay host is a
LAN address, not a secret. No api_key / tokens / passwords anywhere.

Usage: python3 export_iptv.py [--no-push] [--pc-host 10.0.0.98] [--pc-port 8100]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.expanduser("~/workspace/seth-dashboard/kavitv")
SCHED_DIR = os.path.join(HERE, "schedules")
ET_Z = ZoneInfo("America/New_York")

# schedule key -> public channel id
FLAGSHIPS = {"30": "horror", "31": "experimental", "32": "independent"}
# Per-channel logos (authoritative source: Google Drive channel-logo collection).
# These MUST stay in sync with the Drive files; the schedule refresh must
# never revert channels to a single shared logo.
CHANNEL_LOGOS = {"horror": "logo-horror.jpg",
                 "experimental": "logo-experimental.jpg",
                 "independent": "logo-independent.jpg"}
PAGES_BASE = "https://kellner-dot.github.io/seth-dashboard/kavitv"

SECRET_PAT = re.compile(
    r"api[_-]?key\s*[:=]|password\s*[:=]|passwd\s*[:=]|"
    r"(?<![a-z])token\s*[:=]|X-Emby-Authorization|"
    r"secret\s*[:=]|bearer\s+[A-Za-z0-9_\-]{8,}",
    re.IGNORECASE)


def load_json(path):
    with open(path) as f:
        return json.load(f)


def channel_meta():
    """id -> {name, tagline} from the published channels.json."""
    data = load_json(os.path.join(DASH, "channels.json"))
    return {c["id"]: c for c in data["channels"]}


def sched_items(date_str, key):
    day = load_json(os.path.join(SCHED_DIR, f"{date_str}.json"))
    return day.get(key, {}).get("items", [])


def abs_dt(date_str, hhmm):
    """Broadcast-day HH:MM -> aware ET datetime. Day runs 06:00 -> 06:00."""
    h, m = (int(x) for x in hhmm.split(":"))
    d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=ET_Z)
    if h < 6:  # 00:00-05:59 belongs to the next calendar day
        d += timedelta(days=1)
    return d.replace(hour=h, minute=m, second=0, microsecond=0)


def xmltv_dt(dt):
    return dt.strftime("%Y%m%d%H%M%S %z")


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;") \
        .replace(">", "&gt;").replace('"', "&quot;")


def build_m3u(meta, pc_host, pc_port):
    lines = [f'#EXTM3U x-tvg-url="{PAGES_BASE}/kavitv.xml"']
    for key, cid in FLAGSHIPS.items():
        c = meta[cid]
        lines.append(
            f'#EXTINF:-1 tvg-id="kavitv.{cid}" '
            f'tvg-logo="{PAGES_BASE}/{CHANNEL_LOGOS[cid]}" '
            f'group-title="KaviTV",{c["name"]}')
        lines.append(f"http://{pc_host}:{pc_port}/kavitv/live/{cid}.m3u8")
    return "\n".join(lines) + "\n"


def build_xmltv(meta):
    """Programmes come from the published epg.json — the exact same source
    the TV client reads, so the XMLTV guide can never drift from it."""
    epg = load_json(os.path.join(DASH, "epg.json"))
    epg_ch = {c["id"]: c for c in epg["channels"]}
    out = ['<?xml version="1.0" encoding="UTF-8"?>', "<tv>"]
    for key, cid in FLAGSHIPS.items():
        c = meta[cid]
        out.append(
            f'  <channel id="kavitv.{cid}">'
            f"<display-name>{esc(c['name'])}</display-name>"
            f'<icon src="{PAGES_BASE}/{CHANNEL_LOGOS[cid]}"/></channel>')
    for key, cid in FLAGSHIPS.items():
        for p in epg_ch[cid].get("programs", []):
            start = datetime.fromisoformat(p["start"])
            end = datetime.fromisoformat(p["end"])
            genres = ", ".join(p.get("genres") or [])
            desc = f"{p.get('year', '')} - {genres}".strip(" -")
            if p.get("overview"):
                desc += ". " + p["overview"][:200]
            out.append(
                f'  <programme start="{xmltv_dt(start)}" '
                f'stop="{xmltv_dt(end)}" channel="kavitv.{cid}">'
                f"<title>{esc(p['title'])}</title>"
                f"<desc>{esc(desc)}</desc></programme>")
    out.append("</tv>")
    return "\n".join(out) + "\n"


def validate(m3u, xmltv, meta):
    errors = []
    # --- M3U ---
    entries = re.findall(
        r'#EXTINF:-1 tvg-id="([^"]+)" tvg-logo="([^"]+)" '
        r'group-title="([^"]+)",([^\n]+)\n([^\n]+)', m3u)
    if len(entries) != 3:
        errors.append(f"M3U: expected 3 entries, found {len(entries)}")
    for tvg_id, logo, group, name, url in entries:
        if group != "KaviTV":
            errors.append(f"M3U: bad group-title {group}")
        cid = tvg_id.split(".")[-1]
        expect_logo = f"{PAGES_BASE}/{CHANNEL_LOGOS.get(cid, '')}"
        if logo != expect_logo:
            errors.append(f"M3U: {tvg_id} logo {logo} != expected {expect_logo}")
        if not url.startswith("http://") or ".m3u8" not in url:
            errors.append(f"M3U: bad URL {url}")
    # --- XMLTV well-formed + content ---
    try:
        root = ET.fromstring(xmltv)
    except ET.ParseError as e:
        errors.append(f"XMLTV parse error: {e}")
        root = None
    if root is not None:
        chans = root.findall("channel")
        progs = root.findall("programme")
        if len(chans) != 3:
            errors.append(f"XMLTV: expected 3 channels, found {len(chans)}")
        if len(progs) < 10:
            errors.append(f"XMLTV: too few programmes ({len(progs)})")
        for p in progs:
            if not (p.get("start") and p.get("stop") and p.get("channel")
                    and p.find("title") is not None):
                errors.append("XMLTV: programme missing fields")
                break
    # --- alignment: XMLTV programmes ARE epg.json (same source) ---
    epg = load_json(os.path.join(DASH, "epg.json"))
    for key, cid in FLAGSHIPS.items():
        ech = next(c for c in epg["channels"] if c["id"] == cid)
        n_xml = xmltv.count(f'channel="kavitv.{cid}"')
        n_epg = len(ech.get("programs", []))
        if n_xml != n_epg:
            errors.append(
                f"alignment: {cid} xmltv programmes {n_xml} != epg.json {n_epg}")
    # --- secret scan ---
    for label, blob in (("m3u", m3u), ("xmltv", xmltv)):
        m = SECRET_PAT.search(blob)
        if m:
            errors.append(f"SECRET LEAK in {label}: matched {m.group(0)!r}")
    return errors


def git_push(paths, msg):
    repo = os.path.expanduser("~/workspace/seth-dashboard")
    def run(*a):
        return subprocess.run(a, cwd=repo, capture_output=True, text=True)
    run("git", "add", *paths)
    st = run("git", "status", "--porcelain")
    if not st.stdout.strip():
        print("nothing to commit")
        return True
    run("git", "commit", "-m", msg)
    for attempt in (1, 2):
        r = run("git", "pull", "--rebase")
        p = run("git", "push")
        if p.returncode == 0:
            print("pushed OK")
            return True
        print(f"push attempt {attempt} failed, retrying")
    print("PUSH FAILED")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--pc-host", default="10.0.0.98")
    ap.add_argument("--pc-port", type=int, default=8100)
    a = ap.parse_args()

    meta = channel_meta()
    m3u = build_m3u(meta, a.pc_host, a.pc_port)
    xmltv = build_xmltv(meta)

    errors = validate(m3u, xmltv, meta)
    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    print(f"validated: 3 channels, "
          f"{xmltv.count('<programme')} programmes, no secrets")

    os.makedirs(DASH, exist_ok=True)
    m3u_path = os.path.join(DASH, "kavitv.m3u")
    xml_path = os.path.join(DASH, "kavitv.xml")
    with open(m3u_path, "w") as f:
        f.write(m3u)
    with open(xml_path, "w") as f:
        f.write(xmltv)
    # Per-channel logos: copied from the local logo source dir into the
    # dashboard so the Pages site serves each channel's own logo.
    # Authoritative originals live in Google Drive (channel-logo collection).
    import shutil
    logo_src_dir = os.environ.get("KAVITV_LOGO_SRC",
                                  os.path.expanduser("~/workspace/kavitv-logos"))
    for cid, fname in CHANNEL_LOGOS.items():
        src = os.path.join(logo_src_dir, fname)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(DASH, fname))
        else:
            print(f"WARNING: missing logo source {src} for channel {cid}")

    if not a.no_push:
        ok = git_push(["kavitv/kavitv.m3u", "kavitv/kavitv.xml",
                       "kavitv/logo-horror.jpg", "kavitv/logo-experimental.jpg",
                       "kavitv/logo-independent.jpg"],
                      "KaviTV: M3U + XMLTV export for Flix Pro / Emby Live TV")
        sys.exit(0 if ok else 1)
    print("wrote (no push):", m3u_path, xml_path)


if __name__ == "__main__":
    main()
