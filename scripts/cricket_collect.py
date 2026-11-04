"""Collect the cricket pages GitHub cannot read (scorecards, points tables, series tables) on this Mac and save them in data/cricket_cache.json.

  .venv/bin/python scripts/cricket_collect.py            read the pages and save the cache (nothing is committed)
  .venv/bin/python scripts/cricket_collect.py --push     ... and commit and push data/cricket_cache.json so the daily run on GitHub can use it
  .venv/bin/python scripts/cricket_collect.py --dry-run  show what would be collected, save nothing

To run it every morning at 6:50am Singapore time (a few minutes before the 7:15 edition builds), see scripts/com.thekickoff.cricket.plist for the one command.
The Mac must be on and awake then; if it is not, the edition still goes out, without the batting and bowling cards. Uses 1 to 3 of CricketData's daily calls.
Nothing secret is printed or committed (the cache holds only public scorecards)."""
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import cricket, cricketcache  # noqa: E402
from kickoff.envfile import load_env  # noqa: E402
from kickoff.sources import cricket as src  # noqa: E402
from kickoff.sources import espn, espn_cricket  # noqa: E402

load_env()
now = datetime.now(timezone.utc)
day = now.astimezone(ZoneInfo("Asia/Singapore")).date()
matches, used = src.get_matches()
matches = cricket.normalise(matches)
matches += cricket.espn_extras(matches, espn_cricket.Feed())
picked = cricket.pick(matches, now, espn.window_start(day))
print(f"{now:%Y-%m-%d %H:%M} UTC | {len(picked)} matches for the edition of {day}: " + "; ".join(m["name"].split(",")[0] for m in picked) + f" | CricketData calls used today: {used}")
cache = cricketcache.collect(picked, espn_cricket.Source(), now, cricketcache.load())
print(f"cache now holds {len(cache['cards'])} scorecards, {len(cache['tables'])} points tables, {len(cache['series'])} series tables")
if "--dry-run" in sys.argv:
    sys.exit(0)
cricketcache.save(cache)
print(f"saved {cricketcache.PATH.relative_to(ROOT)}")
if "--push" in sys.argv:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    git("pull", "--rebase", "--autostash")
    git("add", "data/cricket_cache.json")
    done = git("commit", "-m", f"Cricket cache ({day})")
    if done.returncode != 0 and "nothing to commit" in (done.stdout + done.stderr):
        print("nothing new to push")
    else:
        pushed = git("push", "origin", "main")
        print("pushed" if pushed.returncode == 0 else "committed but the push failed: " + pushed.stderr.strip()[:200])
