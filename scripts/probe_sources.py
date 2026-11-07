"""Every outside source the daily run reads, tried once each from wherever this runs (D, 2026-11-08: prove it from GitHub's servers, not from the Mac).
No keys, nothing saved, nothing sent. Prints one line per source: OK, or what came back instead.

  .venv/bin/python scripts/probe_sources.py           on the Mac
  .github/workflows/probe.yml                          the same on GitHub (D starts it: gh workflow run probe.yml)"""
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff.http import USER_AGENT  # noqa: E402

E = "https://site.api.espn.com/apis"
# (what it feeds, url, a word that must be in a good answer)
SOURCES = [
    ("Cricket: ESPN header feed (the matches)", "https://site.web.api.espn.com/apis/v2/scoreboard/header?sport=cricket&lang=en&region=us", '"leagues"'),
    ("Cricket: ESPN summary feed (scorecards, POTM, tables) - the new main source", E + "/site/v2/sports/cricket/{series}/summary?event={event}", '"rosters"'),
    ("Cricket: ESPN scores web page (old source, expected blocked on GitHub)", "https://www.espn.com/cricket/scores", "cscore"),
    ("Cricket: ESPN scorecard web page (old source, expected blocked on GitHub)", "https://www.espn.com/cricket/series/{series}/scorecard/{event}", "batsmen"),
    ("Football: ESPN Premier League scoreboard", E + "/site/v2/sports/soccer/eng.1/scoreboard", '"events"'),
    ("Football: ESPN standings", E + "/v2/sports/soccer/eng.1/standings", '"standings"'),
    ("Football: ESPN core (leaders, athletes)", "https://sports.core.api.espn.com/v2/sports/soccer/leagues/eng.1/seasons/2026", '"year"'),
    ("Football: ESPN news", E + "/site/v2/sports/soccer/eng.1/news", '"articles"'),
    ("FPL: Fantasy Premier League", "https://fantasy.premierleague.com/api/bootstrap-static/", '"elements"'),
    ("NBA: ESPN scoreboard", E + "/site/v2/sports/basketball/nba/scoreboard", '"events"'),
    ("NFL: ESPN scoreboard", E + "/site/v2/sports/football/nfl/scoreboard", '"events"'),
    ("MLB: ESPN scoreboard", E + "/site/v2/sports/baseball/mlb/scoreboard", '"events"'),
    ("Tennis: ESPN ATP scoreboard", E + "/site/v2/sports/tennis/atp/scoreboard", '"events"'),
    ("F1: Jolpica", "https://api.jolpi.ca/ergast/f1/current/last/results.json", '"MRData"'),
    ("Golf: ESPN PGA scoreboard", E + "/site/v2/sports/golf/pga/scoreboard", '"events"'),
    ("Rugby: ESPN scoreboard", E + "/site/v2/sports/rugby/180659/scoreboard", '"events"'),
    ("UFC: events page", "https://www.ufc.com/events", "c-card-event"),
    ("UFC: rankings page", "https://www.ufc.com/rankings", "view-grouping"),
    ("Chess: Lichess broadcasts", "https://lichess.org/api/broadcast/top", '"active"'),
    ("Wikipedia API", "https://en.wikipedia.org/w/api.php?action=query&titles=Arsenal_F.C.&format=json", '"pages"'),
    ("Elo ratings", "https://www.eloratings.net/World.tsv", "\t"),
    ("News: BBC Sport", "https://feeds.bbci.co.uk/sport/football/rss.xml", "<rss"),
    ("News: Guardian", "https://www.theguardian.com/football/rss", "<rss"),
    ("News: Google News", "https://news.google.com/rss/search?q=cricket&hl=en-SG&gl=SG&ceid=SG:en", "<rss"),
    ("News: Times of India cricket", "https://timesofindia.indiatimes.com/rssfeeds/4719148.cms", "<rss"),
    ("News: The Hindu sport", "https://www.thehindu.com/sport/feeder/default.rss", "<rss"),
    ("News: Straits Times sport", "https://www.straitstimes.com/news/sport/rss.xml", "<rss"),
    ("News: Yahoo Sports", "https://sports.yahoo.com/rss/", "<rss"),
    ("News: Chess.com", "https://www.chess.com/rss/news", "<rss"),
    ("News: ChessBase", "https://en.chessbase.com/feed", "<rss"),
]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.status, r.read().decode("utf-8", "replace")


def live_test():
    """A cricket match on now (series, event) from the header feed, to fill in the scorecard addresses."""
    try:
        d = json.loads(get(SOURCES[0][1])[1])
        for lg in d["sports"][0]["leagues"]:
            for ev in lg.get("events") or []:
                if ev.get("status") in ("in", "post"):
                    return lg["id"], ev["id"], ev.get("name")
    except Exception:
        pass
    return None


match = live_test()
print(f"Sample cricket match: {match[2] if match else 'none found'}\n")
bad = 0
for label, url, must in SOURCES:
    if "{series}" in url:
        if not match:
            print(f"SKIP  {label}: no current cricket match to try")
            continue
        url = url.format(series=match[0], event=match[1])
    try:
        status, body = get(url)
        ok = status == 200 and must in body
        print(f"{'OK  ' if ok else 'BAD '}  {label}: HTTP {status}, {len(body) // 1024} KB" + ("" if ok else f", '{must}' not in the answer"))
    except Exception as e:
        ok = False
        print(f"BAD   {label}: {type(e).__name__} {str(e)[:80]}")
    bad += not ok and "expected blocked" not in label
print(f"\n{bad} source(s) failing that the run needs" if bad else "\nEvery source the run needs answered.")
