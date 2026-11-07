"""Cricket right now, as the daily run would read it, with ESPN's web pages and the Mac's cache switched off: only the JSON feeds (D, 2026-11-08).
Prints every match the run would show, whether its scorecard came through, and the standouts found. Exits with an error if any match with a score has no card.
No keys, nothing saved. Runs on the Mac and on GitHub (.github/workflows/probe.yml).

  .venv/bin/python scripts/check_cricket_live.py"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import cricket, cricketcache  # noqa: E402
from kickoff.sources import espn, espn_cricket  # noqa: E402


def blocked(url):
    raise RuntimeError("pages off")


now = datetime.now(timezone.utc)
day = now.astimezone(ZoneInfo("Asia/Singapore")).date()
src = espn_cricket.Source(fetch=blocked)
card, table, series = cricketcache.getters({"cards": {}, "tables": {}, "series": {}}, src)
got = cricket.run(now, espn.window_start(day), {}, lambda: ([], 0), lambda i: (_ for _ in ()).throw(RuntimeError("no key")), lambda u: 0,
                  espn_card=card, espn_table=table, espn_series=series, espn_extra=lambda ms: cricket.espn_matches(espn_cricket.Feed()))
missing = got["stats"]["missing_cards"]
print(f"Matches the run would show: {got['stats']['picked']} | scorecards found: {got['stats']['checked']} | missing: {', '.join(missing) or 'none'}")
for e in got["events"]:
    print(("  STAR  " if e.get("milestone") else "  " + e.get("kind", "") + "  ") + e["text"][:140])
standouts = [li for ul in re.findall(r'<ul class="standouts[^"]*">(.*?)</ul>', got["html"], re.S) for li in re.findall(r"<li[^>]*>(.*?)</li>", ul, re.S)]
print(f"Standouts in the cricket section: {len(standouts)}")
for s in standouts[:12]:
    print("  - " + re.sub(r"<[^>]+>", "", s)[:140])
sys.exit(1 if missing else 0)
