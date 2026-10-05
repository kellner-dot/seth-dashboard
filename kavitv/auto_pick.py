#!/usr/bin/env python3
"""
KaviTV auto-picker — builds a fresh channel lineup that respects Seth's
hard constraints.

Reads the pool of verified movies from library.json (plus optional new
candidates from ~/workspace/kavitv-research/new-movie-candidates.md),
assigns each movie to its best-fit channel, and writes a new library.json.

Usage:
    python3 auto_pick.py [--horror N] [--experimental N] [--independent N]

Defaults: 14 horror, 12 experimental, 10 independent.

Constraints enforced (see ~/workspace/kavitv-research/auto-picker-constraints.md):
  1. Storage: C: (UbuWeb .strm) or D: (local) only. T: (TeraBox) is NEVER used.
  2. IDs: only Emby IDs from the verified pool or the candidates file.
  3. Theme: each movie is scored against its channel's theme keywords.
  4. No duplicates: a movie appears on at most ONE channel.
  5. Repeat limit: pool per channel is sized so no movie plays more than
     twice per day (ceil(daily_slots / 2) minimum).
  6. Posters: movies with place cards are preferred.
  7. No bumpers / intermission items are ever added.
  8. Corrected metadata (titles/years) is preserved from the source records.

The picker is deterministic: same inputs -> same lineup. A state file
(auto-pick-state.json) tracks recent picks so lineups rotate over time.
It fails closed: if any channel would end up with zero movies (which
generate.py cannot schedule), it aborts without writing anything.
"""

import argparse
import json
import os
import re
import shutil
import sys
from collections import Counter
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
LIBRARY_PATH = os.path.join(HERE, "library.json")
POSTERS_DIR = os.path.join(HERE, "posters")
RESEARCH_DIR = os.path.expanduser("~/workspace/kavitv-research")
CANDIDATES_PATH = os.path.join(RESEARCH_DIR, "new-movie-candidates.md")
STATE_PATH = os.path.join(RESEARCH_DIR, "auto-pick-state.json")
DEAD_IDS_PATH = os.path.join(RESEARCH_DIR, "dead-ids.txt")
LOG_PATH = os.path.join(RESEARCH_DIR, "auto-pick.log")

# ---------------------------------------------------------------------------
# Constraint data
# ---------------------------------------------------------------------------

# Movies known to have a fast LOCAL copy on D: even though their Emby ID
# lives in the 37xxxx (TeraBox) range. Source: rebuild-inventory.md.
# Everything else in 37xxxx is T: (throttled) and is excluded outright.
DRIVE_OVERRIDES = {
    "373072": "D",  # The Monkey (2025) — 1.6 GB local copy at D:\Movies\The Monkey.mp4
}

# Emby ID ranges verified against the live Emby inventory
# (~/workspace/kavitv-research/rebuild-inventory.md):
#   C: UbuWeb .strm items ......... 21xxxx / 24xxxx  (fast local)
#   T: TeraBox cloud via rclone .... 37xxxx          (throttled — excluded)
def drive_of(emby_id):
    """Return 'C', 'D', or 'T' for an Emby ID. Unknown prefixes -> 'C'
    is NOT assumed; anything unrecognised is treated as untrusted ('?')
    and excluded, so a future ID-range change fails closed, not open."""
    eid = str(emby_id)
    if eid in DRIVE_OVERRIDES:
        return DRIVE_OVERRIDES[eid]
    if eid.startswith("37"):
        return "T"
    if eid.startswith("21") or eid.startswith("24"):
        return "C"
    return "?"

FAST_DRIVES = {"C", "D"}

# Theme keywords per channel. Matched (case-insensitive) against the
# movie's title + genres + overview + director.
THEME_KEYWORDS = {
    "kavitv.horror": {
        "core": ["horror"],
        "keywords": [
            "horror", "thriller", "giallo", "slasher", "creature", "dread",
            "disturbing", "monster", "zombie", "vampire", "terror",
            "nightmare", "occult", "gore", "possession", "haunted", "killer",
            "dark",
        ],
    },
    "kavitv.experimental": {
        "core": ["experimental"],
        "keywords": [
            "experimental", "avant-garde", "avant garde", "structural",
            "video art", "brakhage", "frampton", "kubelka", "sharits",
            "snow", "menken", "deren", "anger", "conner", "jacobs", "kren",
            "matsumoto", "ubuweb", "fluxus", "materialaktion",
        ],
    },
    "kavitv.independent": {
        "core": [],
        "keywords": [
            "indie", "arthouse", "art house", "auteur", "a24", "jarmusch",
            "van sant", "soderbergh", "reggio", "kelley", "simpson",
            "trockel", "drama", "comedy",
        ],
    },
}

# Scoring weights
W_THEME_CORE = 30       # genre exactly matches channel core genre
W_THEME_KEYWORD = 6     # per keyword hit (capped)
W_POSTER = 10           # has a place-card poster
W_FAST_D = 4            # D: local file (most reliable)
W_FAST_C = 2            # C: UbuWeb .strm (fast, reliable)
W_RECENT_PENALTY = -25  # picked within the rotation window
W_DIRECTOR_DUP = -12    # per extra film by an already-picked director
W_DECADE_DUP = -6       # per extra film from an already-heavy decade
MAX_KEYWORD_HITS = 5
ROTATION_DAYS = 7       # don't re-pick a movie picked within this window
MAX_PER_DIRECTOR = 2    # soft cap per channel
MAX_PER_DECADE = 3      # soft cap per channel

# ---------------------------------------------------------------------------
# Pool loading
# ---------------------------------------------------------------------------

def load_library():
    with open(LIBRARY_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_dead_ids():
    """Optional blocklist, one Emby ID per line. Missing file -> empty set."""
    if not os.path.exists(DEAD_IDS_PATH):
        return set()
    ids = set()
    with open(DEAD_IDS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                ids.add(line)
    return ids


def load_state():
    """{emby_id: 'YYYY-MM-DD' of last pick}. Missing file -> {}."""
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, sort_keys=True)


def director_of(movie):
    """Best-effort director extraction from the overview text
    (e.g. \"Toshio Matsumoto's Phantom (1975)\")."""
    overview = movie.get("overview") or ""
    m = re.match(r"^([A-Z][A-Za-z.'\- ]+?)'s\s", overview)
    if m:
        name = m.group(1).strip()
        # Guard against false positives like "A man's ..."
        if len(name.split()) <= 4 and name.lower() not in {
            "a man", "a woman", "the film", "this film",
        }:
            return name
    return movie.get("director") or "Unknown"


def movie_text(movie):
    parts = [
        movie.get("title", ""),
        " ".join(movie.get("genres", [])),
        movie.get("overview", ""),
        director_of(movie),
    ]
    return " ".join(parts).lower()


def has_poster(movie):
    """True if the movie has a local place-card poster."""
    eid = str(movie.get("emby_id", ""))
    if os.path.exists(os.path.join(POSTERS_DIR, eid + ".jpg")):
        return True
    if os.path.exists(os.path.join(POSTERS_DIR, eid + ".png")):
        return True
    # A non-empty poster URL also counts (Emby artwork / GitHub Pages card).
    return bool(movie.get("poster"))


def parse_candidates(path):
    """Tolerant parser for new-movie-candidates.md.

    Accepts markdown table rows or free-form lines that contain:
      - a 5-6 digit Emby ID
      - a title, a 4-digit year
      - optionally a drive hint (C:/D:/T:) and a channel hint
        (horror/experimental/independent)

    Returns a list of movie dicts. Never raises on malformed input.
    """
    movies = []
    if not os.path.exists(path):
        return movies
    seen = set()
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            ids = re.findall(r"\b(\d{5,6})\b", line)
            if not ids:
                continue
            eid = ids[0]
            if eid in seen:
                continue
            years = re.findall(r"\b(19\d{2}|20\d{2})\b", line)
            year = int(years[0]) if years else None
            low = line.lower()
            drive = "D" if re.search(r"\bd:|\bdrive d\b", low) else (
                "T" if re.search(r"\bt:|\bterabox\b", low) else None)
            channel_hint = None
            for ch in ("horror", "experimental", "independent"):
                if ch in low:
                    channel_hint = ch
                    break
            # Title: strip markdown table pipes, the ID, the year, and the
            # hint tokens (drive/channel/dir.) that are metadata, not title.
            title = re.sub(r"[|]", " ", line).strip()
            title = re.sub(r"\b\d{5,6}\b", "", title)
            title = re.sub(r"\b(19\d{2}|20\d{2})\b", "", title)
            title = re.sub(r"\(\)", "", title)
            title = re.sub(r"\b[CTD]:", "", title)
            title = re.sub(r"(?i)\b(horror|experimental|independent)\b", "", title)
            title = re.sub(r"(?i)\bdir\.?\s+[A-Z][A-Za-z.'\- ]+", "", title)
            title = re.sub(r"\s{2,}", " ", title).strip(" -–—:\t")
            if len(title) > 80:
                title = title[:77] + "..."
            if not title:
                title = "Untitled candidate " + eid
            # Director: look for "(dir. Name)" or "by Name" fragments.
            director = "Unknown"
            dm = re.search(r"(?:dir\.?|by)\s+([A-Z][A-Za-z.'\- ]+)", line)
            if dm:
                director = dm.group(1).strip()[:60]
            movies.append({
                "emby_id": eid,
                "title": title,
                "year": year or 0,
                "duration_s": 5400,
                "genres": [],
                "overview": title + (" — candidate from research" if year else ""),
                "poster": "",
                "director": director,
                "_drive_hint": drive,
                "_channel_hint": channel_hint,
            })
            seen.add(eid)
    return movies


def build_pool():
    """Merge library.json movies with research candidates.

    Returns (pool_by_id, notes). pool_by_id maps emby_id -> movie dict.
    Library records win on conflicts (they carry verified metadata).
    """
    lib = load_library()
    pool = {}
    notes = []
    for cid, ch in lib.get("channels", {}).items():
        for m in ch.get("movies", []):
            eid = str(m.get("emby_id", ""))
            if eid and eid not in pool:
                pool[eid] = dict(m)
    notes.append("pool from library.json: %d unique movies" % len(pool))

    candidates = parse_candidates(CANDIDATES_PATH)
    added = 0
    for c in candidates:
        eid = c["emby_id"]
        if eid not in pool:
            pool[eid] = c
            added += 1
    notes.append("candidates file %s: %d parsed, %d new" % (
        "found" if os.path.exists(CANDIDATES_PATH) else "missing",
        len(candidates), added,
    ))
    return pool, notes


# ---------------------------------------------------------------------------
# Scoring & selection
# ---------------------------------------------------------------------------

def score_movie(movie, channel_id, state, today):
    """Return (score, reasons). Higher is better."""
    theme = THEME_KEYWORDS[channel_id]
    text = movie_text(movie)
    reasons = []
    score = 0

    genres = [g.lower() for g in movie.get("genres", [])]
    if any(c in genres for c in theme["core"]):
        score += W_THEME_CORE
        reasons.append("core genre match +%d" % W_THEME_CORE)

    hits = sum(1 for kw in theme["keywords"] if kw in text)
    hits = min(hits, MAX_KEYWORD_HITS)
    if hits:
        score += hits * W_THEME_KEYWORD
        reasons.append("%d theme keyword hits +%d" % (hits, hits * W_THEME_KEYWORD))

    # Channel hint from the research file counts as a theme signal.
    hint = movie.get("_channel_hint")
    if hint and hint in channel_id:
        score += W_THEME_KEYWORD
        reasons.append("research channel hint +%d" % W_THEME_KEYWORD)

    drive = drive_of(movie["emby_id"])
    if drive == "D":
        score += W_FAST_D
        reasons.append("D: local +%d" % W_FAST_D)
    elif drive == "C":
        score += W_FAST_C
        reasons.append("C: fast +%d" % W_FAST_C)

    if has_poster(movie):
        score += W_POSTER
        reasons.append("poster +%d" % W_POSTER)

    last = state.get(str(movie["emby_id"]))
    if last:
        try:
            last_d = date.fromisoformat(last)
            if (today - last_d).days < ROTATION_DAYS:
                score += W_RECENT_PENALTY
                reasons.append("picked recently %s (%d)" % (last, W_RECENT_PENALTY))
        except ValueError:
            pass

    return score, reasons


def select_lineup(pool, requests, state, today, log_lines):
    """Assign movies to channels.

    Pass 1 (best-fit): every movie goes to the channel where its theme
    score is highest, subject to that channel's requested cap.
    Pass 2 (fill): channels still under their cap take the highest-scoring
    movies left unassigned.

    A movie is NEVER assigned to two channels and T:/unknown-drive movies
    are NEVER eligible. If the pool is too small to fill every request,
    the shortfall is logged as a warning (fix: add verified candidates to
    new-movie-candidates.md) rather than silently duplicating.
    Returns {channel_id: [(movie, score, reasons)]}.
    """
    eligible = {eid: m for eid, m in pool.items()
                if drive_of(eid) in FAST_DRIVES}
    log_lines.append("eligible pool after drive filter: %d" % len(eligible))

    # Score matrix: eid -> {cid: (score, reasons)}
    scores = {}
    for eid, m in eligible.items():
        scores[eid] = {}
        for cid in CHANNEL_ORDER:
            scores[eid][cid] = score_movie(m, cid, state, today)

    # Pass 1: best-fit assignment, strongest preference first.
    preference = []
    for eid, ch_scores in scores.items():
        ranked = sorted(ch_scores.items(), key=lambda kv: -kv[1][0])
        best_cid, (best_s, _) = ranked[0]
        second_s = ranked[1][1][0] if len(ranked) > 1 else -10 ** 9
        preference.append((best_s - second_s, best_s, eid, best_cid))
    preference.sort(key=lambda t: (-t[0], -t[1], t[2]))

    assignment = {cid: [] for cid in CHANNEL_ORDER}
    for _, _, eid, best_cid in preference:
        if len(assignment[best_cid]) < requests[best_cid]:
            assignment[best_cid].append(eid)
        else:
            log_lines.append("  unassigned (all channels at cap): %s [%s]" % (
                eligible[eid].get("title"), eid))

    # Pass 2: fill under-cap channels from whatever is left, by score.
    assigned = {eid for c in assignment.values() for eid in c}
    for cid in CHANNEL_ORDER:
        while len(assignment[cid]) < requests[cid]:
            remaining = [(scores[e][cid][0], e)
                         for e in eligible if e not in assigned]
            if not remaining:
                break
            remaining.sort(key=lambda t: (-t[0], t[1]))
            _, eid = remaining[0]
            assignment[cid].append(eid)
            assigned.add(eid)

    # Within-channel ordering: greedy by score with director/decade
    # soft-cap penalties, fully deterministic.
    lineup = {}
    for cid in CHANNEL_ORDER:
        ordered = []
        dir_count = Counter()
        decade_count = Counter()
        remaining = list(assignment[cid])
        while remaining:
            best = None
            for eid in remaining:
                s, reasons = scores[eid][cid]
                d = director_of(eligible[eid])
                decade = (eligible[eid].get("year") or 0) // 10 * 10
                penalty = 0
                extra = []
                if dir_count[d] >= MAX_PER_DIRECTOR and d != "Unknown":
                    penalty += W_DIRECTOR_DUP
                    extra.append("director cap (%s) %d" % (d, W_DIRECTOR_DUP))
                if decade and decade_count[decade] >= MAX_PER_DECADE:
                    penalty += W_DECADE_DUP
                    extra.append("decade cap (%ss) %d" % (decade, W_DECADE_DUP))
                key = (s + penalty, eid)
                if best is None or key > best[0]:
                    best = (key, eid, s + penalty, reasons + extra, d, decade)
            _, eid, final, reasons, d, decade = best
            ordered.append((eligible[eid], final, reasons))
            dir_count[d] += 1
            if decade:
                decade_count[decade] += 1
            remaining.remove(eid)
        lineup[cid] = ordered
        log_lines.append("channel %s: %d/%d filled" % (cid, len(ordered), requests[cid]))
        if len(ordered) < requests[cid]:
            log_lines.append(
                "  WARNING: pool too small for %s — add verified candidates to "
                "new-movie-candidates.md" % cid)
    return lineup


def check_repeat_limit(picked, log_lines):
    """Seth's rule: no movie more than twice per day.

    Estimate daily slots as 24h / average movie duration, then require
    pool >= ceil(daily_slots / 2). Warn if violated.
    """
    if not picked:
        return
    avg_dur = sum(m.get("duration_s", 5400) or 5400 for m, _, _ in picked) / len(picked)
    daily_slots = 86400 / avg_dur
    minimum = -(-int(daily_slots) // 2)  # ceil
    if len(picked) < minimum:
        log_lines.append(
            "  WARNING: pool of %d < %d needed for 2x/day repeat limit "
            "(~%.1f slots/day)" % (len(picked), minimum, daily_slots))
    else:
        log_lines.append(
            "  repeat check ok: %d movies cover ~%.1f slots/day "
            "(max %.2f plays/day)" % (len(picked), daily_slots, daily_slots / len(picked)))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

CHANNEL_ORDER = ["kavitv.horror", "kavitv.experimental", "kavitv.independent"]


def main():
    ap = argparse.ArgumentParser(description="KaviTV constraint-aware auto-picker")
    ap.add_argument("--horror", type=int, default=14)
    ap.add_argument("--experimental", type=int, default=12)
    ap.add_argument("--independent", type=int, default=10)
    args = ap.parse_args()

    today = date.today()
    ts = datetime.now().isoformat(timespec="seconds")
    log_lines = ["=" * 70, "auto_pick run %s" % ts]

    dead_ids = load_dead_ids()
    if dead_ids:
        log_lines.append("dead-id blocklist: %d ids" % len(dead_ids))

    pool, notes = build_pool()
    for n in notes:
        log_lines.append(n)

    # Drop dead IDs from the pool.
    for eid in list(pool):
        if eid in dead_ids:
            del pool[eid]
            log_lines.append("excluded dead id %s" % eid)

    state = load_state()
    lib = load_library()
    new_lib = {"channels": {}}
    # Preserve any other top-level keys generate.py might use.
    for k, v in lib.items():
        if k != "channels":
            new_lib[k] = v

    requests = {
        "kavitv.horror": args.horror,
        "kavitv.experimental": args.experimental,
        "kavitv.independent": args.independent,
    }

    lineup = select_lineup(pool, requests, state, today, log_lines)

    # Fail closed: generate.py cannot schedule a channel with zero movies
    # (ZeroDivisionError), so never emit such a lineup. The operator must
    # grow the pool via new-movie-candidates.md instead.
    empty = [cid for cid in CHANNEL_ORDER if not lineup[cid]]
    if empty:
        msg = ("ABORT: no movies available for %s. Refusing to write an "
               "unplayable lineup. Add verified C:/D: candidates to %s." % (
                   ", ".join(empty), CANDIDATES_PATH))
        log_lines.append(msg)
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("\n".join(log_lines) + "\n")
        print(msg)
        print("full log -> %s" % LOG_PATH)
        sys.exit(1)

    for cid in CHANNEL_ORDER:
        old_ch = lib["channels"].get(cid, {})
        picked = lineup[cid]
        check_repeat_limit(picked, log_lines)
        for m, final, reasons in picked:
            log_lines.append("  PICK %-28s [%s] score=%d (%s)" % (
                (m.get("title") or "?")[:28], m["emby_id"], final,
                "; ".join(reasons) if reasons else "no signals"))
            state[str(m["emby_id"])] = today.isoformat()

        new_ch = dict(old_ch)
        new_ch["movies"] = []
        for m, _, _ in picked:
            rec = {k: m.get(k) for k in (
                "emby_id", "title", "year", "duration_s",
                "genres", "overview", "poster")}
            rec["emby_id"] = str(rec["emby_id"])
            new_ch["movies"].append(rec)
        new_lib["channels"][cid] = new_ch

    # --- validation -------------------------------------------------------
    seen = Counter()
    for cid, ch in new_lib["channels"].items():
        for m in ch["movies"]:
            seen[str(m["emby_id"])] += 1
    dupes = [e for e, c in seen.items() if c > 1]
    assert not dupes, "duplicate emby_ids across channels: %s" % dupes
    for cid, ch in new_lib["channels"].items():
        for m in ch["movies"]:
            d = drive_of(m["emby_id"])
            assert d in FAST_DRIVES, "non-fast drive %s for %s" % (d, m["emby_id"])
    log_lines.append("validation ok: no duplicates, no T:/unknown drives")

    # --- write ------------------------------------------------------------
    if os.path.exists(LIBRARY_PATH):
        backup = LIBRARY_PATH + ".bak"
        shutil.copy2(LIBRARY_PATH, backup)
        log_lines.append("backed up %s -> %s" % (LIBRARY_PATH, backup))
    with open(LIBRARY_PATH, "w", encoding="utf-8") as f:
        json.dump(new_lib, f, indent=1)
        f.write("\n")
    log_lines.append("wrote new %s" % LIBRARY_PATH)

    save_state(state)
    log_lines.append("state saved (%d ids tracked)" % len(state))

    total = sum(len(ch["movies"]) for ch in new_lib["channels"].values())
    log_lines.append("done: %d movies picked across %d channels" % (
        total, len(new_lib["channels"])))

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")
    print("\n".join(log_lines[-8:]))
    print("full log -> %s" % LOG_PATH)


if __name__ == "__main__":
    main()
