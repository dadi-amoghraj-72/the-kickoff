"""Tests for D's comments on the 11 Nov 2026 edition: the player of the match's figures, 40-point NBA games always Stars, prime-time NFL always a key score,
NFL and NBA moves in Biggest News.
Run: .venv/bin/python scripts/test_morning5.py"""
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import bigstuff, cricket, events, nba, usnews  # noqa: E402

results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


# 1. Player of the match: her figures on the line
entry = {"potm": [{"name": "Emma de Broughe", "team": "Adelaide Strikers Women"}],
         "innings": [{"batting": [{"name": "Nicola Carey", "r": 66, "b": 53, "out": "not out"}], "bowling": [{"name": "Emma de Broughe", "o": 1.0, "r": 9, "w": 0}]},
                     {"batting": [{"name": "Emma de Broughe", "r": 41, "b": 37, "out": "c Carey b Malgioglio"}], "bowling": []}]}
got = cricket.potm_html(entry, True)
check("POTM line carries her score in gold", '<span class="n">41 (37)</span>' in got and "Emma de Broughe" in got, got)
check("a wicketless spell is not shown", "0/9" not in got, got)
allround = {"potm": [{"name": "A", "team": "X"}], "innings": [{"batting": [{"name": "A", "r": 30, "b": 20, "out": "not out"}], "bowling": []},
                                                            {"batting": [], "bowling": [{"name": "A", "o": 4.0, "r": 24, "w": 2}]}]}
got = cricket.potm_html(allround, True)
check("an all-rounder: both figures, not out marked", "30* (20)" in got and "2/24</span> (4 ov)" in got, got)
check("a name not on the card: the line as before", cricket.potm_html({"potm": [{"name": "Z", "team": "X"}], "innings": []}, True).endswith("(X)</span>"))

# 2. NBA: 40 points or a triple-double is a milestone, always a Star
p40 = {"PTS": 43, "REB": 10, "AST": 6, "STL": 3, "BLK": 0}
check("43 points is a milestone", nba.big_night(p40))
check("a triple-double is a milestone", nba.big_night({"PTS": 25, "REB": 16, "AST": 10, "STL": 0, "BLK": 0}))
check("32-8-10 is not", not nba.big_night({"PTS": 32, "REB": 8, "AST": 10, "STL": 5, "BLK": 2}))
perfs = events.nba_perf([("Wembanyama (SAS): 40 pts", 95, True), ("Doncic (LAL): 32 pts", 90, False), ("Flagg (DAL): 43 pts", 80, True), ("Davis (WSH): 44 pts", 78, True)])
names = [p["text"].split(" ")[0] for p in bigstuff.stars(perfs)]
check("11 Nov: Wembanyama, Doncic, Flagg and Davis are all Stars", names == ["Wembanyama", "Doncic", "Flagg", "Davis"], names)
check("old two-item rows still work", events.nba_perf([("x", 80)])[0].get("milestone") is None)

# 3. NFL: a prime-time game always makes Key Overnight Scores
mnf = {"status": "final", "date": datetime(2026, 11, 10, 1, 15, tzinfo=timezone.utc), "away": {"name": "Buffalo Bills", "score": 23, "abbr": "BUF"},
       "home": {"name": "Minnesota Vikings", "score": 6, "abbr": "MIN"}}
early = {**mnf, "date": datetime(2026, 11, 8, 18, 0, tzinfo=timezone.utc)}
check("MNF is prime time", events.nfl([mnf], 2, 10, 2)[0].get("primetime"))
check("a 1pm Sunday game is not", not events.nfl([early], 2, 10, 2)[0].get("primetime"))
nbas = [{**events.story("nba", "NBA", f"NBA: game {i}", 6 + i, False, "regular"), "kind": "result"} for i in range(4)]
cric = {**events.story("cricket", "Cricket", "Cricket: NZ v India", 9, True, "regular"), "kind": "result"}
picked = [s["text"] for s in bigstuff.select(nbas + [cric] + events.nfl([mnf], 2, 10, 2), 2)]
check("11 Nov: MNF makes it on a full Wednesday", "NFL: Buffalo Bills 23–6 Minnesota Vikings" in picked, picked)
dull = {**mnf, "away": {**mnf["away"], "score": 10}, "home": {**mnf["home"], "score": 7}}
picked = [s["text"] for s in bigstuff.select(events.nfl([dull], 2, 10, 2), 2)]
check("a dull prime-time game still makes it (below the usual bar)", len(picked) == 1, picked)

# 4. NFL and NBA moves for Biggest News
now = datetime(2026, 11, 11, 23, 15, tzinfo=timezone.utc)
art = lambda h, t="HeadlineNews", when="2026-11-11T14:30:00Z": {"headline": h, "type": t, "published": when, "links": {"web": {"href": "https://espn.com/x"}}}  # noqa: E731
arts = [art("Raiders name Fernando Mendoza starting QB after trading Kirk Cousins"), art("Sources: Giants called Falcons to ask about Bijan Robinson before trade deadline"),
        art("RB Jonathan Taylor, QB Daniel Jones remain with Colts as trade deadline passes"), art("What the Kirk Cousins trade means", "Story"),
        art("Stephen A. has some words after Vikings trade for Kirk Cousins", "Media"), art("Falcons trade center Ryan Neuzil to Ravens", when="2026-11-09T10:00:00Z"),
        art("Giants' Nabers calls analyst's critique a 'lie'")]
got = [c["text"] for c in usnews.candidates(arts, now, "NFL")]
check("only the confirmed hard-news move of the last day", got == ["NFL: Raiders name Fernando Mendoza starting QB after trading Kirk Cousins"], got)


class Fake:
    def __init__(self, reply):
        self.reply = reply


calls = []
usnews.notes.call_json, real = (lambda client, system, schema, content, model=None: (calls.append(content) or client.reply, {"input": 100, "output": 10})), usnews.notes.call_json
feed = {"football/nfl": {"articles": arts}, "basketball/nba": {"articles": []}}
items, usage = usnews.find(Fake({"nfl": 1, "nba": 0}), now, get_json=lambda url: feed["football/nfl" if "nfl" in url else "basketball/nba"])
check("Claude's pick is kept, marked as US news, with the ESPN link", [(i["text"], i["us"], i["link"]) for i in items] ==
      [("NFL: Raiders name Fernando Mendoza starting QB after trading Kirk Cousins", True, "https://espn.com/x")], items)
items, _ = usnews.find(Fake({"nfl": 0, "nba": 0}), now, get_json=lambda url: feed["football/nfl" if "nfl" in url else "basketball/nba"])
check("nothing big: nothing", items == [])
n = len(calls)
items, usage = usnews.find(None, now, get_json=lambda url: feed["football/nfl" if "nfl" in url else "basketball/nba"])
check("no Claude: no call and nothing", items == [] and len(calls) == n and usage == {"input": 0, "output": 0})
usnews.notes.call_json = real

foot = [{"text": "Arsenal sign A Player"}, {"text": "Spurs sack Their Manager"}]
us = [{"text": "NFL: Raiders name Fernando Mendoza starting QB after trading Kirk Cousins", "us": True}]
check("Biggest News: football first, then the US move", [i["text"] for i in bigstuff.top_news(foot + us)] == ["Arsenal sign A Player", us[0]["text"]])
check("only the US move: it shows", [i["text"] for i in bigstuff.top_news(us)] == [us[0]["text"]])
check("no US move: football's two", [i["text"] for i in bigstuff.top_news(foot)] == ["Arsenal sign A Player", "Spurs sack Their Manager"])

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
