"""Cricket exactly as GitHub sees it (D, 2026-11-08): ESPN's web pages blocked, no Mac cache, no CricketData key. Only ESPN's JSON feeds, replayed from a real
morning (tests/fixtures/cricket_feed_2026-11-08.json: Afghanistan v Zimbabwe and Bangladesh v West Indies, both Tests on day 3, and a finished WBBL match).
The Test centuries that went missing on 7 November must come through: in the cricket section's standouts and as Stars Of The Night candidates.
Run: .venv/bin/python scripts/test_cricket_feed.py"""
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import bigstuff, cricket, cricketcache, telegram  # noqa: E402
from kickoff.sources import espn, espn_cricket  # noqa: E402

SAVED = json.loads((ROOT / "tests" / "fixtures" / "cricket_feed_2026-11-08.json").read_text())
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:400]}"))
    results.append(ok)


def replay(url, *a, **k):
    if url not in SAVED:
        raise RuntimeError("not saved: " + url)
    return SAVED[url]


def blocked(url):
    raise RuntimeError("ESPN's cricket pages are blocked from GitHub")


summary = next(v for u, v in SAVED.items() if "event=1555123" in u)
card = espn_cricket.parse_summary(summary)
zim = card["scorecard"][0]
taylor = next(b for b in zim["batting"] if b["batsman"]["name"] == "Brendan Taylor")
check("the feed's scorecard: Zimbabwe's 1st innings first, 504 all out in 134.3 overs", zim["inning"] == "Zimbabwe 1st Innings" and zim["espn"]["total"] == {"r": 504, "w": 10, "o": 134.3, "rr": None}, zim["espn"])
check("Brendan Taylor 131 off 168, 14 fours, 4 sixes, out caught", (taylor["r"], taylor["b"], taylor["4s"], taylor["6s"]) == (131, 168, 14, 4) and taylor["dismissal-text"].startswith("c "), taylor)
check("the batters are in batting order and the not-out batter says 'not out'", [b["batsman"]["name"] for b in zim["batting"]][:3] == ["Innocent Kaia", "Ben Curran", "Brendan Taylor"]
      and any(b["dismissal-text"] == "not out" for b in zim["batting"]), [b["batsman"]["name"] for b in zim["batting"]])
check("the bowling is the other side's, with overs, wickets and runs", zim["bowling"] and all(b["o"] for b in zim["bowling"]) and sum(b["w"] for b in zim["bowling"]) <= 10, zim["bowling"][:2])
check("no HTML codes left in a dismissal ('&dagger;' becomes '†')", not any("&" in b["dismissal-text"] for inn in card["scorecard"] for b in inn["batting"]))
check("the state line comes with it", card["status"] == "Afghanistan trail by 102 runs", card["status"])
wbbl = espn_cricket.parse_summary(next(v for u, v in SAVED.items() if "event=1543957" in u))
check("a finished match carries Player of the Match from the feed", wbbl and wbbl["potm"] == [{"name": "Lily Bassingthwaighte", "team": "Brisbane Heat Women"}], wbbl and wbbl["potm"])
table = espn_cricket.parse_standings(next(v for u, v in SAVED.items() if "event=1543957" in u))
check("a league's points table from the feed (WBBL)", table and table[0]["team"] == "SS-W" and table[0]["pts"] == 6 and table[0]["nrr"] == 1.517, table and table[0])
check("no innings in the feed: no card (the backups are tried)", espn_cricket.parse_summary({"header": {"competitions": [{"competitors": []}]}}) is None)

# ---- The whole cricket run, GitHub-style ----
src = espn_cricket.Source(fetch=blocked, fetch_json=replay)
get_card, get_table, get_series = cricketcache.getters({"cards": {}, "tables": {}, "series": {}}, src)
now = datetime(2026, 11, 7, 23, 15, tzinfo=timezone.utc)
got = cricket.run(now, espn.window_start(date(2026, 11, 8)), {}, lambda: ([], 0), lambda i: (_ for _ in ()).throw(RuntimeError("no key")), lambda u: 0,
                  espn_card=get_card, espn_table=get_table, espn_series=get_series, espn_extra=lambda ms: cricket.espn_matches(espn_cricket.Feed(get_json=replay, pause=0)))
text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", got["html"]))
centuries = ["Brendan Taylor", "Brian Bennett", "Towhid Hridoy", "Amir Jangoo", "Sediqullah Atal", "Rahmanullah"]
check("with the pages blocked and no Mac cache, every match still has its scorecard", got["stats"]["missing_cards"] == [] and got["stats"]["checked"] == got["stats"]["picked"], got["stats"])
check("the cricket section shows the full batting cards (Taylor's 131 off 168 in the table)", "Brendan Taylor" in text and "131 168 14 4" in text, text[:300])
perfs = [e for e in got["events"] if e.get("kind") == "perf"]
check("every Test century of the day is a milestone Star candidate: " + ", ".join(centuries),
      all(any(e["text"].startswith(n + " (") and e.get("milestone") for e in perfs) for n in centuries), [e["text"][:40] for e in perfs])
check("Hridoy's 242* is one line, not three (100, 150 and 200 at once)", sum(1 for e in perfs if e["text"].startswith("Towhid Hridoy")) == 1)
check("Hasan Mahmud's six-for is a milestone too", any(e["text"].startswith("Hasan Mahmud (BAN): 6/90") for e in perfs), [e["text"][:40] for e in perfs])
stars = bigstuff.stars(perfs)
check("Stars Of The Night takes the milestones (up to five)", len(stars) == 5 and all(s.get("milestone") for s in stars), [s["text"][:30] for s in stars])
again = cricket.run(now, espn.window_start(date(2026, 11, 8)), got["state"], lambda: ([], 0), lambda i: (_ for _ in ()).throw(RuntimeError("no key")), lambda u: 0,
                    espn_card=get_card, espn_table=get_table, espn_series=get_series, espn_extra=lambda ms: cricket.espn_matches(espn_cricket.Feed(get_json=replay, pause=0)))
check("a milestone is announced once: the next run with the same scores repeats none", not [e for e in again["events"] if e.get("milestone")], [e["text"][:40] for e in again["events"] if e.get("milestone")])

# ---- Never silent ----
dark = espn_cricket.Source(fetch=blocked, fetch_json=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("feed down")))
c2, t2, s2 = cricketcache.getters({"cards": {}, "tables": {}, "series": {}}, dark)
none = cricket.run(now, espn.window_start(date(2026, 11, 8)), {}, lambda: ([], 0), lambda i: (_ for _ in ()).throw(RuntimeError("no key")), lambda u: 0,
                   espn_card=c2, espn_table=t2, espn_series=s2, espn_extra=lambda ms: cricket.espn_matches(espn_cricket.Feed(get_json=replay, pause=0)))
check("no scorecard from anywhere: each match is named as missing", "Afghanistan v Zimbabwe" in none["stats"]["missing_cards"] and "Bangladesh v West Indies" in none["stats"]["missing_cards"], none["stats"]["missing_cards"])
msg = telegram.build_message({"date": "2026-11-08", "headlines": ["a"], "warnings": ["Cricket: no scorecard for Afghanistan v Zimbabwe"]})
check("and D's Telegram message says so", "⚠ Cricket: no scorecard for Afghanistan v Zimbabwe" in msg, msg)
check("a normal morning's message has no warning line", "⚠" not in telegram.build_message({"date": "2026-11-08", "headlines": ["a"]}))
cache_only = cricketcache.getters({"cards": {"espn-1555123": {"built": "x", "scorecard": card["scorecard"]}}, "tables": {}, "series": {}},
                                  espn_cricket.Source(fetch=blocked, fetch_json=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("feed down"))))[0]
check("the order is fixed: the feed first, then the Mac's cache (used when the feed is down)", cache_only({"id": "espn-1555123", "series": "24799", "event": "1555123"})["scorecard"] == card["scorecard"])

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
