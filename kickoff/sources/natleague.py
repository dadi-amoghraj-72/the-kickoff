"""UEFA Nations League groups and fixtures from ESPN's unofficial API."""
from datetime import timedelta

from kickoff.http import SourceError, get_json
from kickoff.sources import espn

LEAGUE = "uefa.nations"
STANDINGS = "https://site.api.espn.com/apis/v2/sports/soccer/uefa.nations/standings"
SCHEDULE = "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.nations/teams/{team}/schedule"
ROUNDS = 6  # matchdays in the league phase


def get_groups():
    """[{"name": "Group A1", "league": "A", "rows": [...]}], each row with rank, played, points, goals and ESPN's zone note."""
    data = get_json(STANDINGS)
    children = data.get("children") or []
    if not children:
        raise SourceError("no Nations League groups in response")
    groups = []
    for g in children:
        rows = []
        for e in g["standings"]["entries"]:
            s = {x["name"]: x.get("value") for x in e["stats"]}
            rows.append({"id": e["team"]["id"], "team": e["team"]["displayName"], "short": e["team"].get("shortDisplayName") or e["team"]["displayName"],
                         "abbr": e["team"].get("abbreviation", ""), "rank": int(s.get("rank") or 0), "played": int(s.get("gamesPlayed") or 0),
                         "won": int(s.get("wins") or 0), "drawn": int(s.get("ties") or 0), "lost": int(s.get("losses") or 0),
                         "gf": int(s.get("pointsFor") or 0), "ga": int(s.get("pointsAgainst") or 0),
                         "gd": int(s.get("pointDifferential") or 0), "points": int(s.get("points") or 0),
                         "note": (e.get("note") or {}).get("description")})
        groups.append({"name": g["name"], "league": g["name"].replace("Group ", "")[:1], "rows": sorted(rows, key=lambda r: r["rank"])})
    return groups


def matches_between(first_day, last_day, pause=0.1):
    """Every Nations League match ESPN lists from first_day to last_day (UTC dates, inclusive), finished or not."""
    import time
    out, day = [], first_day
    while day <= last_day:
        out += espn.get_matches_on(LEAGUE, day)
        day += timedelta(days=1)
        time.sleep(pause)
    return out


def remaining_fixtures(groups):
    """Every Nations League match still to be played by the teams in these groups, found through each team's own schedule
    (ESPN cannot list a date range, and the next matchday can be weeks away). Each match appears once.
    A team whose schedule cannot be read is simply missing: the caller checks the counts before drawing conclusions."""
    from kickoff.http import safe
    found = {}
    for g in groups:
        for row in g["rows"]:
            data = safe(f"{row['team']} schedule", get_json, SCHEDULE.format(team=row["id"]), {"fixture": "true"})
            for e in (data or {}).get("events", []):
                m = espn.parse_schedule_event(e)
                if not m["completed"] and m["league"] == LEAGUE:
                    found[m["id"]] = m
    return list(found.values())


def group_of(groups):
    """{team id: group}."""
    return {r["id"]: g for g in groups for r in g["rows"]}
