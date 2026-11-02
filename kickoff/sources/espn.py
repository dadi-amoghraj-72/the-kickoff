"""ESPN's unofficial public API: football scores and tables. No key needed. Can change without notice."""
import time
from datetime import datetime, timedelta, timezone

from kickoff.http import SourceError, get_json

SCORES = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"
TABLES = "https://site.api.espn.com/apis/v2/sports/soccer/{league}/standings"
CORE = "https://sports.core.api.espn.com/v2/sports/soccer/leagues/{league}/seasons/{year}"
SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/summary"
SCHEDULE = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/teams/{team}/schedule"

LEAGUES = {
    "eng.1": "Premier League", "esp.1": "La Liga", "fra.1": "Ligue 1",
    "ita.1": "Serie A", "ger.1": "Bundesliga", "tur.1": "Süper Lig",
}
WSL = "eng.w.1"
CHAMPIONS_LEAGUE = "uefa.champions"
MATCH_LENGTH = timedelta(minutes=105)  # kick-off to full time, roughly


def _utc(text):
    return datetime.strptime(text, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)


def parse_time(kickoff):
    """A match's kick-off text like '2026-11-12T19:45Z' as a UTC datetime."""
    return _utc(kickoff)


def parse_match(event, league):
    comp = event["competitions"][0]
    teams = {c["homeAway"]: c for c in comp["competitors"]}
    side_of = {teams[s]["team"]["id"]: s for s in teams}

    def team(s):
        t = teams[s]["team"]
        return {"id": t["id"], "name": t["displayName"], "abbr": t.get("abbreviation", t["displayName"][:3].upper()),
                "short": t.get("shortDisplayName") or t["displayName"]}

    goals, reds = [], []
    for d in comp.get("details", []):
        who = (d.get("athletesInvolved") or [{}])[0].get("displayName", "Unknown")
        side = side_of.get((d.get("team") or {}).get("id"))
        if d.get("scoringPlay"):
            goals.append({"minute": d["clock"]["displayValue"], "player": who, "side": side,
                          "penalty": bool(d.get("penaltyKick")), "own_goal": bool(d.get("ownGoal"))})
        elif d.get("redCard"):
            reds.append({"minute": d["clock"]["displayValue"], "player": who, "side": side})
    status = event["status"]["type"]
    recap = next((h for h in (comp.get("headlines") or []) if h and h.get("type") == "Recap"), None)
    return {
        "id": event["id"], "league": league, "kickoff": event["date"], "stage": (event.get("season") or {}).get("slug", ""),
        "recap": {"headline": recap.get("shortLinkText", ""), "summary": recap.get("description", "")} if recap else None,
        "home": team("home"), "away": team("away"),
        "home_score": int(teams["home"].get("score") or 0), "away_score": int(teams["away"].get("score") or 0),
        "completed": bool(status.get("completed")), "status": status.get("description", ""),
        "goals": goals, "reds": reds,
    }


def get_matches_on(league, utc_date):
    """All matches ESPN lists for one UTC calendar day. (A date range makes ESPN return an error.)"""
    data = get_json(SCORES.format(league=league), {"dates": utc_date.strftime("%Y%m%d")})
    if "events" not in data:
        raise SourceError("no events field in response")
    return [parse_match(e, league) for e in data["events"]]


def window_start(edition_date):
    """When the previous edition's run happened: 7:15am Singapore time the day before = 23:15 UTC two days before."""
    return datetime.combine(edition_date - timedelta(days=2), datetime.min.time(), tzinfo=timezone.utc) \
        + timedelta(hours=23, minutes=15)


def recent_results(league, edition_date):
    """Finished matches that belong in the edition for edition_date (a date in Singapore time).
    That means everything that finished since the previous edition's run (7:15am SGT the day before)."""
    prev_run = window_start(edition_date)
    found = []
    for back in (2, 1):
        found += get_matches_on(league, edition_date - timedelta(days=back))
    out = [m for m in found if m["completed"] and _utc(m["kickoff"]) + MATCH_LENGTH > prev_run]
    return sorted(out, key=lambda m: m["kickoff"])


def get_table(league):
    """The league table as a list of rows, best first. Each row includes ESPN's zone note, if any."""
    data = get_json(TABLES.format(league=league))
    groups = data.get("children") or []
    if not groups:
        raise SourceError("no table in response")
    rows = []
    for e in groups[0]["standings"]["entries"]:
        s = {x["name"]: x.get("value") for x in e["stats"]}
        rows.append({
            "rank": int(s.get("rank") or 0), "id": e["team"]["id"], "team": e["team"]["displayName"],
            "abbr": e["team"].get("abbreviation", ""), "short": e["team"].get("shortDisplayName") or e["team"]["displayName"], "played": int(s.get("gamesPlayed") or 0),
            "won": int(s.get("wins") or 0), "drawn": int(s.get("ties") or 0), "lost": int(s.get("losses") or 0),
            "gf": int(s.get("pointsFor") or 0), "ga": int(s.get("pointsAgainst") or 0),
            "gd": int(s.get("pointDifferential") or 0), "points": int(s.get("points") or 0),
            "zone": (e.get("note") or {}).get("description"),
        })
    return sorted(rows, key=lambda r: r["rank"])


# ---- Season leaders and goalkeepers ---------------------------------------------------------

def season_year(day):
    """ESPN names a European season by the year it starts: 2026-27 is 2026."""
    return day.year if day.month >= 7 else day.year - 1


def _id_from_ref(ref):
    return ref.split("?")[0].rstrip("/").split("/")[-1]


def get_leaders(league, year, max_tied=10):
    """The season's top scorer(s) and top assist-maker(s). Ties at the top are all returned (up to max_tied).
    Each entry: {"athlete_id", "team_id", "value"}."""
    data = get_json(CORE.format(league=league, year=year) + "/types/1/leaders")
    cats = {c["name"]: c for c in data.get("categories", [])}
    out = {}
    for key, cat in (("goals", "goalsLeaders"), ("assists", "assistsLeaders")):
        leaders = sorted(cats.get(cat, {}).get("leaders", []), key=lambda x: -x["value"])
        if not leaders:
            raise SourceError(f"no {key} leaders in response")
        out[key] = [{"athlete_id": _id_from_ref(x["athlete"]["$ref"]), "team_id": _id_from_ref(x["team"]["$ref"]),
                     "value": int(x["value"])} for x in leaders if x["value"] == leaders[0]["value"]][:max_tied]
    return out


def get_athlete_name(league, year, athlete_id):
    data = get_json(CORE.format(league=league, year=year) + f"/athletes/{athlete_id}")
    return data.get("displayName") or data.get("fullName") or "Unknown"


def get_starting_keepers(league, event_id):
    """{team_id: (athlete_id, name)} for the goalkeepers who started a match."""
    data = get_json(SUMMARY.format(league=league), {"event": event_id})
    out = {}
    for side in data.get("rosters", []):
        for p in side.get("roster", []):
            if p.get("starter") and (p.get("position") or {}).get("abbreviation") == "G":
                out[side["team"]["id"]] = (p["athlete"]["id"], p["athlete"]["displayName"])
    return out


def results_between(league, start, end, pause=0.1):
    """Every finished match from start to end (UTC dates, inclusive), one day at a time."""
    out, day = [], start
    while day <= end:
        out += [m for m in get_matches_on(league, day) if m["completed"]]
        day += timedelta(days=1)
        time.sleep(pause)
    return out


# ---- One team's games, in every competition ---------------------------------------------------

def _score(c):
    sc = c.get("score")
    if isinstance(sc, dict):
        sc = sc.get("value", sc.get("displayValue"))
    try:
        return int(float(sc))
    except (TypeError, ValueError):
        return 0


def parse_schedule_event(e):
    comp = e["competitions"][0]
    teams = {c["homeAway"]: c for c in comp["competitors"]}
    team = lambda s: {"id": teams[s]["team"]["id"], "name": teams[s]["team"]["displayName"],  # noqa: E731
                      "abbr": teams[s]["team"].get("abbreviation", "")}
    lg = e.get("league") or {}
    return {"id": e["id"], "kickoff": e["date"], "league": lg.get("slug") or "all", "competition": lg.get("name") or "",
            "home": team("home"), "away": team("away"), "home_score": _score(teams["home"]), "away_score": _score(teams["away"]),
            "completed": comp["status"]["type"]["state"] == "post"}


def get_team_games(team_id, domestic_league, upcoming=False, today=None):
    """One team's games across every competition, oldest first. ESPN's all-competitions list can miss recent
    league games, so the domestic league's own list is merged in. upcoming=True gives fixtures still to play."""
    year = season_year(today or datetime.now(timezone.utc).date())
    if upcoming:
        requests = [("all", {"fixture": "true"})]
    else:
        requests = [("all", {}), (domestic_league, {"season": year})]
    games, failures = {}, 0
    for league, params in requests:
        try:
            data = get_json(SCHEDULE.format(league=league, team=team_id), params)
        except SourceError:
            failures += 1
            continue
        for e in data.get("events", []):
            g = parse_schedule_event(e)
            games[g["id"]] = g
    if failures == len(requests):
        raise SourceError("team schedule unavailable")
    return sorted(games.values(), key=lambda g: g["kickoff"])


def _leg_score(c):
    """(goals, penalty shoot-out goals or None, aggregate or None) from one competitor of a team-schedule event, where the score is a dict."""
    sc = c.get("score")
    if isinstance(sc, dict):
        return _score({"score": sc.get("displayValue")}), sc.get("shootoutScore"), sc.get("aggregateScore")
    return _score(c), None, None


def get_tie_legs(match, league=CHAMPIONS_LEAGUE):
    """Every leg of the knockout tie a match belongs to, oldest first, from one team's schedule: the played legs with their scores (and a
    shoot-out when there was one) and any leg still to come. A final is a tie of one match. Each leg: {"id", "kickoff", "home", "away"
    (id, name, abbr), "home_score", "away_score", "completed", "status" (ESPN's name, e.g. STATUS_FULL_TIME, STATUS_FINAL_AET, STATUS_FINAL_PEN),
    "pens": (home, away) or None, "agg": {team id: ESPN's aggregate} or None, "note": ESPN's note}."""
    team, opp = match["home"]["id"], match["away"]["id"]
    kick = parse_time(match["kickoff"])
    year = kick.year if kick.month >= 7 else kick.year - 1
    data = get_json(SCHEDULE.format(league=league, team=team), {"season": year})
    legs = []
    for e in data.get("events", []):
        comp = e["competitions"][0]
        sides = {c["homeAway"]: c for c in comp["competitors"]}
        ids = {sides["home"]["team"]["id"], sides["away"]["team"]["id"]}
        when = parse_time(e["date"])
        note = next((n.get("headline") or n.get("text") or "" for n in comp.get("notes", [])), "")
        if ids != {team, opp} or abs((when - kick).days) > 75 or not ("Leg" in note or when.date() == kick.date() or "penalties" in note.lower() or "extra time" in note.lower()):
            continue
        hs, hp, ha = _leg_score(sides["home"])
        as_, ap, aa = _leg_score(sides["away"])
        team_of = lambda s: {"id": sides[s]["team"]["id"], "name": sides[s]["team"]["displayName"], "abbr": sides[s]["team"].get("abbreviation", "")}  # noqa: E731
        legs.append({"id": e["id"], "kickoff": e["date"], "home": team_of("home"), "away": team_of("away"), "home_score": hs, "away_score": as_,
                     "completed": comp["status"]["type"]["state"] == "post", "status": comp["status"]["type"]["name"],
                     "pens": (int(hp), int(ap)) if hp is not None and ap is not None else None,
                     "agg": {sides["home"]["team"]["id"]: ha, sides["away"]["team"]["id"]: aa} if ha is not None else None, "note": note})
    return sorted(legs, key=lambda g: g["kickoff"])


def get_match_details(event_id, league="all"):
    """Goals (with assists) and red cards from a match summary. Works for any competition."""
    data = get_json(SUMMARY.format(league=league), {"event": event_id})
    comp = data["header"]["competitions"][0]
    side_of = {c["id"]: c["homeAway"] for c in comp["competitors"]}
    goals, reds = [], []
    for d in comp.get("details", []):
        people = [p["athlete"]["displayName"] for p in d.get("participants", []) if p.get("athlete")]
        minute = d["clock"]["displayValue"] + ((d.get("addedClock") or {}).get("displayValue") or "")
        side = side_of.get((d.get("team") or {}).get("id"))
        if d.get("scoringPlay"):
            goals.append({"minute": minute, "player": people[0] if people else "Unknown", "side": side,
                          "penalty": bool(d.get("penaltyKick")), "own_goal": bool(d.get("ownGoal")),
                          "assist": people[1] if len(people) > 1 and not d.get("ownGoal") else None})
        elif d.get("redCard"):
            reds.append({"minute": minute, "player": people[0] if people else "Unknown", "side": side})
    return {"goals": goals, "reds": reds}


def get_odds(event_id, league="all"):
    """The pre-match betting lines (a list of records) for one match, from its summary. May be empty."""
    data = get_json(SUMMARY.format(league=league), {"event": event_id})
    return data.get("pickcenter") or data.get("odds") or []
