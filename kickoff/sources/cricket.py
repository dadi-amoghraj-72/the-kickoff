"""CricketData.org (the CricAPI): match lists and scorecards. Needs a free key in CRICKET_DATA_API_KEY.

The free tier allows 100 calls a day. A match list costs 1 call per 25 matches; a SCORECARD COSTS 10 CALLS. So the
daily run reads the list, then buys scorecards only for the few matches that matter most, within a budget."""
import os

from kickoff.http import SourceError, get_json

BASE = "https://api.cricapi.com/v1"
DAILY_LIMIT = 100
SCORECARD_COST = 10
RESERVE = 10  # calls kept back so a late list refresh or a retry never hits the limit


def _key():
    key = os.environ.get("CRICKET_DATA_API_KEY", "")
    if not key:
        raise SourceError("CRICKET_DATA_API_KEY is not set")
    return key


def _call(path, **params):
    """One call. Returns (data, calls used today so far). Never includes the key in an error message."""
    body = get_json(f"{BASE}/{path}", {"apikey": _key(), **params})
    if body.get("status") != "success":
        raise SourceError(f"CricketData said: {str(body.get('reason'))[:80]}")
    return body.get("data"), (body.get("info") or {}).get("hitsToday")


def get_matches(max_pages=3):
    """The recent match list (about the last four days), newest first, plus calls used today. 1 call per 25 matches."""
    out, used = [], None
    for page in range(max_pages):
        data, used = _call("currentMatches", offset=page * 25)
        out += data or []
        if not data or len(data) < 25:
            break
    return out, used


def get_scorecard(match_id):
    """(the scorecard data, calls used today). Costs 10 calls."""
    data, used = _call("match_scorecard", id=match_id)
    return data, used


def scorecards_affordable(used_today):
    """How many scorecards fit in what is left of today's calls, keeping a reserve."""
    left = DAILY_LIMIT - RESERVE - (used_today or 0)
    return max(0, left // SCORECARD_COST)
