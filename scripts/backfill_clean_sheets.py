"""One-off: count this season's clean sheets from the start, so the daily run only has to add new ones.

  python3 scripts/backfill_clean_sheets.py            scan the season so far, save data/state/clean_sheets.json
  python3 scripts/backfill_clean_sheets.py --check    compare our Premier League count with FPL's public numbers

Safe to run again: matches already counted are skipped.
"""
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kickoff import leaders, state  # noqa: E402
from kickoff.http import get_json, safe  # noqa: E402
from kickoff.sources import espn  # noqa: E402


def backfill():
    today = datetime.now(timezone.utc).date()
    start = date(espn.season_year(today), 8, 1)
    cs = state.load("clean_sheets")
    for league, name in espn.LEAGUES.items():
        print(f"{name}: scanning {start} to {today} ...", flush=True)
        matches = safe(f"{name} season results", espn.results_between, league, start, today)
        if matches is None:
            continue
        cs = leaders.count_clean_sheets(cs, league, matches, lambda m, lg=league: espn.get_starting_keepers(lg, m["id"]))
        state.save("clean_sheets", cs)  # save after each league, so a crash loses little
        top = leaders.top_clean_sheets(cs, league)
        print(f"   {len(matches)} matches, {len(cs[league]['matches'])} counted; most clean sheets: "
              + ", ".join(f"{k['name']} {k['cs']}" for k in top), flush=True)


def check():
    cs = state.load("clean_sheets")
    f = get_json("https://fantasy.premierleague.com/api/bootstrap-static/")
    gks = sorted((e for e in f["elements"] if e["element_type"] == 1), key=lambda e: -e["clean_sheets"])[:5]
    ours = sorted(cs.get("eng.1", {}).get("keepers", {}).values(), key=lambda k: -k["cs"])[:5]
    print("FPL top 5 :", ", ".join(f"{e['web_name']} {e['clean_sheets']}" for e in gks))
    print("Our top 5 :", ", ".join(f"{k['name']} {k['cs']}" for k in ours))
    print("Leader agrees:", bool(ours) and ours[0]["cs"] == gks[0]["clean_sheets"])


check() if "--check" in sys.argv else backfill()
