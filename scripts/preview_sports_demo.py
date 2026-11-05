"""One event from each of the other sports, as the page shows it, built by the real code (kickoff/around.py) so the layout is the real layout (2026-11-05).

  .venv/bin/python scripts/preview_sports_demo.py            writes docs/demo/sports-demo.html and opens it
  add --publish to put it at https://dadi-amoghraj-72.github.io/the-kickoff/demo/sports-demo.html, --no-open to skip opening it.

Each block says whether it is real data (a real saved page or today's real feeds) or a made-up game in the real layout:
  real:      rugby (a Six Nations match), golf (the 2025 Masters and Evian Championship), badminton (the 2025 All England Open day by day), darts (the 2025 Grand Slam of Darts), the live headlines of today (Yahoo, Hindu, Straits Times, Google News)
  real shape, one field changed: UFC (a real card made a finished numbered event)
  made up:   chess (an elite round in the Lichess layout; none was on)"""
import copy
import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import around, render  # noqa: E402
from kickoff.sources import other_sports  # noqa: E402

FX = ROOT / "tests" / "fixtures"
load = lambda n: json.loads((FX / n).read_text())  # noqa: E731
rd = lambda n: (FX / f"majors_{n}.txt").read_text()  # noqa: E731
utc = lambda *a: datetime(*a, tzinfo=timezone.utc)  # noqa: E731


class Fake:
    """Only what one block needs; every other page 'does not answer'."""

    def __init__(self, **kw):
        self.kw = kw

    def _get(self, name, *a):
        if name not in self.kw:
            raise RuntimeError("not in this demo block")
        v = self.kw[name]
        return v(*a) if callable(v) else v

    def rugby(self, league):
        return self._get("rugby", league)

    def golf(self, tour):
        return self._get("golf", tour)

    def ufc(self):
        return self._get("ufc")

    def ufc_rankings(self):
        return self._get("rankings")

    def news(self):
        return self._get("news")

    def wikitext(self, title):
        return self._get("wiki", title)

    def top(self):
        return self._get("top")

    def tour(self, tid):
        return self._get("tour", tid)

    def round_pgn(self, rid):
        return self._get("pgn", rid)


blocks = []


def add(title, kind, note, now, **kw):
    out = around.run(now, {}, Fake(**kw), None)
    html = "".join(s["html"] for s in out["sections"]) or "<p class='muted'>Nothing came out of this block.</p>"
    blocks.append(f"<p class='muted'><strong>Demo · {render.esc(title)} · {render.esc(kind)}.</strong> {render.esc(note)}</p>{html}")


# rugby: a real finished Six Nations match
six = load("other_rugby_six_nations.json")
final = next(e for e in six["events"] if e["status"]["type"]["name"] == "STATUS_FINAL")
add("Rugby", "Real data", "A Six Nations match from the saved ESPN scoreboard.", datetime.fromisoformat(final["date"].replace("Z", "+00:00")) + timedelta(hours=5), rugby=lambda lg: six if lg == "180659" else {"events": []})

# golf: the real 2025 Masters and Evian Championship, as the code shows them after each round
import copy as _copy  # noqa: E402
from kickoff import badminton as bd, golf  # noqa: E402

masters, evian = load("golf_masters_2025.json"), load("golf_evian_2025.json")


def upto(board, n):
    b = _copy.deepcopy(board)
    for c in b["events"][0]["competitions"][0]["competitors"]:
        for l in c["linescores"]:
            if l["period"] > n:
                l["holes"], l["value"], l["displayValue"] = 0, 0, "-"
    b["events"][0]["status"]["type"].update(state="in", completed=False, name="STATUS_IN_PROGRESS")
    return b


def golf_block(title, kind, note, board, now, tour="pga"):
    out = golf.run({tour: board}, now, {})
    html = "".join(out["blocks"]) or "<p class='muted'>Nothing came out of this block.</p>"
    html += "".join(f"<p class='muted'>Big Stuff line: {render.esc(w)}</p>" for w in out["winners"])
    blocks.append(f"<p class='muted'><strong>Demo \u00b7 {render.esc(title)} \u00b7 {render.esc(kind)}.</strong> {render.esc(note)}</p><h4>Golf</h4>{html}")


golf_block("Golf · men's major, Friday", "Real data", "The real 2025 Masters as it stood after round 2 (later rounds emptied): the first 25, then D's players below.", upto(masters, 2), utc(2025, 4, 12, 0, 0))
golf_block("Golf · men's major, Monday", "Real data", "The real 2025 Masters, final: the winner in gold (after a playoff).", {**masters, "events": [{**masters["events"][0], "endDate": "2026-11-04T20:00Z"}]}, utc(2026, 11, 5, 0, 0))
golf_block("Golf · women's major, Sunday morning", "Real data", "The real 2025 Evian Championship after round 3: the first 10 only (women's majors show the weekend only).", upto(evian, 3), utc(2025, 7, 13, 0, 0), "lpga")
golf_block("Golf · women's major, Monday", "Real data", "The real 2025 Evian Championship, final top 10.", {**evian, "events": [{**evian["events"][0], "endDate": "2026-11-04T20:00Z"}]}, utc(2026, 11, 5, 0, 0), "lpga")

# UFC: a real card made a finished numbered event
ufc = copy.deepcopy(load("other_ufc_scoreboard.json"))
ranks = load("other_ufc_rankings.json")
ev = ufc["events"][0]
ev["name"], ev["date"] = "UFC 330: Test vs. Test", "2026-11-04T22:00Z"
for c in ev["competitions"]:
    c["status"]["type"]["completed"] = True
main, co = ev["competitions"][-1], ev["competitions"][-2]
main["competitors"][0]["athlete"]["displayName"] = ranks["rankings"][0]["ranks"][0]["athlete"]["displayName"]
main["competitors"][0]["winner"], main["competitors"][1]["winner"] = True, False
co["competitors"][0]["athlete"]["displayName"] = ranks["rankings"][1]["ranks"][0]["athlete"]["displayName"]
co["competitors"][0]["winner"], co["competitors"][1]["winner"] = True, False
add("UFC", "Real shape, names and status changed", "A real upcoming card made a finished UFC 330 with ranked winners (the real finished-card layout has not been seen yet).", utc(2026, 11, 5, 0, 0), ufc=ufc, rankings=ranks)

# badminton and darts: real 2025 Wikipedia pages
pages = {"2025 All England Open": rd("all_england_2025"), "2025 Grand Slam of Darts": rd("gsod_2025"), "2025 China Open (badminton)": rd("china_open_2025")}
# badminton: the real 2025 All England Open, shown the way it would come day by day
ae = rd("all_england_2025")
parsed = bd.parse(ae)
tops = bd.top_seeds(parsed)


def day(rounds, notice=None):
    fresh = {d: [m for m in info["matches"] if m["round"] in rounds and (m["round"] in bd.LATE or bd.interesting(m, d, tops))] for d, info in parsed.items()}
    return bd.event_html("All England Open", {d: v for d, v in fresh.items() if v}, tops, notice)


for title, note, html in (("Badminton · the week before", "One line before the event starts (no list of players).", day([], bd.notice_text("All England Open", bd.level_of(ae), date(2025, 3, 11)))),
                          ("Badminton · Round of 32 day", "The matches with an Indian or Southeast Asian player or a top-three singles seed, grouped by discipline in the fixed order, always winner def. loser.", day(["Round of 32"])),
                          ("Badminton · quarter-final day", "The same, for the quarter-finals.", day(["Quarter-finals"])),
                          ("Badminton · semi-final day", "Every semi-final of the five disciplines, as tables.", day(["Semi-finals"])),
                          ("Badminton · final day", "Every final, as tables.", day(["Final"]))):
    blocks.append(f"<p class='muted'><strong>Demo \u00b7 {render.esc(title)} \u00b7 Real data (the 2025 All England Open's real page).</strong> {render.esc(note)}</p><h4>Badminton</h4>{html}")
add("Darts", "Real data", "The 2025 Grand Slam of Darts, read the day after the final (16 November 2025).", utc(2025, 11, 17, 0, 0), wiki=lambda t: pages.get(t, ""))

# chess: made-up elite round in Lichess's layout
now = utc(2027, 1, 31, 12, 0)
ms = int((now - timedelta(hours=5)).timestamp() * 1000)
g = lambda w, b, r, we, be: f'[Event "R13"]\n[White "{w}"]\n[Black "{b}"]\n[Result "{r}"]\n[WhiteElo "{we}"]\n[BlackElo "{be}"]\n\n1. e4 {r}'  # noqa: E731
earlier = {"R11": g("Gukesh, D", "Giri, Anish", "1-0", 2780, 2745), "R12": g("Wei Yi", "Gukesh, D", "0-1", 2730, 2780)}
pgn = "\n\n".join([g("Gukesh, D", "Firouzja, Alireza", "1-0", 2780, 2760), g("Caruana, Fabiano", "Nakamura, Hikaru", "1/2-1/2", 2790, 2800), g("Abdusattorov, Nodirbek", "Wei Yi", "0-1", 2750, 2730),
                   g("Giri, Anish", "Erigaisi, Arjun", "1/2-1/2", 2745, 2780)])
item = {"tour": {"id": "T1", "name": "Tata Steel Chess 2027 | Masters", "slug": "tata-steel-2027", "tier": 5, "dates": [ms - 86400000 * 12, ms + 3600000]}, "round": {"id": "R13", "name": "Round 13", "finished": True, "finishedAt": ms, "url": "https://lichess.org"}}
add("Chess", "Made up, in the real layout", "An elite round of a made-up Tata Steel 2027 in Lichess's real format (no elite event is on in November). The winner line adds up all rounds (three rounds are given here).", now,
    top=lambda: {"active": [], "past": {"currentPageResults": [item]}}, pgn=lambda rid: pgn if rid == "R13" else earlier[rid], tour=lambda tid: {"rounds": [{"id": r_, "finished": True} for r_ in ("R11", "R12", "R13")]})

# today's real live headlines
try:
    live = other_sports.Source().news()
except Exception:
    live = []
add("Live headlines of today (badminton, hockey, chess, darts ...)", "Real data", "Today's real headlines from Yahoo, The Hindu, The Straits Times, Times of India, Google News, BBC and the Guardian that the rules keep, as the source wrote them (Claude off). With Claude each becomes one checked sentence.",
    datetime.now(timezone.utc), news=live)

edition = {"date": date(2026, 11, 5).isoformat(), "dummy": False, "banner": "DEMO of the other sports: one event of each, in the real layout. Each block says what is real and what is made up.", "home": "../index.html", "headlines": [],
           "sections": [{"id": "other-sports", "title": "Other Sports", "html": "".join(blocks)}]}
path = ROOT / "docs" / "demo" / "sports-demo.html"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(render.render_edition(edition))
print("Built", path.relative_to(ROOT))
if "--no-open" not in sys.argv and sys.platform == "darwin":
    subprocess.run(["open", str(path)])
if "--publish" in sys.argv:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    git("add", "docs/demo/sports-demo.html")
    done = git("commit", "-m", "Add the other-sports demo page")
    if done.returncode != 0:
        print("Nothing new to publish." if "nothing to commit" in (done.stdout + done.stderr) else "Could not commit: " + (done.stderr or done.stdout)[:300])
    else:
        git("pull", "--rebase")
        print("Published: https://dadi-amoghraj-72.github.io/the-kickoff/demo/sports-demo.html" if git("push", "origin", "main").returncode == 0 else "Push failed.")
