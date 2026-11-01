"""Show what the football sources return. Run: python3 scripts/check_football.py [YYYY-MM-DD]
The date is the edition date in Singapore time. Defaults to today."""
import os
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kickoff.http import safe  # noqa: E402
from kickoff.sources import espn  # noqa: E402

day = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else datetime.now(ZoneInfo("Asia/Singapore")).date()
print(f"Edition date: {day}\n")
failed = 0
for league, name in {**espn.LEAGUES, espn.WSL: "WSL"}.items():
    results = safe(f"{name} results", espn.recent_results, league, day)
    table = safe(f"{name} table", espn.get_table, league)
    if results is None or table is None:
        failed += 1
    print(f"== {name}: {'FAILED' if results is None else str(len(results)) + ' result(s)'}")
    for m in results or []:
        print(f"   {m['home']['abbr']} {m['home_score']}-{m['away_score']} {m['away']['abbr']}")
    if table:
        print("   table top 3:", ", ".join(f"{r['rank']}. {r['abbr']} {r['points']}pts" for r in table[:3]), f"({len(table)} teams)")
print(f"\n{'All sources OK' if not failed else str(failed) + ' source(s) failed'}")
