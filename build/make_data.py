#!/usr/bin/env python3
"""Turn a raw dashboard database dump into the coaches' page data file.

The dashboard holds things the coaching staff must not be handed: player and
family email addresses, phone numbers, parent names and the full outreach log.
So this script works by WHITELIST. A field reaches the coaches' page only if it
is named below. Anything new added to the dashboard later is excluded by
default, which is the safe direction to fail in.

The only free text that crosses over is coach_summary, which is written
deliberately for other people to read. scouting_notes never crosses: that is
where the phone numbers and parent names live.

Usage: python3 -I make_data.py raw_players.json raw_games.json data.json

Each raw file is a JSON list of {"id": ..., "data": {...}} as returned by the
artifact db_query tool.
"""
import json, re, sys

# Scouting assessment fields, by position. Shown on the coaches' page as the
# evaluation grid. "Not yet assessed" is treated as empty.
SKATER_FIELDS = ["skating", "shooting_release", "hockey_iq", "compete_level", "off_ice_character"]
GOALIE_FIELDS = ["skating", "lateral_movement", "recovery", "tracking",
                 "puck_handling", "rebound_control", "off_ice_character"]

GAME_KEYS = ["team", "date", "time", "home_away", "opponent", "location", "own_team", "kind"]

PHONE = re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]\d{4}\b")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def blank(v):
    return v is None or not str(v).strip() or str(v).strip().lower() == "not yet assessed"


def is_goalie(p):
    return any("goal" in str(x).lower() for x in (p.get("positions") or []))


def fallback_summary(p):
    """A mechanical line for a player with no coach_summary written yet.

    Built only from structured fields, so it cannot leak free text.
    """
    bits = []
    if p.get("current_team"):
        bits.append(str(p["current_team"]))
    if p.get("birth_year"):
        bits.append(str(p["birth_year"]))
    pos = ", ".join(p.get("positions") or [])
    if pos:
        bits.append(pos.lower())
    if p.get("shoots"):
        bits.append("shoots " + str(p["shoots"]))
    line = ". ".join(bits)
    return (line + ". No summary written yet.") if line else "No summary written yet."


def player_out(doc):
    p = doc.get("data", doc)
    keys = GOALIE_FIELDS if is_goalie(p) else SKATER_FIELDS
    fields = {k: str(p[k]).strip() for k in keys if not blank(p.get(k))}

    vids = []
    for v in (p.get("video_links") or []):
        if v.get("url"):
            vids.append({"url": v["url"], "label": v.get("label") or "", "note": v.get("note") or ""})

    reports = []
    for r in (p.get("coach_reports") or []):
        pts = [s for s in (r.get("points") or []) if str(s).strip()]
        if pts:
            reports.append({"at": r.get("at") or "", "by": r.get("by") or "Coach",
                            "source": r.get("source") or "", "points": pts})

    return {
        "name": p.get("name") or "",
        "jersey_number": p.get("jersey_number"),
        "current_team": p.get("current_team") or "",
        "positions": p.get("positions") or [],
        "shoots": p.get("shoots"),
        "birth_year": p.get("birth_year"),
        "pros": [s for s in (p.get("pros") or []) if str(s).strip()],
        "cons": [s for s in (p.get("cons") or []) if str(s).strip()],
        "background": p["coach_summary"].strip() if not blank(p.get("coach_summary")) else fallback_summary(p),
        "fields": fields,
        "video_links": vids,
        "coach_reports": reports,
        "instagram": p.get("instagram"),
    }


def game_out(doc):
    g = doc.get("data", doc)
    return {k: g[k] for k in GAME_KEYS if g.get(k) is not None}


def main():
    if len(sys.argv) < 4:
        sys.exit("usage: make_data.py raw_players.json raw_games.json data.json")

    players = [player_out(d) for d in json.load(open(sys.argv[1], encoding="utf-8"))]
    games = [game_out(d) for d in json.load(open(sys.argv[2], encoding="utf-8"))]

    players = [p for p in players if p["name"]]
    players.sort(key=lambda p: p["name"])
    games.sort(key=lambda g: (g.get("date") or "", g.get("time") or ""))

    out = {"players": players, "games": games}
    blob = json.dumps(out, ensure_ascii=False)

    # Loud failure beats a silent leak. build.py repeats this check over the
    # whole rendered page, so a leak has to clear both.
    leaks = []
    if PHONE.search(blob):
        leaks.append("phone number: " + PHONE.search(blob).group(0))
    if EMAIL.search(blob):
        leaks.append("email address: " + EMAIL.search(blob).group(0))
    if leaks:
        sys.exit("ABORT: contact details reached the coaches' data (" + "; ".join(leaks) + ")")

    with open(sys.argv[3], "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    written = sum(1 for p in players if not p["background"].endswith("No summary written yet."))
    print("players   : %d (%d with a written summary)" % (len(players), written))
    print("games     : %d" % len(games))


if __name__ == "__main__":
    main()
