"""One event from each of the other sports, as the page shows it, built by the real code (kickoff/around.py) so the layout is the real layout (2026-11-05).

  .venv/bin/python scripts/preview_sports_demo.py            writes docs/demo/sports-demo.html and opens it
  add --publish to put it at https://dadi-amoghraj-72.github.io/the-kickoff/demo/sports-demo.html, --no-open to skip opening it.

Each block says whether it is real data (a real saved page or today's real feeds) or a made-up game in the real layout:
  real:      rugby (a Six Nations match), badminton (the 2025 All England Open), darts (the 2025 Grand Slam of Darts), the live headlines of today (Yahoo, Hindu, Straits Times, Google News)
  real shape, one field changed: golf (a real PGA board with a major's name and a finished status), UFC (a real card made a finished numbered event)
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

# golf: a real PGA board made a finished major
pga = copy.deepcopy(load("other_golf_pga.json"))
e = pga["events"][0]
e["name"], e["status"]["type"]["state"], e["endDate"] = "Masters Tournament", "post", "2026-11-04T20:00Z"
top = sorted(e["competitions"][0]["competitors"], key=lambda x: x.get("order", 99))[0]
top["score"] = "-12"
add("Golf", "Real shape, name and status changed", "A real PGA Tour board, renamed 'Masters Tournament' and marked finished, so the winner line shows (no major is on in November).", utc(2026, 11, 5, 0, 0), golf=lambda t: pga if t == "pga" else {"events": []})

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
add("Badminton", "Real data", "The 2025 All England Open's real finals page, read the Monday after the final (16 March 2025), with the Indian and Southeast Asian line.", utc(2025, 3, 17, 0, 0), wiki=lambda t: pages.get(t, ""))
add("Badminton · a second event", "Real data", "The 2025 China Open, where Satwik and Chirag reached the semi-finals.", utc(2025, 7, 29, 0, 0), wiki=lambda t: {"2025 China Open (badminton)": rd("china_open_2025")}.get(t, ""))
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
