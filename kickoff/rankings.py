"""The top 30 men's national teams, used to decide which Nations League groups to show.

The spec asks for the FIFA ranking. FIFA publishes no stable open feed we can use, so by default this uses World Football
Elo (eloratings.net), a free public rating, as a clearly labelled stand-in. D can override it with the real FIFA list by
editing data/top30_manual.json before each international break; the manual file always wins."""
import json
import re
import unicodedata
from datetime import date, timedelta
from pathlib import Path

from kickoff.http import SourceError, get_bytes

ROOT = Path(__file__).resolve().parent.parent
MANUAL = ROOT / "data" / "top30_manual.json"
RATINGS = "https://www.eloratings.net/World.tsv"
NAMES = "https://www.eloratings.net/en.teams.tsv"
MAX_AGE = timedelta(days=21)
ALIASES = {"turkey": "turkiye", "czech republic": "czechia", "republic of ireland": "ireland", "usa": "united states",
           "united states of america": "united states", "korea republic": "south korea", "ir iran": "iran",
           "cote d'ivoire": "ivory coast", "bosnia-herzegovina": "bosnia and herzegovina", "north macedonia": "macedonia"}


def normalise(name):
    """'Türkiye' and 'Turkey' compare equal; case, accents and a few known spellings are ignored."""
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower().strip()
    return ALIASES.get(re.sub(r"\s+", " ", folded), re.sub(r"\s+", " ", folded))


def fetch_elo(n=30):
    """The top n team names by World Football Elo, best first."""
    names = {}
    for line in get_bytes(NAMES).decode("utf-8", "ignore").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            names[parts[0]] = parts[1]
    rows = [line.split("\t") for line in get_bytes(RATINGS).decode("utf-8", "ignore").splitlines() if line.strip()]
    ranked = sorted((r for r in rows if len(r) > 3 and r[0].isdigit()), key=lambda r: int(r[0]))[:n]
    teams = [names.get(r[2]) for r in ranked if names.get(r[2])]
    if len(teams) < n:
        raise SourceError("Elo ratings had an unexpected shape")
    return teams


def load(today, saved=None):
    """(top30 record, changed). Order of preference: D's manual FIFA list, a saved list under 21 days old, a fresh fetch.
    Returns ({'source', 'updated', 'teams'}, new_state_or_None)."""
    if MANUAL.exists():
        rec = json.loads(MANUAL.read_text())
        return {"source": rec.get("source", "FIFA ranking (manual)"), "updated": rec.get("updated", ""), "teams": rec["teams"]}, None
    if saved and saved.get("teams") and date.fromisoformat(saved["updated"]) >= today - MAX_AGE:
        return saved, None
    rec = {"source": "World Football Elo (stand-in for the FIFA ranking)", "updated": today.isoformat(), "teams": fetch_elo()}
    return rec, rec


def in_top(team_names, top30):
    if not top30:
        return False
    wanted = {normalise(t) for t in top30["teams"]}
    return any(normalise(n) in wanted for n in team_names)
