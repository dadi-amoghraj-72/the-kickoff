"""The Premier League's own Fantasy data: official player status, injury news and minutes. No key needed."""
from kickoff.http import SourceError, get_json

BOOTSTRAP = "https://fantasy.premierleague.com/api/bootstrap-static/"
FIXTURES = "https://fantasy.premierleague.com/api/fixtures/"
ENTRY = "https://fantasy.premierleague.com/api/entry/{id}/"
PICKS = "https://fantasy.premierleague.com/api/entry/{id}/event/{gw}/picks/"
HISTORY = "https://fantasy.premierleague.com/api/entry/{id}/history/"
LIVE = "https://fantasy.premierleague.com/api/event/{gw}/live/"
DRAFT = "https://draft.premierleague.com/api/league/{id}/details"
STATUS = {"a": "available", "i": "injured", "d": "doubtful", "s": "suspended", "u": "unavailable", "n": "not in squad"}


def get_bootstrap():
    data = get_json(BOOTSTRAP)
    if "elements" not in data or "teams" not in data:
        raise SourceError("FPL data has an unexpected shape")
    return data


def get_fixtures():
    data = get_json(FIXTURES)
    if not isinstance(data, list):
        raise SourceError("FPL fixtures have an unexpected shape")
    return data


def games_played(fixtures):
    """{team id: finished games}. The teams list has a 'played' field, but it is always 0, so count fixtures."""
    played = {}
    for f in fixtures:
        if f.get("finished"):
            for side in ("team_h", "team_a"):
                played[f[side]] = played.get(f[side], 0) + 1
    return played


def players(data, fixtures=None):
    """Every player as a plain dict, with his team's short code, name and games played so far attached."""
    teams = {t["id"]: t for t in data["teams"]}
    played = games_played(fixtures or [])
    out = []
    for e in data["elements"]:
        t = teams[e["team"]]
        out.append({"id": e["id"], "name": f"{e['first_name']} {e['second_name']}".strip(), "web_name": e["web_name"],
                    "team": t["short_name"], "team_name": t["name"], "team_position": t.get("position"),
                    "team_played": played.get(e["team"], t.get("played") or 0), "status": e["status"], "news": e.get("news") or "",
                    "news_added": e.get("news_added"), "chance_next": e.get("chance_of_playing_next_round"),
                    "minutes": e.get("minutes") or 0, "starts": e.get("starts") or 0,
                    "owned": float(e.get("selected_by_percent") or 0)})
    return out


def get_entry(entry_id):
    return get_json(ENTRY.format(id=entry_id))


def get_picks(entry_id, gw):
    return get_json(PICKS.format(id=entry_id, gw=gw))


def get_history(entry_id):
    return get_json(HISTORY.format(id=entry_id))


def get_live(gw):
    """{player id: points this gameweek}."""
    return {e["id"]: e["stats"]["total_points"] for e in get_json(LIVE.format(gw=gw)).get("elements", [])}


def get_draft_league(league_id):
    data = get_json(DRAFT.format(id=league_id))
    if "standings" not in data or "league_entries" not in data:
        raise SourceError("FPL Draft data has an unexpected shape")
    return data
