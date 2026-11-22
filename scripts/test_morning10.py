"""Tests for D's review of 22 Nov 2026 (second batch): highlighted scores and new positions, Arsenal men's scoreboard (goals, cards, substitutions), Raya in Major Injuries,
Football in Biggest News, injury news under its own heading, rugby under one competition header, no rugby under World Cups, F1 grid sizes from the articles, stars on the day,
Harden's night first, the 45% favourite.
Run: .venv/bin/python scripts/test_morning10.py"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import around, events, f1grid, focus, news, overview, render  # noqa: E402
from kickoff.sources import espn  # noqa: E402

results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


# Highlights
h = render.highlight("Chelsea dropped from fifth to eighth on 16. Leeds won 4–1. Solanke in the 51st. Eze scored in the 33rd minute. City are third on 22.")
check("only the new position is picked out", '<span class="hl">eighth</span>' in h and ">fifth<" not in h and '<span class="hl">third</span>' in h, h)
check("the score is picked out and a goal minute is not", '<span class="hl">4–1</span>' in h and ">51st<" not in h and ">33rd<" not in h, h)
check("'from 11th to ninth' picks out ninth only", '<span class="hl">ninth</span>' in render.highlight("rose from 11th to ninth") and ">11th<" not in render.highlight("rose from 11th to ninth"))

# Arsenal timeline
game = {"home": {"id": "361", "name": "Newcastle United", "abbr": "NEW"}, "away": {"id": "359", "name": "Arsenal", "abbr": "ARS"},
        "timeline": [{"minute": "33'", "at": 1969, "kind": "goal", "side": "away", "player": "Eberechi Eze", "other": "Kai Havertz", "injury": False, "own_goal": False, "penalty": False},
                     {"minute": "56'", "at": 3300, "kind": "yellow", "side": "away", "player": "Declan Rice", "other": "", "injury": False, "own_goal": False, "penalty": False},
                     {"minute": "70'", "at": 4200, "kind": "sub", "side": "away", "player": "Kepa Arrizabalaga", "other": "David Raya", "injury": True, "own_goal": False, "penalty": False},
                     {"minute": "75'", "at": 4500, "kind": "red", "side": "home", "player": "Dan Burn", "other": "", "injury": False, "own_goal": False, "penalty": False}]}
t = focus.timeline_html(game, "359")
import html as _html  # noqa: E402
plain = _html.unescape(re.sub(r"<[^>]+>", " ", t))
check("the scoreboard lists goal, card, substitution and red in order", all(x in plain for x in ("33'", "Eze (Kai Havertz)", "Rice", "Kepa Arrizabalaga on for David Raya (injury)", "Burn")) and plain.index("Eze") < plain.index("Rice") < plain.index("Kepa") < plain.index("Burn"), plain)
check("cards are coloured boxes and each line has a team code", 'class="card yellow"' in t and 'class="card red"' in t and "<strong>ARS</strong>" in t and "<strong>NEW</strong>" in t, t)
check("Arsenal's injured substitution is named", focus.injured_off(game, "359") == ["David Raya"], focus.injured_off(game, "359"))
check("it reaches Major Injuries", events.hurt_in_game([("David Raya", "Newcastle United")]) == [{"text": "David Raya (ARS): came off injured v Newcastle United"}])
check("a game with no timeline gives no list", focus.timeline_html({"home": {}, "away": {}}, "359") == "")
tl = espn.timeline([{"type": {"type": "substitution", "text": "Substitution"}, "text": "Substitution, Arsenal. A replaces B because of an injury.", "clock": {"value": 4200.0, "displayValue": "70'"},
                     "scoringPlay": False, "team": {"id": "359"}, "participants": [{"athlete": {"displayName": "A"}}, {"athlete": {"displayName": "B"}}]},
                    {"type": {"type": "start-delay", "text": "Start Delay"}, "text": "", "clock": {"value": 1.0}, "scoringPlay": False, "team": {}, "participants": []}], {"359": "away"})
check("ESPN's key events become the timeline, quiet kinds left out", len(tl) == 1 and tl[0]["kind"] == "sub" and tl[0]["injury"] and tl[0]["player"] == "A" and tl[0]["other"] == "B" and tl[0]["side"] == "away", tl)

# Biggest News / injury news
item = {"kind": "milestone", "club": "Kane", "summary": "England's Kane breaks the caps record.", "headline": "x", "link": "l", "source": "BBC", "published": datetime(2026, 11, 21, tzinfo=timezone.utc)}
check("football in Biggest News says Football", events.football_news([item])[0]["text"].startswith("Football: "), events.football_news([item]))
inj = {"kind": "injury", "club": "PSG", "summary": "Doue carried off.", "headline": "h", "link": "l2", "source": "Guardian", "published": datetime(2026, 11, 21, tzinfo=timezone.utc), "section": "football"}
check("an injury story is not under Transfers And Managers", "Doue" not in news.html([inj], "football", "Transfers And Managers", skip=("injury",)))
check("it has its own heading", "Injury News" in news.html([inj], "football", "Injury News", kinds=("injury",)) and "Doue" in news.html([inj], "football", "Injury News", kinds=("injury",)))
check("a club's own winning run is not a milestone", "club's own winning streak" in news.SYSTEM or "club's own winning streak" in open(ROOT / "kickoff/news.py").read())

# Rugby
src = type("S", (), {"rugby": lambda self, league: {"events": [{"id": "1", "date": "2026-11-21T14:00Z", "status": {"type": {"name": "STATUS_FINAL"}}, "competitions": [{"competitors": [
    {"homeAway": "home", "score": "37", "team": {"displayName": "England"}}, {"homeAway": "away", "score": "12", "team": {"displayName": "New Zealand"}}]}]}]}})()
got = around.rugby(src, datetime(2026, 11, 22, 0, 0, tzinfo=timezone.utc))
check("rugby results still carry their competition in the data", got and got[0][0].endswith(")"), got)
check("World Cups never takes a rugby line", around.EXCLUDE["worldcups"].search("Rugby union") is not None and 'EXCLUDE["worldcups"].search(lead)' in (ROOT / "kickoff/around.py").read_text())

# F1 grid
rows = [{"position": "1", "Driver": {"givenName": "Kimi", "familyName": "Antonelli"}, "Constructor": {"name": "Mercedes"}},
        {"position": "2", "Driver": {"givenName": "Max", "familyName": "Verstappen"}, "Constructor": {"name": "Red Bull"}},
        {"position": "3", "Driver": {"givenName": "George", "familyName": "Russell"}, "Constructor": {"name": "Mercedes"}}]
items = [{"source": "BBC", "title": "Antonelli takes a grid penalty, Verstappen on pole", "text": "", "link": "http://x", "published": datetime(2026, 11, 22, tzinfo=timezone.utc)}]
saved = f1grid.article_text, f1grid.notes.call_json
calls = []
f1grid.article_text = lambda link: "Kimi Antonelli will drop five places on the grid after a gearbox change, leaving Max Verstappen on pole."


def fake(client, system, schema, content, model=None):
    calls.append(content)
    if "gearbox" in content:
        return {"penalties": [{"driver": "Kimi Antonelli", "kind": "places", "places": 5, "reason": "gearbox change"}]}, {"input": 1, "output": 1}
    return {"penalties": []}, {"input": 1, "output": 1}


f1grid.notes.call_json = fake
try:
    pens, _ = f1grid.find(object(), "Las Vegas Grand Prix", rows, items, datetime(2026, 11, 22, 1, tzinfo=timezone.utc))
finally:
    f1grid.article_text, f1grid.notes.call_json = saved
check("the grid reads the articles when the headline has no size: Antonelli five places", pens.get("Kimi Antonelli", {}).get("places") == 5, pens)
check("Verstappen, only named in the report, is not given a penalty", "Max Verstappen" not in pens, pens)
check("the provisional grid puts Verstappen on pole", f1grid.provisional(rows, pens)[0] == "Max Verstappen", f1grid.provisional(rows, pens))

# Stars on the day, Harden first
o = {"kind": "century", "name": "KL Rahul", "team": "India", "against": "New Zealand", "runs": 136, "balls": 290, "not_out": False, "fours": 9, "sixes": 2, "today": 43, "today_unit": "runs", "id": "m"}
class M(dict):
    pass
m = {"id": "m", "matchType": "test", "teams": ["New Zealand", "India"], "name": "NZ v IND", "class": {"label": "International", "kind": "international"}, "matchEnded": False, "score": []}
_, perfs, _ = events.cricket([m], {"m": {"standouts": [o]}}, 6, now=datetime(2026, 11, 22, tzinfo=timezone.utc))
check("43 runs of a 136 is not a star night and not forced in", all(p["score"] < 70 and not p.get("milestone") for p in perfs), perfs)
full = {**o, "today": 120}
_, perfs2, _ = events.cricket([m], {"m": {"standouts": [full]}}, 6, now=datetime(2026, 11, 22, tzinfo=timezone.utc))
check("a hundred made that day still is", any(p["score"] >= 70 and p.get("milestone") for p in perfs2) or any(p["score"] >= 100 for p in perfs2), perfs2)
rows_n = events.nba_perf([("James Harden (CLE): 51 pts", 78.0, True, True), ("Tyler Herro (MIL): 50 pts", 73.7, True, False)])
check("Harden's night carries the mine flag and ranks above Herro's", rows_n[0]["mine"] and rows_n[0]["score"] > rows_n[1]["score"] and not rows_n[1]["mine"], rows_n)

# Favourite
fav = overview.verdict({"home_score": 1, "away_score": 4}, {"home": 49, "draw": 28, "away": 23})
check("Chelsea at 49% beaten at home is an upset now", fav == "upset", fav)
check("a 40-40 match is still close", overview.verdict({"home_score": 1, "away_score": 0}, {"home": 40, "draw": 20, "away": 40}) == "close_match")

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
