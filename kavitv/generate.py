#!/usr/bin/env python3
"""KaviTV single-source-of-truth schedule generator (stdlib only).

Reads:  library.json  (hand-maintained movie pools per channel)
Writes (atomically): timeline.json  (relay's schedule — UTC, gapless, 72h)
                     kavitv.xml     (XMLTV guide — derived from timeline)
                     kavitv.m3u     (M3U playlist — tvg-id/logo in sync)

Deterministic per-day seed (DizqueTV model): regeneration is stateless.
The relay and the guide read the SAME timeline — drift is impossible
by construction.

Usage: generate.py [library.json] [out_dir]
"""
import hashlib
import json
import os
import random
import sys
from datetime import date, datetime, timedelta, timezone
from xml.sax.saxutils import escape as xml_escape

UTC = timezone.utc
WINDOW_DAYS = 3
RELAY_BASE = "http://10.0.0.98:8100"


def day_seed(cid, day):
    h = hashlib.sha256(f"{cid}:{day.isoformat()}".encode()).digest()
    return int.from_bytes(h[:8], "big")


def build_day(cid, day, movies, bumpers, bumper_every=1):
    """Gapless 24h tiling. Movies never cut. Returns list of slots."""
    rng = random.Random(day_seed(cid, day))
    pool = movies[:]
    rng.shuffle(pool)
    day_start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    day_end = day_start + timedelta(days=1)
    slots = []
    t = day_start
    i = 0
    since_bumper = 0
    pool_idx = 0
    while t < day_end:
        # Bumper interstitial every N movies
        if bumpers and since_bumper >= bumper_every:
            b = rng.choice(bumpers)
            dur = timedelta(seconds=b["duration_s"])
            if t + dur <= day_end:
                slots.append(_slot(t, t + dur, b, "bumper"))
                t += dur
            since_bumper = 0
            continue
        m = pool[pool_idx % len(pool)]
        pool_idx += 1
        dur = timedelta(seconds=m["duration_s"])
        if t + dur <= day_end:
            slots.append(_slot(t, t + dur, m, "movie"))
            t += dur
            since_bumper += 1
        else:
            # Fill remaining gap with bumpers (largest-fit-first)
            gap = (day_end - t).total_seconds()
            t = _fill_gap(slots, t, gap, bumpers, rng)
            t = day_end
    # Gapless invariant (compare as ISO strings)
    ds_iso = day_start.isoformat()
    de_iso = day_end.isoformat()
    for k in range(len(slots) - 1):
        assert slots[k]["end"] == slots[k + 1]["start"], \
            f"gap/overlap in {cid} {day}"
    assert slots[0]["start"] == ds_iso and slots[-1]["end"] == de_iso, \
        f"day not fully covered in {cid} {day}: " \
        f"{slots[0]['start']}..{slots[-1]['end']}"
    return slots


def _slot(start, end, media, kind):
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "emby_id": media["emby_id"],
        "kind": kind,
        "title": media["title"],
        "year": media.get("year"),
        "duration_s": int((end - start).total_seconds()),
        "genres": media.get("genres", []),
        "overview": media.get("overview", ""),
    }


def _fill_gap(slots, t, gap_s, bumpers, rng):
    """Tile bumpers into a gap. If no bumpers fit, extend last slot."""
    if not bumpers:
        # No bumpers: extend the last movie slot to cover (rare)
        if slots:
            slots[-1]["end"] = (t + timedelta(seconds=gap_s)).isoformat()
            slots[-1]["duration_s"] = int(
                (datetime.fromisoformat(slots[-1]["end"]) -
                 datetime.fromisoformat(slots[-1]["start"])).total_seconds())
        return t + timedelta(seconds=gap_s)
    sorted_b = sorted(bumpers, key=lambda b: -b["duration_s"])
    while gap_s > 0:
        placed = False
        for b in sorted_b:
            if b["duration_s"] <= gap_s:
                dur = timedelta(seconds=b["duration_s"])
                slots.append(_slot(t, t + dur, b, "bumper"))
                t += dur
                gap_s -= b["duration_s"]
                placed = True
                break
        if not placed:
            # Nothing fits; extend last bumper slightly
            if slots:
                extra = timedelta(seconds=gap_s)
                new_end = t + extra
                slots[-1]["end"] = new_end.isoformat()
                s = datetime.fromisoformat(slots[-1]["start"])
                slots[-1]["duration_s"] = int((new_end - s).total_seconds())
            t += timedelta(seconds=gap_s)
            gap_s = 0
    return t


def xmltv_from_timeline(timeline, lib):
    """Pure transform: timeline slots -> XMLTV."""
    # Build poster lookup: emby_id -> poster URL
    posters = {}
    for ch in lib["channels"].values():
        for m in ch["movies"]:
            if m.get("poster"):
                posters[m["emby_id"]] = m["poster"]
        for b in ch.get("bumpers", []):
            if b.get("poster"):
                posters[b["emby_id"]] = b["poster"]

    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<tv generator-info-name="kavitv-scheduler">']
    for cid, ch in lib["channels"].items():
        out.append(f'  <channel id="{cid}">')
        out.append(f'    <display-name>{xml_escape(ch["name"])}</display-name>')
        out.append(f'    <icon src="{xml_escape(ch["logo"])}"/>')
        out.append('  </channel>')
    for cid, chdata in timeline["channels"].items():
        for s in chdata["slots"]:
            st = _xmltv_ts(s["start"])
            en = _xmltv_ts(s["end"])
            out.append(
                f'  <programme start="{st}" stop="{en}" channel="{cid}">')
            out.append(f'    <title>{xml_escape(s["title"])}</title>')
            if s.get("year"):
                out.append(f'    <date>{s["year"]}</date>')
            if s.get("overview"):
                out.append(f'    <desc>{xml_escape(s["overview"][:400])}</desc>')
            for g in s.get("genres", []):
                out.append(f'    <category>{xml_escape(g)}</category>')
            # Program poster (fixes missing posters in Emby guide)
            poster = posters.get(s.get("emby_id"))
            if poster:
                out.append(f'    <icon src="{xml_escape(poster)}"/>')
            out.append('  </programme>')
    out.append('</tv>')
    return "\n".join(out) + "\n"


def _xmltv_ts(iso):
    dt = datetime.fromisoformat(iso)
    return dt.strftime("%Y%m%d%H%M%S +0000")


def m3u_from_library(lib):
    out = ["#EXTM3U"]
    for cid, ch in lib["channels"].items():
        out.append(
            f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{ch["name"]}" '
            f'tvg-logo="{ch["logo"]}" '
            f'group-title="KaviTV",{ch["name"]}')
        out.append(f"{RELAY_BASE}/kavitv/live/{ch['slug']}.ts")
    return "\n".join(out) + "\n"


def atomic_write(path, data):
    tmp = path + ".new"
    mode = "w" if isinstance(data, str) else "wb"
    with open(tmp, mode) as f:
        f.write(data)
    os.replace(tmp, path)



def validate_m3u(m3u_text, lib):
    """CI check: enforce tuner config invariants on generated M3U."""
    errors = []
    lines = m3u_text.strip().split("\n")
    if not lines[0].startswith("#EXTM3U"):
        errors.append("missing #EXTM3U header")
    # Check each channel has .ts URL (required for SharedHttpStream)
    for cid, ch in lib["channels"].items():
        slug = ch["slug"]
        expected = f"/kavitv/live/{slug}.ts"
        if expected not in m3u_text:
            errors.append(f"{cid}: missing .ts URL {expected}")
        # tvg-id must match channel id exactly
        if f'tvg-id="{cid}"' not in m3u_text:
            errors.append(f"{cid}: tvg-id mismatch")
        # No tvg-chno (Seth wants no channel numbers)
        if "tvg-chno" in m3u_text:
            errors.append("tvg-chno found (should be absent)")
            break
    if errors:
        raise ValueError("M3U validation failed: " + "; ".join(errors))
    return True


def main():
    lib_path = sys.argv[1] if len(sys.argv) > 1 else "library.json"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    lib = json.load(open(lib_path))
    today = date.today()
    days = [today + timedelta(days=d) for d in range(WINDOW_DAYS)]

    timeline = {
        "generated_at": datetime.now(UTC).isoformat(),
        "window_days": WINDOW_DAYS,
        "channels": {},
    }
    for cid, ch in lib["channels"].items():
        slots = []
        for d in days:
            slots += build_day(cid, d, ch["movies"], ch.get("bumpers", []))
        timeline["channels"][cid] = {"slots": slots}

    atomic_write(os.path.join(out_dir, "timeline.json"),
                 json.dumps(timeline, indent=1))
    atomic_write(os.path.join(out_dir, "kavitv.xml"),
                 xmltv_from_timeline(timeline, lib))
    m3u_text = m3u_from_library(lib)
    validate_m3u(m3u_text, lib)
    atomic_write(os.path.join(out_dir, "kavitv.m3u"), m3u_text)

    n_slots = sum(len(c["slots"]) for c in timeline["channels"].values())
    print(json.dumps({"channels": len(lib["channels"]), "slots": n_slots,
                      "days": WINDOW_DAYS}))


if __name__ == "__main__":
    main()
