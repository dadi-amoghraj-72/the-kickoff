"""Who is young: an athlete's age, birth date and years of experience from ESPN's free core API (the same host as the other sports' data). One request per athlete,
kept in the state afterwards, so a player is looked up once and never again. Undocumented; any failure is simply 'unknown' and the player is not listed."""
from kickoff import http

CORE = "https://sports.core.api.espn.com/v2/sports/{path}/athletes/{id}"
PATHS = {"nba": "basketball/leagues/nba", "nfl": "football/leagues/nfl", "mlb": "baseball/leagues/mlb", "soccer": "soccer", "tennis": "tennis"}


def athlete(sport, athlete_id, get_json=http.get_json):
    """{"dob": 'YYYY-MM-DD' or None, "age": int or None, "years": experience years or None}, or None when the lookup fails."""
    try:
        a = get_json(CORE.format(path=PATHS[sport], id=athlete_id))
    except Exception:
        return None
    return {"dob": (a.get("dateOfBirth") or "")[:10] or None, "age": a.get("age"), "years": (a.get("experience") or {}).get("years")}
