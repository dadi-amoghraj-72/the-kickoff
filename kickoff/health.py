"""The morning health check (D, 2026-11-08): what should have come through and did not, said in D's Telegram message so nobody has to ask.

Plain rules over what the run already knows, nothing fetched again. A morning with nothing wrong adds nothing to the message. Checked:
  a sport that could not be built at all (its source down), and any part that was skipped (the run's problems list; normally empty)
  Claude: wanted but not used (no key, or the month's budget used up), or the cheaper mode
  the Mac's cricket backup: not run for more than a day (it collects ESPN's scorecard pages at 6:50am; the JSON feed is the main source, so this is a backup warning)
  nothing at all came through from any sport
Cricket's missing scorecards are named by the cricket adapter itself (daily.cricket_go)."""
from datetime import datetime, timedelta, timezone

MAC_STALE = timedelta(hours=30)       # the Mac job runs once a day at 6:50am; a day and a bit without it means a missed morning

NAMES = {"football": "Football", "cricket": "Cricket", "f1": "F1", "tennis": "Tennis", "nfl": "NFL", "nba": "NBA", "mlb": "MLB", "around": "Other Sports"}


def newest_built(cache):
    """When the Mac's cricket job last ran: its 'ran' stamp (written every run, cricket or not), else the newest entry's 'built' stamp; None when neither."""
    stamps = []
    try:
        stamps.append(datetime.strptime(cache["ran"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc))
    except (KeyError, ValueError, TypeError):
        pass
    for kind in ("cards", "tables", "series"):
        for entry in (cache.get(kind) or {}).values():
            try:
                stamps.append(datetime.strptime(entry["built"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc))
            except (KeyError, ValueError, TypeError):
                continue
    return max(stamps) if stamps else None


def check(out, now, use_claude, cache=None):
    """Warnings for the edition (short lines, no '⚠': the message adds it). out: daily.run_day's result; cache: the Mac's cricket cache as loaded, or None to skip."""
    warn = []
    for sid in out.get("failed") or []:
        warn.append(f"{NAMES.get(sid, sid)}: could not be built today (its data source failed)")
    for p in out.get("problems") or []:
        if p.split(" (")[0] in (out.get("failed") or []) or p.startswith("cricket: no scorecard"):
            continue                                       # already said above, or by the cricket adapter
        warn.append(f"Skipped: {p}")
    mode = (out.get("budget") or {}).get("mode")
    if use_claude and not out.get("client_used"):
        warn.append("Claude was off: plain notes today" + (" (this month's budget is used up)" if mode == "plain" else " (no key)"))
    elif use_claude and mode == "cheaper":
        warn.append("Claude in cheaper mode (most of this month's budget is used)")
    if cache is not None:
        last = newest_built(cache)
        if last is None or now - last > MAC_STALE:
            warn.append("Mac cricket backup has not run since " + (f"{last:%-d %b}" if last else "it was set up") + " (cricket still comes from ESPN's feed)")
    sections = [s["id"] for s in (out.get("edition") or {}).get("sections") or []]
    if sections == ["quiet"]:
        warn.append("Nothing came through from any sport")
    return warn
