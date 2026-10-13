#!/usr/bin/env python3
"""Apple Music library import pilot (type: file_import).

Seth: Music app (Mac) or iTunes (Windows) -> File -> Library ->
Export Library -> save Library.xml. Then:

    kavibot-connect.py import apple_music "C:\\path\\to\\Library.xml"

Parses the plist into a taste profile: top artists/albums/tracks by play
count, genre mix, loved tracks, recently played/added, playlist inventory.
The XML never leaves the PC; only the derived profile enters KaviBOT's
knowledge area. No account, no network, no cost.

Capabilities:
  import_library(path, profile_dir) -> {ok, profile_path, summary}
  taste_summary(profile_path)       -> one-paragraph natural-language summary
"""
import collections
import datetime
import json
import os
import plistlib

SPEC_NAME = "apple_music"
PROFILE_SCHEMA = "taste-profile-0.1"


class ImportError_(RuntimeError):
    pass


def _as_text(value, default=""):
    return value if isinstance(value, str) else default


def parse_library_xml(path):
    """Parse Library.xml -> raw track list. Raises ImportError_ on problems."""
    if not os.path.exists(path):
        raise ImportError_("file not found: %s" % path)
    try:
        with open(path, "rb") as fh:
            lib = plistlib.load(fh)
    except Exception as exc:
        raise ImportError_("not a readable Library.xml plist: %s" % exc)
    tracks = lib.get("Tracks")
    if not isinstance(tracks, dict):
        raise ImportError_("no 'Tracks' dictionary in %s" % path)
    parsed = []
    for tid, t in tracks.items():
        if not isinstance(t, dict):
            continue
        parsed.append({
            "name": _as_text(t.get("Name"), "(unknown)"),
            "artist": _as_text(t.get("Artist"), "(unknown artist)"),
            "album": _as_text(t.get("Album"), ""),
            "genre": _as_text(t.get("Genre"), ""),
            "play_count": int(t.get("Play Count") or 0),
            "rating": int(t.get("Rating") or 0),  # 0-100
            "loved": bool(t.get("Loved", False)),
            "date_added": t.get("Date Added"),
            "last_played": t.get("Play Date UTC"),
        })
    playlists = []
    for pl in lib.get("Playlists", []) or []:
        if isinstance(pl, dict) and pl.get("Name"):
            items = pl.get("Playlist Items") or []
            playlists.append({"name": pl["Name"], "tracks": len(items)})
    return {"tracks": parsed, "playlists": playlists}


def build_profile(parsed):
    tracks = parsed["tracks"]
    artist_plays = collections.Counter()
    album_plays = collections.Counter()
    track_plays = collections.Counter()
    genres = collections.Counter()
    loved = []
    for t in tracks:
        artist_plays[t["artist"]] += t["play_count"]
        if t["album"]:
            album_plays["%s - %s" % (t["artist"], t["album"])] += t["play_count"]
        track_plays["%s - %s" % (t["artist"], t["name"])] += t["play_count"]
        if t["genre"]:
            genres[t["genre"]] += 1
        if t["loved"]:
            loved.append("%s - %s" % (t["artist"], t["name"]))

    def dt_key(t, field):
        v = t.get(field)
        return v if isinstance(v, datetime.datetime) else datetime.datetime.min

    recent_played = sorted(
        (t for t in tracks if isinstance(t.get("last_played"), datetime.datetime)),
        key=lambda t: t["last_played"], reverse=True)[:10]
    recent_added = sorted(
        (t for t in tracks if isinstance(t.get("date_added"), datetime.datetime)),
        key=lambda t: t["date_added"], reverse=True)[:10]

    return {
        "schema": PROFILE_SCHEMA,
        "generated_utc": datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        "total_tracks": len(tracks),
        "total_plays": sum(t["play_count"] for t in tracks),
        "top_artists": artist_plays.most_common(25),
        "top_albums": album_plays.most_common(25),
        "top_tracks": track_plays.most_common(25),
        "genres": genres.most_common(20),
        "loved_tracks": sorted(loved)[:50],
        "recently_played": ["%s - %s" % (t["artist"], t["name"])
                            for t in recent_played],
        "recently_added": ["%s - %s" % (t["artist"], t["name"])
                           for t in recent_added],
        "playlists": parsed["playlists"][:50],
    }


def summarize_profile(profile):
    """One-paragraph, speakable summary of the taste profile."""
    top_a = ", ".join(a for a, _ in profile["top_artists"][:5]) or "nothing yet"
    top_g = ", ".join(g for g, _ in profile["genres"][:4]) or "unclassified"
    lines = [
        "Library: %d tracks, %d total plays." % (
            profile["total_tracks"], profile["total_plays"]),
        "Most played artists: %s." % top_a,
        "The collection leans %s." % top_g,
    ]
    if profile["loved_tracks"]:
        lines.append("Loved: %s." %
                     ", ".join(profile["loved_tracks"][:5]))
    if profile["recently_played"]:
        lines.append("Recently spinning: %s." %
                     ", ".join(profile["recently_played"][:3]))
    return " ".join(lines)


def import_library(path, profile_dir):
    """Full import: parse -> profile JSON on disk -> summary."""
    parsed = parse_library_xml(path)
    profile = build_profile(parsed)
    os.makedirs(profile_dir, exist_ok=True)
    profile_path = os.path.join(profile_dir, "apple_music_taste.json")
    with open(profile_path, "w", encoding="utf-8") as fh:
        json.dump(profile, fh, indent=2, default=str)
    return {"ok": True, "profile_path": profile_path,
            "summary": summarize_profile(profile),
            "total_tracks": profile["total_tracks"]}


def taste_summary(profile_path):
    with open(profile_path, "r", encoding="utf-8") as fh:
        profile = json.load(fh)
    if profile.get("schema") != PROFILE_SCHEMA:
        raise ImportError_("unknown profile schema")
    return {"ok": True, "summary": summarize_profile(profile)}


CAPABILITIES = {
    "import_library": import_library,
    "taste_summary": taste_summary,
}
