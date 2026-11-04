"""Offline tests for the IPL extras (Orange and Purple Cap, closing note, end-of-season awards) on the saved real Wikipedia page of IPL 2026. Run: python3 scripts/test_ipl.py"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import cricket as ck, ipl  # noqa: E402

FX = ROOT / "tests" / "fixtures"
PAGE = (FX / "wiki_ipl_2026.txt").read_text()
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


class Wiki:
    def __init__(self, text=PAGE):
        self.text, self.asked = text, []

    def wikitext(self, page):
        self.asked.append(page)
        return self.text if page == "2026 Indian Premier League" else ""


text = lambda h: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))  # noqa: E731
st = ipl.stats(PAGE)
check("the top five run-scorers from the page: Sooryavanshi 776, Gill 732, Sudharsan 722, Kohli 675, Klaasen 624, with team codes", [(n, w, t) for n, w, t in st["runs"]] == [(776, "Vaibhav Sooryavanshi", "RR"), (732, "Shubman Gill", "GT"), (722, "Sai Sudharsan", "GT"), (675, "Virat Kohli", "RCB"), (624, "Heinrich Klaasen", "SRH")], st["runs"])
raw_runs = [int(x) for x in re.findall(r"\|\+ Most runs.*?\n(.*?)\|\}", PAGE, re.S)[0].split("scope=row | ")[1:] and re.findall(r"scope=row \| (\d+)", re.findall(r"\|\+ Most runs.*?\n(.*?)\|\}", PAGE, re.S)[0])]
check("independent: the five run totals are exactly the raw numbers in the page's table, in order", [n for n, _, _ in st["runs"]] == raw_runs, raw_runs)
check("the wicket table keeps ties: Rashid Khan and Anshul Kamboj are both on 21", [(n, w) for n, w, _ in st["wickets"]][:5] == [(29, "Kagiso Rabada"), (28, "Bhuvneshwar Kumar"), (25, "Jofra Archer"), (21, "Rashid Khan"), (21, "Anshul Kamboj")], st["wickets"])
check("a page without the tables gives nothing", ipl.stats("nothing here") == {} and ipl.stats("") == {})

ch = ipl.caps_html(st, limit=5)
check("the caps: 'Orange Cap · most runs' and 'Purple Cap · most wickets', Sooryavanshi first, each with its figure and team", "Orange Cap · most runs" in ch and "Purple Cap · most wickets" in ch and "Vaibhav Sooryavanshi" in ch and "776" in ch and "Kagiso Rabada" in ch, text(ch)[:300])
check("D's rule: Sunrisers Hyderabad's row (Klaasen) carries the gold class, nobody else's does", ch.count('class="hl"') == 1 and "Heinrich Klaasen" in ch.split('class="hl"')[1].split("</tr>")[0], ch.count('class="hl"'))
check("the default is the top three of each", ipl.caps_html(st).count("<tr") == 2 * (1 + 1 + 3), ipl.caps_html(st).count("<tr"))
check("no stats, no caps", ipl.caps_html({}) == "")

aw = ipl.end_awards(PAGE)
check("end of season: the Most Valuable Player and the Emerging Player (both Vaibhav Sooryavanshi of Rajasthan Royals)", aw == {"MVP": ("Vaibhav Sooryavanshi", "RR"), "Emerging": ("Vaibhav Sooryavanshi", "RR")}, aw)
check("before the awards exist: nothing", ipl.end_awards(PAGE.split("=== End of season awards ===")[0]) == {})

# ---- the closing note from ESPN's own final ----
final = {"name": "Royal Challengers Bengaluru vs Gujarat Titans, Final, Indian Premier League 2026", "matchEnded": True, "status": "Royal Challengers Bengaluru won by 5 wickets"}
check("the closing note: IPL 2026, the champions and how they won (the page says Royal Challengers beat Gujarat Titans by 5 wickets in the final)", "That&#x27;s IPL 2026. Royal Challengers Bengaluru are champions, winning the final by 5 wickets." in ipl.closing_html(final), ipl.closing_html(final))
check("not for a qualifier, an unfinished final or a final with no winner", ipl.closing_html({**final, "name": "A vs B, Qualifier 1, Indian Premier League 2026"}) == "" and ipl.closing_html({**final, "matchEnded": False}) == "" and ipl.closing_html({**final, "status": "Match tied"}) == "")

# ---- the extras function the cricket block calls ----
go = ipl.extras_for(2026, Wiki())
h1, s1 = go("IPL", [final], {})
check("on a morning with IPL matches: the caps, then the closing note, and the year is remembered", "Orange Cap" in h1 and "champions" in h1 and s1 == {"closed": 2026} and h1.index("Orange Cap") < h1.index("champions"), (text(h1)[:200], s1))
h2, s2 = go("IPL", [final], s1)
check("the next morning with the final still in view: caps again, the closing note not repeated", "Orange Cap" in h2 and "champions" not in h2 and s2 == s1)
check("other leagues get nothing from it", go("WBBL", [final], {}) == ("", {}))


class Down:
    def wikitext(self, page):
        raise OSError("down")


hd, sd = ipl.extras_for(2026, Down())("IPL", [final], {})
check("Wikipedia down: no caps, but the closing note (from ESPN's own data) still comes", "champions" in hd and "Orange" not in hd and sd == {"closed": 2026}, hd[:120])

# ---- through the cricket block itself ----
NOW = datetime(2026, 5, 31, 23, 30, tzinfo=timezone.utc)
m = {"id": "ipl-final", "name": final["name"], "matchType": "t20", "teams": ["Royal Challengers Bengaluru", "Gujarat Titans"], "matchStarted": True, "matchEnded": True,
     "status": final["status"], "dateTimeGMT": "2026-05-31T14:00:00",
     "score": [{"inning": "Gujarat Titans Inning 1", "r": 160, "w": 8, "o": 20}, {"inning": "Royal Challengers Bengaluru Inning 1", "r": 161, "w": 5, "o": 18.4}]}
out = ck.run(NOW, datetime(2026, 5, 31, 0, 0, tzinfo=timezone.utc), {}, lambda: ([m], 1), lambda mid: (_ for _ in ()).throw(RuntimeError("no")), lambda used: 0, extras_fn=ipl.extras_for(2026, Wiki()))
oh = text(out["html"])
check("the IPL block of the final's morning has the result, the Orange and Purple Cap leaders and the closing note", "Royal Challengers Bengaluru" in oh and "Orange Cap" in oh and "Purple Cap" in oh and "champions" in oh and out["state"]["ipl"] == {"closed": 2026}, oh[:300])
out2 = ck.run(NOW, datetime(2026, 5, 31, 0, 0, tzinfo=timezone.utc), {}, lambda: ([m], 1), lambda mid: (_ for _ in ()).throw(RuntimeError("no")), lambda used: 0, extras_fn=lambda *a: 1 / 0)
check("an extras function that blows up costs the cricket block nothing", "Royal Challengers Bengaluru" in text(out2["html"]) and "Orange" not in out2["html"], text(out2["html"])[:150])

# ---- the awards block ----
from kickoff import awards  # noqa: E402
before = Wiki(PAGE.split("=== End of season awards ===")[0] + "\n== See also ==\n")
fresh = {"season": 2026, "seen": {}, "rows": [], "names": {}}
hb, sb = ipl.awards_block(2026, fresh, before)
check("before the awards are on the page: no table", hb == "" and sb["rows"] == [])
ha, sa = ipl.awards_block(2026, sb, Wiki())
check("the morning the page has them: an 'IPL Awards' table with MVP and Emerging, Vaibhav Sooryavanshi (RR) both times", "IPL Awards" in ha and text(ha).count("Vaibhav Sooryavanshi") == 2 and "MVP" in ha and "Emerging" in ha and ha.count("wn mvp") == 1, text(ha)[:200])
hc, sc = ipl.awards_block(2026, sa, Wiki())
check("and not again afterwards", hc == "" and sc == sa)

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
