"""Preview rounds 2 and 3 of the season work on real saved data: MLB awards, the IPL's caps, closing note and awards, and the Premier League's closing note and awards with
the FA Cup and Champions League closing notes. No key, no calls.

  .venv/bin/python scripts/preview_season.py            writes docs/demo/season.html and opens it
  add --publish to put it at https://dadi-amoghraj-72.github.io/the-kickoff/demo/season.html, --no-open to skip opening it.

The MLB awards are the real 2025 ones replayed over mornings (2026's are still being announced); the IPL page is the real IPL 2026 season page; the football data is the real
2025-26 final table and the real FA Cup and Champions League finals of May 2026."""
import copy
import html as _html
import json
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import awards, football_season as fs, ipl, render  # noqa: E402
from kickoff.sources import espn, espn_awards  # noqa: E402

FX = ROOT / "tests" / "fixtures"
REC = json.loads((FX / "espn_awards.json").read_text())
R = lambda n: (FX / n).read_text()  # noqa: E731


class Replay(espn_awards.Source):
    def winners(self, season, award_id):
        return []


def source(show):
    def get(url):
        j = copy.deepcopy(REC[url])
        m = re.search(r"/awards/(\d+)$", url.split("?")[0])
        if m and j.get("winners") and j["name"] not in show:
            j["winners"] = []
        return j
    return Replay("baseball", "mlb", get_json=get, pause=0)


class Wiki:
    def __init__(self, pages):
        self.pages = pages

    def wikitext(self, page):
        return self.pages.get(page, "")


# ---- MLB ----
MW = Wiki({"Major League Baseball Manager of the Year Award": R("wiki_mlb_moty.txt"), "Gold Glove Award": R("wiki_mlb_plat.txt")})
sched = [("start", set(), None),
         ("Morning 1: MVP and Cy Young (a pair each: AL then NL), the World Series MVP and the Roberto Clemente Award", {"MVP", "Cy Young", "World Series MVP", "Roberto Clemente Award"}, None),
         ("Morning 2: the Gold Glove (20 winners, a block by league)", {"MVP", "Cy Young", "World Series MVP", "Roberto Clemente Award", "Gold Glove"}, None),
         ("Morning 3: Platinum Glove Awardees and Manager of the Year join (from Wikipedia), Rookie of the Year", {"MVP", "Cy Young", "World Series MVP", "Roberto Clemente Award", "Gold Glove", "Rookie of the Year"}, MW)]
mlb_html, state = "", {}
for i, (label, show, wiki) in enumerate(sched):
    extra = awards.wiki_items("mlb", 2025, wiki) if wiki else []
    out, state = awards.run(source(show), "MLB Awards", copy.deepcopy(state), 2025, extra=extra)
    if i:
        mlb_html += f"<h4>{_html.escape(label)}</h4>{out or '<p class=muted>Nothing new.</p>'}"
all_star = awards.wiki_items("mlb", 2026, Wiki({"2026 Major League Baseball All-Star Game": R("wiki_mlb_asg_2026.txt")}))
mlb_html += "<h4>The All-Star selections (the real 2026 page; shown the morning they are announced)</h4>" + awards.table_html("MLB Awards", [{**x, "note": ""} for x in all_star])

# ---- IPL ----
page = R("wiki_ipl_2026.txt")
wiki_ipl = Wiki({"2026 Indian Premier League": page})
final = {"name": "Royal Challengers Bengaluru vs Gujarat Titans, Final, Indian Premier League 2026", "matchEnded": True, "status": "Royal Challengers Bengaluru won by 5 wickets"}
extra, _ = ipl.extras_for(2026, wiki_ipl)("IPL", [final], {})
ipl_html = "<h4>A morning with IPL matches: the cap leaders (orange and purple, shown here with the top five; no gold row here), then on the final's morning the closing note</h4>"
ipl_html += ipl.caps_html(ipl.stats(page), limit=5) + ipl.closing_html(final)
aw_html, _ = ipl.awards_block(2026, {"season": 2026, "seen": {}, "rows": [], "names": {}}, wiki_ipl, yahoo_page=R("yahoo_ipl_2026_awards.html"))
ipl_html += "<h4>The morning the end-of-season awards are on the page (Wikipedia's table plus Yahoo Sports' article)</h4>" + aw_html

# ---- Premier League ----
rows = espn.parse_table(json.loads(R("espn_eng1_table_2025.json")))
fa = [espn.parse_match(e, "eng.fa") for e in json.loads(R("espn_facup_final_2026.json"))["events"]]
cl = [espn.parse_match(e, "uefa.champions") for e in json.loads(R("espn_cl_final_2026.json"))["events"]]
pages = {n: R(f) for n, f in (("Premier League Player of the Season", "wiki_pl_pots.txt"), ("Premier League Young Player of the Season", "wiki_pl_young.txt"),
                                ("Premier League Manager of the Season", "wiki_pl_manager.txt"), ("Premier League Golden Boot", "wiki_pl_boot.txt"), ("Premier League Golden Glove", "wiki_pl_glove.txt"))}
fo = fs.build(date(2026, 5, 25), datetime(2026, 5, 24, 23, 0, tzinfo=timezone.utc), rows, fa, cl, {}, client=None, wiki=Wiki(pages))
pl_html = "<h4>Premier League season (the morning after the last day, 25 May 2026)</h4>" + fo["pl"] + "<h4>FA Cup closing note</h4>" + fo["fa"] + "<h4>Champions League closing note</h4>" + fo["cl"]

banner = ("PREVIEW of rounds 2 and 3 (MLB, IPL, Premier League) on real saved data. In the real edition each part appears only on the morning something new is announced. "
          "The 'season is coming' notes need Claude and are not in this page.")
edition = {"date": date(2026, 11, 4).isoformat(), "dummy": False, "banner": banner, "home": "../index.html", "headlines": [],
           "sections": [{"id": "mlb", "title": "MLB", "html": mlb_html}, {"id": "cricket", "title": "IPL", "html": ipl_html}, {"id": "football", "title": "Football", "html": pl_html}]}
out = ROOT / "docs" / "demo" / "season.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(render.render_edition(edition))
print("Built", out.relative_to(ROOT))
if "--no-open" not in sys.argv and sys.platform == "darwin":
    subprocess.run(["open", str(out)])
if "--publish" in sys.argv:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    git("add", "docs/demo/season.html")
    done = git("commit", "-m", "Update season demo page")
    if done.returncode != 0:
        print("Nothing new to publish." if "nothing to commit" in (done.stdout + done.stderr) else "Could not commit: " + (done.stderr or done.stdout)[:300])
    else:
        git("pull", "--rebase")
        print("Published: https://dadi-amoghraj-72.github.io/the-kickoff/demo/season.html" if git("push", "origin", "main").returncode == 0 else "Push failed.")
