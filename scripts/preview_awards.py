"""Preview the Awards tables and the season closing notes, on the real saved ESPN and Wikipedia data. No key, no calls.

  .venv/bin/python scripts/preview_awards.py            writes docs/demo/awards.html and opens it
  add --publish to put it at https://dadi-amoghraj-72.github.io/the-kickoff/demo/awards.html, --no-open to skip opening it.

The NBA (2025-26 awards) and NFL (2025 season) awards are replayed as if announced over several mornings, so the table can be seen growing: the newest at the top, the
older ones still below it. The closing notes are the real 2026 NBA Finals and Super Bowl LX results. The 'season is coming' note needs Claude and is not in this page."""
import copy
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import awards, nba, nfl, render  # noqa: E402
from kickoff.sources import espn_awards  # noqa: E402

FX = ROOT / "tests" / "fixtures"
REC = json.loads((FX / "espn_awards.json").read_text())
W = {k: (FX / v).read_text() for k, v in {"2026 NBA All-Star Game": "wiki_nba_asg_2026.txt", "NBA Coach of the Year Award": "wiki_nba_coy.txt",
                                          "2025 All-Pro Team": "wiki_all_pro_2025.txt", "2026 Pro Bowl Games": "wiki_pro_bowl_2026.txt"}.items()}


class Wiki:
    def __init__(self, replace=None):
        self.replace = replace or {}

    def wikitext(self, page):
        t = W.get(page, "")
        for a, b in self.replace.items():
            cut = t.find("|+Western Conference All-Stars")
            t = t[:cut] + t[cut:].replace(a, b, 1) if cut > 0 else t
        return t


HIST = json.loads((FX / "espn_allnba_history.json").read_text())


class Replay(espn_awards.Source):
    """ESPN's awards as the replay shows them on one morning: only the awards named in `show` have their winners; the All-NBA history is the saved real one."""
    def winners(self, season, award_id):
        return HIST.get(str(season), {}).get(award_id) or []


def source(sport, league, show):
    def get(url):
        j = copy.deepcopy(REC[url])
        m = re.search(r"/awards/(\d+)$", url.split("?")[0])
        if m and j.get("winners") and j["name"] not in show:
            j["winners"] = []
        return j
    return Replay(sport, league, get_json=get, pause=0)


def days(league, sport, title, season, schedule, wiki_days=None):
    """The table on each morning of `schedule` ([(label, names announced so far)]); the first morning is the silent first sight."""
    html, state = "", {}
    for i, (label, show) in enumerate(schedule):
        wiki = wiki_days[i] if wiki_days else None
        extra = awards.wiki_items(league, season, wiki) if wiki else []
        out, state = awards.run(source(sport, league, show), title, copy.deepcopy(state), season, extra=extra)
        if i > 0:
            html += f'<h4>{label}</h4>{out or "<p class=muted>Nothing new: no table.</p>"}'
    return html


nba_sched = [("start", set()), ("Morning 1: Rookie and Sixth Man announced", {"Rookie of the Year", "Sixth Man of the Year"}),
             ("Morning 2: Defensive Player and Most Improved added", {"Rookie of the Year", "Sixth Man of the Year", "Defensive Player of the Year", "Most Improved Player"}),
             ("Morning 3: the All-NBA teams, MVP and the conference finals MVPs", {"Rookie of the Year", "Sixth Man of the Year", "Defensive Player of the Year", "Most Improved Player", "MVP",
              "All-NBA 1st Team", "All-NBA 2nd Team", "All-NBA 3rd Team", "NBA Eastern Conference Finals MVP", "NBA Western Conference Finals MVP", "Twyman-Stokes Teammate of the Year Award"}),
             ("Morning 4: Finals MVP lands later (the team lists are not repeated between announcements)", {"Rookie of the Year", "Sixth Man of the Year", "Defensive Player of the Year", "Most Improved Player", "MVP",
              "All-NBA 1st Team", "All-NBA 2nd Team", "All-NBA 3rd Team", "NBA Eastern Conference Finals MVP", "NBA Western Conference Finals MVP", "Twyman-Stokes Teammate of the Year Award", "Finals MVP"})]
nba_html = days("nba", "basketball", "NBA Awards", 2026, nba_sched, wiki_days=[None, None, None, Wiki(), Wiki()])
nba_html += "<h4>The closing note when the Finals are decided (real 2026 Finals)</h4>" + nba.closing_html(
    2026, [x for x in json.loads((FX / "nba_finals_2026_schedule.json").read_text()) if x["headline"].startswith("NBA Finals")])

nfl_sched = [("start", set()), ("Morning 1: Coach of the Year and MVP", {"NFL Coach of the Year", "NFL MVP"}),
             ("Morning 2: the rest of the NFL Honors, Walter Payton Man of the Year and Super Bowl MVP", {"NFL Coach of the Year", "NFL MVP", "NFL Offensive Player of the Year", "NFL Defensive Player of the Year",
              "NFL Offensive Rookie of the Year", "NFL Defensive Rookie of the Year", "NFL Comeback Player of the Year", "Walter Payton NFL Man of the Year", "Super Bowl MVP"})]
nfl_html = days("nfl", "football", "NFL Awards", 2025, nfl_sched, wiki_days=[None, None, Wiki()])
sb = json.loads((FX / "nfl_superbowl_2025.json").read_text())
nfl_html += "<h4>The closing note when the Super Bowl is played (real Super Bowl LX)</h4>" + nfl.closing_html(nfl.super_bowl(sb["events"]))[0]

banner = ("PREVIEW of the Awards tables and the season closing notes on real 2025-26 data, replayed over several mornings. In the real edition only one table appears per morning, "
          "the morning something new is announced, inside the sport's section. The first morning of a sport is silent (existing awards are remembered, not shown).")
edition = {"date": date(2026, 11, 4).isoformat(), "dummy": False, "banner": banner, "home": "../index.html", "headlines": [],
           "sections": [{"id": "nba", "title": "NBA", "html": nba_html}, {"id": "nfl", "title": "NFL", "html": nfl_html}]}
out = ROOT / "docs" / "demo" / "awards.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(render.render_edition(edition))
print("Built", out.relative_to(ROOT))
if "--no-open" not in sys.argv and sys.platform == "darwin":
    subprocess.run(["open", str(out)])
if "--publish" in sys.argv:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    git("add", "docs/demo/awards.html")
    done = git("commit", "-m", "Update awards demo page")
    if done.returncode != 0:
        print("Nothing new to publish." if "nothing to commit" in (done.stdout + done.stderr) else "Could not commit: " + (done.stderr or done.stdout)[:300])
    else:
        git("pull", "--rebase")
        print("Published: https://dadi-amoghraj-72.github.io/the-kickoff/demo/awards.html" if git("push", "origin", "main").returncode == 0 else "Push failed.")
