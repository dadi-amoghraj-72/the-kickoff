"""Show why each cricket match from the free CricketData list is picked or left out for today's edition. Prints match names and decisions only, never the key.
Uses 1 to 3 of the day's calls. Run: .venv/bin/python scripts/cricket_debug.py   (or the 'Cricket debug' workflow on GitHub, which has the key)"""
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kickoff import cricket  # noqa: E402
from kickoff.envfile import load_env  # noqa: E402
from kickoff.sources import cricket as src  # noqa: E402
from kickoff.sources import espn  # noqa: E402

load_env()
now = datetime.now(timezone.utc)
day = now.astimezone(ZoneInfo("Asia/Singapore")).date()
ws = espn.window_start(day)
matches, used = src.get_matches()
matches = cricket.normalise(matches)
print(f"now {now:%Y-%m-%d %H:%M} UTC | window starts {ws:%Y-%m-%d %H:%M} UTC | {len(matches)} matches listed | calls used today: {used}\n")
picked = {m["id"] for m in cricket.pick(matches, now, ws)}
for m in sorted(matches, key=lambda x: x.get("dateTimeGMT", "")):
    c = cricket.classify(m)
    why = "PICKED" if m["id"] in picked else "not in scope" if c["kind"] is None else "not started" if not m.get("matchStarted") else "still on" if not m.get("matchEnded") else "ended outside the window"
    ends = ""
    if m.get("matchEnded"):
        ends = f" est. end {cricket.started(m) + cricket.DURATION.get(m.get('matchType'), cricket.timedelta(hours=10)):%m-%d %H:%M}"
    print(f"{m.get('dateTimeGMT', '?')[:16]}  {m.get('matchType', '?'):5} started={m.get('matchStarted')} ended={m.get('matchEnded')}{ends}  {why:24} {m['name'][:90]}")

# ---- ESPN's cricket feed: can we read it from here, and what would be added? ----
from kickoff.sources import espn_cricket  # noqa: E402

try:
    feed = espn_cricket.Feed()
    extra = cricket.espn_extras(matches, feed)
    print(f"\nESPN feed read ({feed.calls} calls): {len(extra)} matches the CricketData list lacks")
    for m in extra:
        scores = " · ".join(cricket.innings_line(x, m['teams']) for x in m.get('score') or [])
        print(f"  {m['dateTimeGMT'][:16]}  ended={m['matchEnded']}  {m['name'][:70]}  | {m['status']} | {scores}")
except Exception as e:  # noqa: BLE001
    print(f"\nESPN feed FAILED: {type(e).__name__}: {str(e)[:200]}")
