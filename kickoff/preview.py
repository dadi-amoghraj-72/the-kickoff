"""The "season is coming" note (D, 2026-11-04): a week before a league's first regular-season game, one welcome-back note for someone who has not followed the
offseason: the major trades and signings (which star plays for whom now), the top draft picks, coaching changes. NFL, NBA, MLB and the EPL only; once a season.

Claude writes it, from numbered material only: ESPN's latest news (headline and summary) and ESPN's transaction log (trades, signings, hirings). Each bullet must cite
the items it rests on, and the code checks the citations: every name and number in a bullet must appear in the items it cites, and a bullet citing nothing is
dropped. Fewer than three bullets that survive means no note at all: a thin note is worse than none. Without Claude (no key, budget used up) there is no note and
nothing is invented. The first regular-season game's date comes from ESPN's season calendar; preseason never counts."""
import re
from datetime import date, datetime, timedelta

from kickoff import notes
from kickoff import render as r

LEAD_DAYS = 7
MIN_BULLETS = 3
KEEP = ("acquired", "traded", "signed", "re-signed", "drafted", "hired", "named", "agreed", "extended", "claimed")
CORE = "https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}/seasons/{season}/types/2"
SITE = "https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/"

SYSTEM = (
    "You write a short 'the season is coming' note for a sports digest. The reader has not followed the offseason. Use ONLY the numbered items you are given. "
    "Pick the most important things for a casual fan: stars who changed teams (trades and big signings), top draft picks, new head coaches, long-term injuries to stars. "
    "Write 3 to 6 bullets, each one or two short plain sentences, naming the player and the teams. Do not guess, do not add anything the items do not say, "
    "do not use hype. For each bullet list the numbers of the items it rests on. If the items do not support three solid bullets, return fewer."
)
SCHEMA = {"type": "object", "properties": {"bullets": {"type": "array", "items": {"type": "object", "properties": {
    "text": {"type": "string"}, "items": {"type": "array", "items": {"type": "integer"}}}, "required": ["text", "items"], "additionalProperties": False}}},
    "required": ["bullets"], "additionalProperties": False}


def days_to_start(start_iso, today):
    """Whole days from `today` (a date) to the first regular-season day (an ISO timestamp from ESPN); None when unreadable."""
    try:
        return (datetime.strptime(start_iso[:10], "%Y-%m-%d").date() - today).days
    except (ValueError, TypeError):
        return None


def due(start_iso, today, season, done):
    """True on the days from a week before the season to its eve, when this season's note has not been written. done: the seasons already noted."""
    d = days_to_start(start_iso, today)
    return d is not None and 0 < d <= LEAD_DAYS and season not in (done or [])


def material(news, transactions):
    """The numbered items Claude may use: [{"n", "text"}]. news: ESPN's articles (headline, description); transactions: ESPN's log rows (date, description, team)."""
    items = []
    for a in news or []:
        text = " ".join(x for x in (a.get("headline"), a.get("description")) if x).strip()
        if text:
            items.append(text)
    for t in transactions or []:
        d = (t.get("description") or "").strip()
        if d.lower().startswith(KEEP):
            items.append(f"{t.get('team', {}).get('displayName', '')}: {d} ({(t.get('date') or '')[:10]})")
    return [{"n": i + 1, "text": x} for i, x in enumerate(items)]


def supported(bullet, items):
    """A bullet stands only when it cites real items and every capitalised word (a name, a team) and every number in it is found in those items' text."""
    by_n = {x["n"]: x["text"] for x in items}
    cited = [by_n[n] for n in bullet.get("items", []) if n in by_n]
    if not cited:
        return False
    hay = " ".join(cited).lower()
    words = re.findall(r"\b[A-Z][\w'’.-]{2,}\b", re.sub(r"^\W*\w+", "", bullet["text"]))     # the first word is capitalised anyway
    numbers = re.findall(r"\d+", bullet["text"])
    return all(w.lower().strip(".'’-") in hay for w in words) and all(n in hay for n in numbers)


def write(client, league_name, season_label, items):
    """(bullets or [], usage). Never raises."""
    if not client or not items:
        return [], {"input": 0, "output": 0}
    listing = "\n".join(f"{x['n']}. {x['text']}" for x in items)
    got, usage = notes.call_json(client, SYSTEM, SCHEMA, f"League: {league_name}, {season_label} season.\n\nItems:\n{listing}")
    good = [b["text"].strip() for b in (got or {}).get("bullets", []) if supported(b, items)]
    return (good if len(good) >= MIN_BULLETS else []), usage


def html(league_name, season_label, start_iso, bullets):
    """'The 2026-27 NBA season starts on Tue 20 Oct' and the bullets."""
    d = datetime.strptime(start_iso[:10], "%Y-%m-%d")
    lis = "".join(f"<li>{r.esc(b)}</li>" for b in bullets)
    return f'<h4>The {r.esc(season_label)} {r.esc(league_name)} season starts {d:%a} {d.day} {d:%b}</h4><ul class="preview">{lis}</ul>'


def season_label(league, season):
    """2026-27 for the NBA (ESPN names it 2027) and for the Premier League (ESPN names it 2026), the year for the others."""
    return f"{season - 1}-{str(season)[2:]}" if league == "nba" else f"{season}-{str(season + 1)[2:]}" if league == "epl" else str(season)


def block(league, sport, name, season, day, done, client, source=None, league_code=None):
    """(html, seasons noted, Claude cost in dollars) for one league on one morning. Asks ESPN for the season's start only (one call) until the week before it; then
    reads the news and the transaction log and has Claude write the note, once. A season with no note written (no Claude, nothing solid to say) is tried again the
    next day of the week, so a failed call is not the end of it. Never raises."""
    done = list(done or [])
    if not client:                                           # no Claude, no note, and no calls
        return "", done, 0.0
    try:
        from kickoff.sources import espn_season
        source = source or espn_season.Source(sport, league_code or league)
        start = source.regular_season_start(season)
        if not due(start, day, season, done):
            return "", done, 0.0
        label = season_label(league, season)
        bullets, usage = write(client, name, label, material(source.news(), source.transactions()))
        cost = notes.cost(usage)
        if not bullets:
            return "", done, cost
        return html(name, label, start, bullets), done + [season], cost
    except Exception:
        return "", done, 0.0
