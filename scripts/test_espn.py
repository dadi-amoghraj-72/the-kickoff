"""Offline tests for the ESPN reader, using saved real responses. Run: python3 scripts/test_espn.py"""
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff.sources import espn  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
load = lambda name: json.loads((FIX / name).read_text())  # noqa: E731
FAKE = {"20261031": load("espn_pl_20261031.json"), "20261101": load("espn_pl_20261101.json"),
        "20261030": {"events": []}}


def fake_get_json(url, params=None, **kw):
    if "standings" in url:
        return load("espn_pl_table.json")
    return FAKE[params["dates"]]


espn.get_json = fake_get_json
results = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {detail}"))
    results.append(ok)


sat = espn.get_matches_on("eng.1", date(2026, 10, 31))
check("parses all 8 Saturday matches", len(sat) == 8, len(sat))
che = next(m for m in sat if m["home"]["abbr"] == "CHE")
check("score and teams", (che["home"]["name"], che["home_score"], che["away_score"]) == ("Chelsea", 2, 0), che)
check("goals have scorer, minute and side",
      len(che["goals"]) == 2 and all(g["player"] and g["minute"] and g["side"] == "home" for g in che["goals"]), che["goals"])
check("a red card is picked up somewhere", any(m["reds"] for m in sat))
check("a drawn match parses", any(m["home_score"] == m["away_score"] for m in sat))

# Sunday's edition (Singapore date 1 Nov) covers Saturday's games
sun = espn.recent_results("eng.1", date(2026, 11, 1))
check("Sunday edition holds all 8 Saturday results", len(sun) == 8, len(sun))
# Monday's edition must not repeat Saturday, and must skip a match still in progress
mon = espn.recent_results("eng.1", date(2026, 11, 2))
check("Monday edition leaves out Saturday and the unfinished Liverpool match", len(mon) == 0, [m["id"] for m in mon])
check("results come out in kick-off order", [m["kickoff"] for m in sun] == sorted(m["kickoff"] for m in sun))

table = espn.get_table("eng.1")
check("table has 20 teams, rank 1 first", len(table) == 20 and table[0]["rank"] == 1, len(table))
check("table row fields", {"team", "played", "gd", "points", "zone"} <= set(table[0]), table[0].keys())
check("points equal 3 x wins + draws", all(r["points"] == 3 * r["won"] + r["drawn"] for r in table[:5]), table[0])

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
