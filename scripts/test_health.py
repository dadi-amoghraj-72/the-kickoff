"""Tests for the morning health check (kickoff/health.py, D 2026-11-08): what should have come through and did not is said in the ping; a good morning adds nothing.
Run: .venv/bin/python scripts/test_health.py"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import cricketcache, health, telegram  # noqa: E402

results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


now = datetime(2026, 11, 7, 23, 20, tzinfo=timezone.utc)
stamp = cricketcache.stamp
good = {"failed": [], "problems": [], "budget": {"mode": "normal"}, "client_used": True, "edition": {"sections": [{"id": "big-stuff"}, {"id": "cricket"}]}}
fresh_cache = {"cards": {}, "tables": {}, "series": {}, "ran": stamp(now - timedelta(minutes=30))}

check("a good morning: nothing to say", health.check(good, now, True, fresh_cache) == [], health.check(good, now, True, fresh_cache))
check("a sport whose source failed is named", health.check({**good, "failed": ["nba"], "problems": ["nba (HTTPError)"]}, now, True, fresh_cache)
      == ["NBA: could not be built today (its data source failed)"], health.check({**good, "failed": ["nba"], "problems": ["nba (HTTPError)"]}, now, True, fresh_cache))
check("a skipped part is named once", health.check({**good, "problems": ["on today: nba"]}, now, True, fresh_cache) == ["Skipped: on today: nba"])
check("a missing cricket scorecard is not said twice (the cricket adapter says it)", health.check({**good, "problems": ["cricket: no scorecard for A v B"]}, now, True, fresh_cache) == [])
check("Claude wanted but the month's budget is used up", health.check({**good, "client_used": False, "budget": {"mode": "plain"}}, now, True, fresh_cache)
      == ["Claude was off: plain notes today (this month's budget is used up)"])
check("Claude wanted but no key", health.check({**good, "client_used": False}, now, True, fresh_cache) == ["Claude was off: plain notes today (no key)"])
check("Claude not wanted (a hand run without it): nothing said", health.check({**good, "client_used": False}, now, False, fresh_cache) == [])
check("Claude in cheaper mode is said", health.check({**good, "budget": {"mode": "cheaper"}}, now, True, fresh_cache) == ["Claude in cheaper mode (most of this month's budget is used)"])
old = {"cards": {"x": {"built": stamp(now - timedelta(days=4))}}, "tables": {}, "series": {}}
check("the Mac's cricket job not run for days: said, with the day it last ran", health.check(good, now, True, old)
      == ["Mac cricket backup has not run since 3 Nov (cricket still comes from ESPN's feed)"], health.check(good, now, True, old))
check("a Mac run with no cricket to collect still counts (its 'ran' stamp)", health.check(good, now, True, {**old, "ran": stamp(now - timedelta(hours=1))}) == [])
check("never run at all is said too", "since it was set up" in health.check(good, now, True, {"cards": {}, "tables": {}, "series": {}})[0])
check("nothing from any sport", health.check({**good, "edition": {"sections": [{"id": "quiet"}]}}, now, True, fresh_cache) == ["Nothing came through from any sport"])
check("the cache file keeps its 'ran' stamp when loaded", cricketcache.load(Path("/nonexistent")) == {"cards": {}, "tables": {}, "series": {}})
tmp = Path(ROOT / "preview" / "_health_test_cache.json")
tmp.parent.mkdir(exist_ok=True)
cricketcache.save({"cards": {}, "tables": {}, "series": {}, "ran": "2026-11-08T22:50:00Z"}, tmp)
check("saved and loaded, 'ran' survives", cricketcache.load(tmp).get("ran") == "2026-11-08T22:50:00Z")
tmp.unlink()
msg = telegram.build_message({"date": "2026-11-08", "headlines": ["a"], "warnings": [f"w{i}" for i in range(6)]})
check("the ping shows up to four warnings, then how many more", "⚠ w3" in msg and "⚠ w4" not in msg and "⚠ and 2 more (see the run log on GitHub)" in msg, msg)
wf = (ROOT / "scripts" / "daily.py").read_text()
check("the real run adds the health lines to the edition before it is saved and the ping is built", wf.index("health.check(") < wf.index("write_text(json.dumps(ed"))

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
