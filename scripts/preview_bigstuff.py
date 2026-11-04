"""Preview The Big Stuff, On Today and Games to Watch as D reviews them (13b, 2026-11-05).

  .venv/bin/python scripts/preview_bigstuff.py            writes docs/demo/bigstuff.html and opens it
  add --publish to put it at https://dadi-amoghraj-72.github.io/the-kickoff/demo/bigstuff.html, --no-open to skip opening it.

A heavy Monday morning and a quiet Wednesday morning, built by the real code (kickoff/events.py converters, bigstuff.select, ontoday) from real saved games where we have them
(the Premier League, the Champions League, the NBA, the NFL, the F1 race) and from a made-up Royal Challengers game with Virat Kohli's innings (no IPL is on in November)."""
import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import bigstuff, daily, events, fixtures, nba, nfl, ontoday, render  # noqa: E402
from kickoff.sources import espn  # noqa: E402

FX = ROOT / "tests" / "fixtures"
utc = lambda *a: datetime(*a, tzinfo=timezone.utc)  # noqa: E731
load = lambda name: json.loads((FX / name).read_text())  # noqa: E731
MON, WED = 0, 2

# ---- real finished games turned into stories ----
pl = [espn.parse_match(e, "eng.1") for e in load("espn_pl_20261031.json")["events"]]
cl = [espn.parse_match(e, "uefa.champions") for e in load("espn_cl_20261021.json")["events"]]
football = events.football([("Premier League", pl), ("Champions League", cl)], MON)
nba_games = [nba.parse_game(e) for e in load("nba_scoreboards.json")["2026-11-01"]["events"]]
nba_story = events.nba(nba_games, set(nba.FIRST), MON)
nfl_sb = load("nfl_w8_scoreboard.json")
nfl_story = events.nfl([nfl.parse_game(e) for e in nfl_sb["events"]], 2, 8, MON)
f1_story = events.f1([("Mexico City Grand Prix", "Max Verstappen", "Red Bull")])
kohli = {"innings": [{"team": "Royal Challengers Bengaluru", "batting": [{"name": "Virat Kohli", "out": "not out", "mark": "*", "r": 82, "b": 54}]}]}
match = {"id": "demo", "name": "Royal Challengers Bengaluru vs Mumbai Indians, 12th Match, Indian Premier League 2027", "teams": ["Royal Challengers Bengaluru", "Mumbai Indians"], "matchType": "t20",
         "matchEnded": True, "status": "Royal Challengers Bengaluru won by 5 wickets", "class": {"label": "IPL", "women": False}}
ipl_story, ipl_perf = events.cricket([match], {"demo": kohli}, MON)
extra = [events.perf("nba", "Shai Gilgeous-Alexander (OKC): 43 pts, 8 ast", 82), events.perf("football", "F. Ruiz (PSG): 2 goals, 1 assist", 66)]
news = [{"text": "West Ham confirm Scott Parker as head coach after sacking Nuno Espírito Santo", "link": "https://www.theguardian.com", "source": "The Guardian"}]
injuries = [{"text": "Bukayo Saka (ARS): out, hamstring injury"}]

monday = bigstuff.build(football + nba_story + nfl_story + f1_story + ipl_story + ipl_perf + extra, news, injuries, MON)
wednesday = bigstuff.build([e for e in football if e["score"] > 6] + nba_story[:3], (), (), WED)

# ---- On Today and Games to Watch from made-up-but-realistic fixtures (the real ones need the day itself) ----
base = utc(2026, 11, 8, 23, 15)
F = fixtures.fixture
today = [F("football", "PL", "Premier League: Arsenal v Brentford", utc(2026, 11, 9, 12, 30), 12, True), F("football", "CL", "Champions League: Slavia Prague v Arsenal", utc(2026, 11, 9, 20, 0), 14, True),
         F("nfl", "NFL", "NFL: Pittsburgh Steelers at Los Angeles Chargers", utc(2026, 11, 9, 17, 15), 9, True), F("nba", "NBA", "NBA: Los Angeles Lakers at Detroit Pistons", utc(2026, 11, 9, 0, 0), 6, True),
         F("f1", "F1", "F1: Brazilian Grand Prix · Race", utc(2026, 11, 9, 17, 0), 18, False, "final")]
watch = [F("football", "PL", "Premier League: Arsenal v Tottenham Hotspur", utc(2026, 11, 14, 12, 30), 12, True, "regular", {"derby", "clash"}),
         F("cricket", "IPL", "Cricket: Royal Challengers Bengaluru v Sunrisers Hyderabad (IPL)", utc(2026, 11, 15, 14, 0), 8, True), F("nba", "NBA", "NBA: Boston Celtics v Cleveland Cavaliers", utc(2026, 11, 12, 0, 30), 4.2, False, "regular", {"stars"}),
         F("f1", "F1", "F1: Las Vegas Grand Prix · Race", utc(2026, 11, 15, 6, 0), 18, False, "final"), F("tennis", "ATP Finals", "Tennis: ATP Finals final", utc(2026, 11, 15, 13, 0), 10, False, "final")]
today_html = ontoday.today_html(today)
banner = ("REVIEW of 13b on real saved games (a made-up Royal Challengers game stands in for Virat Kohli, there is no IPL in November). First a heavy Monday morning, then a quiet Wednesday morning "
          "to show the lines drop. On Today and Games to Watch below use made-up fixtures with real names.")
edition = {"date": date(2026, 11, 9).isoformat(), "dummy": False, "banner": banner, "home": "../index.html", "headlines": monday["headlines"],
           "sections": [{"id": "big-stuff", "title": "The Big Stuff · a heavy Monday", "html": monday["html"]},
                        {"id": "on-today", "title": "On Today", "html": today_html + ontoday.watch_html(watch)},
                        {"id": "quiet", "title": "The Big Stuff · a quiet Wednesday", "html": wednesday["html"]}]}
out = ROOT / "docs" / "demo" / "bigstuff.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(render.render_edition(edition))
print("Built", out.relative_to(ROOT))
print("Monday lines:", len(monday["selected"]), "| Wednesday lines:", len(wednesday["selected"]), "| lead:", monday["lead"], "| promoted:", monday["promoted"])
for s in monday["selected"]:
    print("  ", s["why"], "|", s["text"])
if "--no-open" not in sys.argv and sys.platform == "darwin":
    subprocess.run(["open", str(out)])
if "--publish" in sys.argv:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    git("add", "docs/demo/bigstuff.html")
    done = git("commit", "-m", "Add Big Stuff and On Today review page")
    if done.returncode != 0:
        print("Nothing new to publish." if "nothing to commit" in (done.stdout + done.stderr) else "Could not commit: " + (done.stderr or done.stdout)[:300])
    else:
        git("pull", "--rebase")
        print("Published: https://dadi-amoghraj-72.github.io/the-kickoff/demo/bigstuff.html" if git("push", "origin", "main").returncode == 0 else "Push failed.")
