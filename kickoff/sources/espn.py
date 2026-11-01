"""ESPN's unofficial public API: football scores and tables. No key needed. Can change without notice."""
from datetime import datetime, timedelta, timezone

from kickoff.http import SourceError, get_json

SCORES = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"
TABLES = "https://site.api.espn.com/apis/v2/sports/soccer/{league}/standings"

LEAGUES = {
    "eng.1": "Premier League", "esp.1": "La Liga", "fra.1": "Ligue 1",
    "ita.1": "Serie A", "ger.1": "Bundesliga", "tur.1": "Süper Lig",
}
WSL = "eng.w.1"
CHAMPIONS_LEAGUE = "uefa.champions"
MATCH_LENGTH = timedelta(minutes=105)  # kick-off to full time, roughly


def _utc(text):
    return datetime.strptime(text, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)


def parse_match(event, league):
    comp = event["competitions"][0]
    teams = {c["homeAway"]: c for c in comp["competitors"]}
    side_of = {teams[s]["team"]["id"]: s for s in teams}

    def team(s):
        t = teams[s]["team"]
        return {"id": t["id"], "name": t["displayName"], "abbr": t.get("abbreviation", t["displayName"][:3].upper())}

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
    return {
        "id": event["id"], "league": league, "kickoff": event["date"],
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


def recent_results(league, edition_date):
    """Finished matches that belong in the edition for edition_date (a date in Singapore time).
    That means everything that finished since the previous edition's run (7:15am SGT the day before)."""
    prev_run = datetime.combine(edition_date - timedelta(days=2), datetime.min.time(), tzinfo=timezone.utc) \
        + timedelta(hours=23, minutes=15)
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
            "rank": int(s.get("rank") or 0), "team": e["team"]["displayName"],
            "abbr": e["team"].get("abbreviation", ""), "played": int(s.get("gamesPlayed") or 0),
            "won": int(s.get("wins") or 0), "drawn": int(s.get("ties") or 0), "lost": int(s.get("losses") or 0),
            "gf": int(s.get("pointsFor") or 0), "ga": int(s.get("pointsAgainst") or 0),
            "gd": int(s.get("pointDifferential") or 0), "points": int(s.get("points") or 0),
            "zone": (e.get("note") or {}).get("description"),
        })
    return sorted(rows, key=lambda r: r["rank"])
