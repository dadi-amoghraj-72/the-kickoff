"""The most packed morning: every section on one page, to see how a full edition reads on a phone (D's request, 2026-11-05).

  .venv/bin/python scripts/preview_packed.py            writes docs/demo/packed-weekend.html (builds each saved-day page first) and opens it
  add --publish to put it at https://dadi-amoghraj-72.github.io/the-kickoff/demo/packed-weekend.html, --no-open to skip opening it.

Each section is the real code's output for a real saved day of its sport, so the layout is the real layout, but the days differ (it is a collage, not one real morning):
  The Big Stuff, On Today, In The Week Ahead   the heavy Monday of scripts/preview_bigstuff.py
  Arsenal, Football                          the Champions League night of 21 October 2026 (live ESPN history)
  Cricket                                    the saved NZ v India series and the other matches of scripts/preview_cricket.py
  NBA                                        the weekend of 31 October and 1 November
  NFL                                        week 8 as the Wednesday wrap (every game, the division tables)
  MLB                                        the division series' first games (4 October)
  F1, Tennis                                 the Mexico City Grand Prix, the US Open and the Tour Finals
  Young Guns                                 plain lines
  Other Sports                               rugby, golf, UFC 309 with the rankings, badminton, darts, chess (scripts/preview_sports_demo.py)
No Claude, no key, no cost."""
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from datetime import datetime, timedelta, timezone  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

from kickoff import fixtures, importance, ontoday, render  # noqa: E402

DEMO = ROOT / "docs" / "demo"
BUILD = [["preview_bigstuff.py"], ["build_demo.py", "2026-10-22", "--no-cricket", "--no-nfl", "--no-nba", "--no-mlb", "--no-f1", "--no-tennis"], ["preview_cricket.py"], ["preview_nba.py"],
         ["preview_nfl.py", "--day", "wed"], ["preview_mlb.py", "--start"], ["preview_f1_tennis.py"], ["preview_youngguns.py"], ["preview_sports_demo.py"]]
# (page, section id, title shown)
PICK = [("bigstuff", "big-stuff", "The Big Stuff"), ("bigstuff", "on-today", "On Today"), ("index", "arsenal", "Arsenal"), ("index", "football", "Football"), ("cricket", "cricket", "Cricket"),
        ("nba", "nba", "NBA"), ("nfl-wed", "nfl", "NFL"), ("mlb-start", "mlb", "MLB"), ("f1-tennis", "f1", "F1"), ("f1-tennis", "tennis", "Tennis"),
        ("youngguns", "young-guns", "Young Guns"), ("sports-demo", "other-sports", "Other Sports")]


SGT = ZoneInfo("Asia/Singapore")


def packed_today():
    """On Today and In The Week Ahead for a Monday 9 November, 7:15am Singapore time, with a game of every kind: under way (two Tests on a day count), UFC's main event, a badminton finals day, a golf start."""
    at = lambda d, h, m=0: datetime(2026, 11, d, h, m, tzinfo=SGT).astimezone(timezone.utc)  # noqa: E731
    now = at(9, 7, 15)
    f = lambda sport, text, when, stage="regular", mine=False, flags=(), score=None: fixtures.fixture(sport, sport, text, when, score if score is not None else importance.story_score(sport, stage, mine), mine, stage, flags)  # noqa: E731
    today = [f("cricket", "Cricket: Bangladesh v West Indies \u00b7 2nd Test \u00b7 Day 3", now, flags={"live"}), f("cricket", "Cricket: Afghanistan v Zimbabwe \u00b7 1st Test \u00b7 Day 4", now, flags={"live"}),
             f("nba", "NBA: Los Angeles Lakers at Detroit Pistons", at(9, 8, 30), mine=True), f("mlb", "MLB: Los Angeles Dodgers at New York Mets \u00b7 NLCS Game 3", at(9, 9, 8), "playoff", True),
             f("ufc", "UFC 330: Jones vs. Miocic (main event)", at(9, 11, 0), "final"), f("badminton", "Badminton: Hylo Open finals day", at(9, 12, 0), "final", flags={"dateonly"}),
             f("golf", "Golf: Masters Tournament starts", at(9, 14, 0), "final", flags={"dateonly"}),
             f("football", "Premier League: Arsenal v Brentford", at(9, 20, 30), mine=True), f("football", "Champions League: Real Madrid v Liverpool", at(9, 23, 0), "knockout"),
             f("cricket", "Cricket: New Zealand v India \u00b7 2nd ODI", at(9, 7, 30), mine=True), f("nfl", "NFL: Pittsburgh Steelers at Los Angeles Chargers", at(10, 1, 15), mine=True),
             f("f1", "F1: Brazilian Grand Prix \u00b7 Race", at(10, 1, 0), "final")]
    week = [f("nba", "NBA: Boston Celtics v Cleveland Cavaliers", at(12, 8, 30), mine=True, flags={"stars"}), f("football", "Premier League: Arsenal v Tottenham Hotspur", at(14, 20, 30), mine=True, flags={"derby"}),
            f("f1", "F1: Las Vegas Grand Prix \u00b7 Race", at(15, 14, 0), "final"), f("tennis", "Tennis: ATP Finals final", at(15, 21, 0), "final"),
            f("cricket", "Cricket: Royal Challengers Bengaluru v Sunrisers Hyderabad (IPL)", at(15, 22, 0), mine=True)]
    return ontoday.today_html(today) + ontoday.watch_html(week)


def section(page, sid):
    html = (DEMO / f"{page}.html").read_text()
    m = re.search(rf'<section id="{sid}"><h2>[^<]*</h2>(.*?)</section>', html, re.S)
    out = m.group(1) if m else ""
    if sid == "other-sports":             # the demo built each sport on its own, so each was "first"; in a real edition only the first sport has no line above it
        head, _, rest = out.partition('class="sport first"')
        out = head + 'class="sport first"' + rest.replace('class="sport first"', 'class="sport"')
    return out


if "--skip-build" not in sys.argv:
    for cmd in BUILD:
        subprocess.run([sys.executable, str(ROOT / "scripts" / cmd[0])] + cmd[1:] + ["--no-open"], cwd=ROOT, capture_output=True, text=True)
sections = []
for page, sid, title in PICK:
    html = packed_today() if sid == "on-today" else section(page, sid)
    if html:
        sections.append({"id": sid, "title": title, "html": html})
    else:
        print(f"missing: {page} / {sid}")
edition = {"date": "2026-11-09", "dummy": False, "home": "../index.html",
           "banner": "Demo: the most packed morning. A collage of real saved days, one per sport (a Champions League night, an NFL week, the MLB division series, UFC 309, the NBA weekend, cricket, F1, tennis and "
                     "the other sports), built by the real code so the layout is the real layout. Not one real morning, and the days differ.",
           "headlines": ["Champions League: Arsenal 2–1 Slavia Prague", "Cricket: New Zealand v India, India won by 5 wickets (DLS)", "NBA: Los Angeles Lakers 116–103 Sacramento Kings"],
           "sections": sections}
page = DEMO / "packed-weekend.html"
page.write_text(render.render_edition(edition))
print(f"Built {page.relative_to(ROOT)} | sections: {', '.join(s['id'] for s in sections)} | {len(page.read_text()) // 1024} KB")
if "--no-open" not in sys.argv and sys.platform == "darwin":
    subprocess.run(["open", str(page)])
if "--publish" in sys.argv:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    git("add", "docs/demo/packed-weekend.html")
    done = git("commit", "-m", "Add the packed-morning demo page")
    if done.returncode != 0:
        print("Nothing new to publish." if "nothing to commit" in (done.stdout + done.stderr) else "Could not commit: " + (done.stderr or done.stdout).strip()[:300])
    else:
        pushed = git("push", "origin", "main")
        print("Published: https://dadi-amoghraj-72.github.io/the-kickoff/demo/packed-weekend.html" if pushed.returncode == 0 else "Committed, but the push failed: " + pushed.stderr.strip()[:300])
