"""Arsenal and Arsenal Women: the result in full, recent form, and the next fixtures."""
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from kickoff import notes
from kickoff import render as r
from kickoff.sources import espn

SGT = ZoneInfo("Asia/Singapore")
NOT_COMPETITIVE = re.compile(r"friendl|emirates cup|pre-?season", re.I)
ARSENAL = {"id": "359", "domestic": "eng.1", "name": "Arsenal"}
ARSENAL_WOMEN = {"id": "19973", "domestic": "eng.w.1", "name": "Arsenal Women"}


def when_sgt(kickoff_utc):
    """'Thursday 5 November, 4:00am SGT' from an ESPN UTC time like '2026-11-04T20:00Z'."""
    dt = datetime.strptime(kickoff_utc, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc).astimezone(SGT)
    clock = dt.strftime("%I:%M%p").lstrip("0").lower()
    return f"{dt:%A} {dt.day} {dt:%B}, {clock} SGT"


def result_for(game, team_id):
    mine, theirs = (game["home_score"], game["away_score"]) if game["home"]["id"] == team_id else (game["away_score"], game["home_score"])
    return "W" if mine > theirs else ("L" if mine < theirs else "D")


def form(games, team_id, upto=None):
    """Last five competitive results up to and including the game 'upto', and the current unbeaten run."""
    played = [g for g in games if g["completed"] and not NOT_COMPETITIVE.search(g["competition"])
              and (upto is None or g["kickoff"] <= upto["kickoff"])]
    results = [result_for(g, team_id) for g in played]
    run = 0
    for res in reversed(results):
        if res == "L":
            break
        run += 1
    last5 = results[-5:]
    return {"last_five_record": f"{last5.count('W')} won, {last5.count('D')} drawn, {last5.count('L')} lost",
            "unbeaten_run": run}


def next_up(upcoming, team_id, today_utc, count=2):
    """The next fixtures, with Singapore kick-off times. Built by code so a time can never be misquoted."""
    out = []
    for g in upcoming:
        if g["completed"] or datetime.strptime(g["kickoff"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc) < today_utc:
            continue
        home = g["home"]["id"] == team_id
        opp = g["away" if home else "home"]["name"]
        out.append({"opponent": opp, "venue": "home" if home else "away", "competition": g["competition"] or "",
                    "when": when_sgt(g["kickoff"])})
        if len(out) == count:
            break
    return out


def next_up_html(fixtures):
    if not fixtures:
        return ""
    parts = [f"{r.esc(x['opponent'])} ({x['venue']}), {r.esc(x['competition'])}, {x['when']}" for x in fixtures]
    return f'<p><strong>Next up:</strong> {parts[0]}.' + (f" Then {parts[1]}." if len(parts) > 1 else "") + "</p>"


def match_dict(game, details):
    return {**game, "goals": details["goals"], "reds": details["reds"]}


def build(club, edition_date, tables, previous=None, now=None, tier="arsenal"):
    """{"facts": [...], "next": [...]} for one club. facts has one entry per game in this edition's window.
    tables: {league slug: table rows}. Raises SourceError if the schedule can't be read."""
    now = now or datetime.now(timezone.utc)
    games = espn.get_team_games(club["id"], club["domestic"], today=edition_date)
    window = espn.window_start(edition_date)
    new = [g for g in games if g["completed"] and datetime.strptime(g["kickoff"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
           + espn.MATCH_LENGTH > window]
    facts = []
    for g in new:
        details = espn.get_match_details(g["id"], g["league"])
        f = notes.match_facts(match_dict(g, details), tier, tables.get(g["league"]), (previous or {}).get(g["league"]),
                              g["competition"] or "match")
        f["focus_team"] = club["name"]
        f["form"] = form(games, club["id"], upto=g)
        facts.append(f)
    try:
        upcoming = espn.get_team_games(club["id"], club["domestic"], upcoming=True, today=edition_date)
        nxt = next_up(upcoming, club["id"], now)
    except espn.SourceError:
        nxt = []
    return {"facts": facts, "next": nxt}
