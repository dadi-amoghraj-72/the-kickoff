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
print(f"now {now:%Y-%m-%d %H:%M} UTC | window starts {ws:%Y-%m-%d %H:%M} UTC | {len(matches)} matches listed | calls used today: {used}\n")
picked = {m["id"] for m in cricket.pick(matches, now, ws)}
for m in sorted(matches, key=lambda x: x.get("dateTimeGMT", "")):
    c = cricket.classify(m)
    why = "PICKED" if m["id"] in picked else "not in scope" if c["kind"] is None else "not started" if not m.get("matchStarted") else "still on" if not m.get("matchEnded") else "ended outside the window"
    ends = ""
    if m.get("matchEnded"):
        ends = f" est. end {cricket.started(m) + cricket.DURATION.get(m['matchType'], cricket.timedelta(hours=10)):%m-%d %H:%M}"
    print(f"{m.get('dateTimeGMT', '?')[:16]}  {m.get('matchType', '?'):5} started={m.get('matchStarted')} ended={m.get('matchEnded')}{ends}  {why:24} {m['name'][:90]}")
