"""The F1 block: results tables after Qualifying, after the Sprint and after the Race (not practice), with the driver and
constructor standings after each race. Everything is built by code from exact data (no Claude), and a session whose
results are not published yet is retried in later editions instead of being dropped.

Standouts (D's spec): big recoveries through the field, first wins and podiums, and standout qualifying laps."""
import re
from datetime import datetime, timedelta, timezone

from kickoff import render as r

# (key in the schedule, our name, how long after the start the results are normally in)
SESSIONS = (("Qualifying", "qualifying", timedelta(minutes=75)), ("Sprint", "sprint", timedelta(minutes=60)), ("race", "race", timedelta(minutes=150)))
ORDER = {"qualifying": 0, "sprint": 1, "race": 2}
LABEL = {"qualifying": "Qualifying", "sprint": "Sprint", "race": "Race"}
RECOVERY_PLACES = 8        # places gained from the grid, for a finish in the points
POLE_MARGIN = 0.300        # seconds: a pole this far clear is called out
LOOKBACK = timedelta(days=6)  # a session whose results never arrive is given up on after this long
TEAM = {"RB F1 Team": "Racing Bulls"}


def team(name):
    name = TEAM.get(name, name)
    return re.sub(r"\s+F1 Team$", "", name)


def start_of(race, key):
    """When a session starts (UTC), or None. The race itself is stored at the top of the schedule entry."""
    slot = race if key == "race" else race.get(key)
    if not slot or not slot.get("date"):
        return None
    return datetime.fromisoformat(f"{slot['date']}T{(slot.get('time') or '12:00:00Z').replace('Z', '+00:00')}")


def due_sessions(schedule, now, window_start, reported=(), pending=()):
    """Sessions whose results should be in this edition: ended inside the window, or still waiting from an earlier edition."""
    out = []
    for race in schedule:
        for key, name, took in SESSIONS:
            begin = start_of(race, key)
            if begin is None:
                continue
            end = begin + took
            sid = f"{race['season']}-{race['round']}-{name}"
            if sid in set(reported) or end > now:
                continue
            if end >= window_start or (sid in set(pending) and now - end <= LOOKBACK):
                out.append({"id": sid, "season": race["season"], "round": int(race["round"]), "session": name, "race": race, "end": end})
    return sorted(out, key=lambda s: (s["round"], ORDER[s["session"]]))


# ---- Tables --------------------------------------------------------------------------------------

def _gap(row, winner_laps):
    status = row.get("status", "")
    if status == "Finished":
        return (row.get("Time") or {}).get("time", "")
    behind = re.match(r"\+(\d+) Lap", status)
    if behind:
        return f"+{behind.group(1)} lap" + ("s" if behind.group(1) != "1" else "")
    if status == "Lapped" and winner_laps and row.get("laps"):
        n = winner_laps - int(row["laps"])
        return f"+{n} lap" + ("s" if n != 1 else "") if n > 0 else (row.get("Time") or {}).get("time", "")
    return {"Disqualified": "DSQ", "Did not start": "DNS"}.get(status, "DNF")


def _tight(html):
    """The compact table style (shared with the cricket points tables) so a phone shows every column."""
    return f'<div class="pts">{html}</div>'


def results_table(caption, rows):
    """Race or sprint: position, driver code, team, gap to the winner (or why out), points."""
    laps = int(rows[0]["laps"]) if rows and rows[0].get("laps") else 0
    body = [[x["position"], x["Driver"]["code"], team(x["Constructor"]["name"]), _gap(x, laps), int(float(x["points"]))] for x in rows]
    return _tight(r.table(caption, [("P", True), ("Driver", False), ("Team", False), ("Gap", True), ("Pts", True)], body))


def best_time(row):
    """(session, time) of the last session this driver set a time in: Q3 for the front ten, Q2 or Q1 for those knocked out. A driver
    in Q3 who set no time shows his Q2 time, marked Q2, so the order of the table always makes sense."""
    return next(((k, row[k]) for k in ("Q3", "Q2", "Q1") if row.get(k)), ("", ""))


def qualifying_table(rows):
    body = [[x["position"], x["Driver"]["code"], team(x["Constructor"]["name"]), *best_time(x)] for x in rows]
    return _tight(r.table("Qualifying", [("P", True), ("Driver", False), ("Team", False), ("Q", False), ("Time", True)], body))


def driver_standings_table(standings, rnd, limit=10, teams=None):
    """teams: {driverId: team they drove for in the race just run}. The standings list several teams for a driver who has moved, in
    no order we can rely on, so the race's own result decides; the first listed team is only the fallback."""
    rows = (standings or {}).get("DriverStandings") or []
    teams = teams or {}
    body = [[x["position"], x["Driver"]["code"], team(teams.get(x["Driver"]["driverId"]) or (x.get("Constructors") or [{"name": ""}])[0]["name"]), int(float(x["points"]))]
            for x in rows[:limit]]
    return _tight(r.table(f"Drivers' standings after round {rnd}: top {min(limit, len(rows))}", [("P", True), ("Driver", False), ("Team", False), ("Pts", True)], body)) if body else ""


def constructor_standings_table(standings, rnd):
    rows = (standings or {}).get("ConstructorStandings") or []
    body = [[x["position"], team(x["Constructor"]["name"]), int(float(x["points"]))] for x in rows]
    return _tight(r.table(f"Constructors' standings after round {rnd}", [("P", True), ("Team", False), ("Pts", True)], body)) if body else ""


# ---- Round-up lines and standouts ----------------------------------------------------------------

def _name(row):
    return row["Driver"]["familyName"]


def seconds(text):
    """'1:34.035' -> 94.035; '+13.078' -> 13.078; anything else None."""
    m = re.fullmatch(r"\+?(?:(\d+):)?(\d+(?:\.\d+)?)", (text or "").strip())
    return int(m.group(1) or 0) * 60 + float(m.group(2)) if m else None


def race_summary(rows):
    """One factual line: who won (and from where), the margin, the fastest lap, how many did not finish."""
    if not rows:
        return ""
    win = rows[0]
    grid = int(win.get("grid") or 0)
    start = "from pole" if grid == 1 else (f"from P{grid} on the grid" if grid > 1 else "from the pit lane")
    out = f"{_name(win)} ({team(win['Constructor']['name'])}) won {start}"
    if len(rows) > 1 and seconds((rows[1].get("Time") or {}).get("time")) is not None and rows[1].get("status") == "Finished":
        out += f", {(rows[1]['Time']['time']).lstrip('+')}s ahead of {_name(rows[1])}"
    out += "."
    fastest = next((x for x in rows if (x.get("FastestLap") or {}).get("rank") == "1"), None)
    if fastest:
        out += f" Fastest lap: {_name(fastest)}, {fastest['FastestLap']['Time']['time']}."
    out_n = sum(1 for x in rows if x.get("status") not in ("Finished", "Lapped") and not re.match(r"\+\d+ Lap", x.get("status", "")))
    if out_n:
        out += f" {out_n} did not finish."
    return out


def quali_summary(rows):
    if not rows:
        return ""
    pole = rows[0]
    out = f"Pole: {_name(pole)} ({team(pole['Constructor']['name'])}), {best_time(pole)[1]}"
    gap = pole_margin(rows)
    if gap is not None:
        out += f", {gap:.3f}s ahead of {_name(rows[1])}"
    return out + "."


def pole_margin(rows):
    """Seconds between pole and second place, from their Q3 laps (None when either did not set one)."""
    if len(rows) < 2:
        return None
    a, b = seconds(rows[0].get("Q3")), seconds(rows[1].get("Q3"))
    return round(b - a, 3) if a is not None and b is not None else None


def recoveries(rows):
    out = []
    for x in rows:
        grid, pos = int(x.get("grid") or 0), int(x["position"])
        if grid > 0 and pos <= 10 and grid - pos >= RECOVERY_PLACES and x.get("status") in ("Finished", "Lapped"):
            out.append(f"{_name(x)} ({team(x['Constructor']['name'])}) came through the field: P{grid} on the grid to P{pos}, {grid - pos} places gained.")
    return out


def firsts(rows, finishes):
    """First career win, or first career podium, for the top three. finishes(driver_id, position) -> career count including this race.
    Starts with the count for the driver's own position: more than one means an earlier podium, so no more calls are needed."""
    out = []
    for x in rows[:3]:
        pos, did = int(x["position"]), x["Driver"]["driverId"]
        here = finishes(did, pos)
        if here != 1:
            continue
        if pos == 1:
            out.append(f"{_name(x)} ({team(x['Constructor']['name'])}): first Grand Prix win.")
        elif sum(finishes(did, p) for p in (1, 2, 3) if p != pos) == 0:
            out.append(f"{_name(x)} ({team(x['Constructor']['name'])}): first podium finish.")
    return out


def quali_standouts(rows, poles):
    out = []
    gap = pole_margin(rows)
    if gap is not None and gap >= POLE_MARGIN:
        out.append(f"{_name(rows[0])} took pole by {gap:.3f}s over {_name(rows[1])}: a dominant lap.")
    if rows and poles(rows[0]["Driver"]["driverId"]) == 1:
        out.append(f"{_name(rows[0])} ({team(rows[0]['Constructor']['name'])}): first pole position.")
    return out


def _list(items):
    return '<ul class="standouts">' + "".join(f"<li>{r.esc(i)}</li>" for i in items) + "</ul>" if items else ""


def standings_match(ds, prev, *result_sets):
    """True when the standings after a round are really that round's: every driver's points have risen by exactly what he scored in
    the race (and the sprint, on a sprint weekend). The API sometimes labels the new round while still holding last round's totals."""
    if not ds or not prev:
        return False
    earned = {}
    for rows in result_sets:
        for x in rows or []:
            earned[x["Driver"]["driverId"]] = earned.get(x["Driver"]["driverId"], 0) + float(x["points"])
    before = {x["Driver"]["driverId"]: float(x["points"]) for x in prev.get("DriverStandings") or []}
    rows = ds.get("DriverStandings") or []
    return bool(rows) and all(round(float(x["points"]) - before.get(x["Driver"]["driverId"], 0), 3) == round(earned.get(x["Driver"]["driverId"], 0), 3) for x in rows)


def fresh_standings(api, season, rnd, race, race_rows, sprint_rows=None):
    """(driver standings, constructor standings) once they are verified to be this round's, else None."""
    ds = api.driver_standings(season, rnd)
    if not ds or str(ds.get("round")) != str(rnd):
        return None
    if "Sprint" in race and sprint_rows is None:
        sprint_rows = ((api.sprint(season, rnd)) or {}).get("SprintResults")
    if rnd > 1 and not standings_match(ds, api.driver_standings(season, rnd - 1), race_rows, sprint_rows):
        return None
    cs = api.constructor_standings(season, rnd)
    return ds, (cs if cs and str(cs.get("round")) == str(rnd) else None)


def standings_html(ds, cs, rnd, race_rows):
    teams = {x["Driver"]["driverId"]: x["Constructor"]["name"] for x in race_rows}
    return driver_standings_table(ds, rnd, teams=teams) + constructor_standings_table(cs, rnd)


# ---- One session, and the whole block ------------------------------------------------------------

def session_html(due, api):
    """(HTML, standings still to come) for one due session, or (None, False) when its results are not published yet. Raises when the source fails."""
    season, rnd, kind = due["season"], due["round"], due["session"]
    if kind == "qualifying":
        data = api.qualifying(season, rnd)
        rows = (data or {}).get("QualifyingResults")
        if not rows:
            return None, False
        return (f'<p class="f1sum">{r.esc(quali_summary(rows))}</p>' + qualifying_table(rows)
                + _list(quali_standouts(rows, api.poles))), False
    data = api.sprint(season, rnd) if kind == "sprint" else api.results(season, rnd)
    rows = (data or {}).get("SprintResults" if kind == "sprint" else "Results")
    if not rows:
        return None, False
    html = f'<p class="f1sum">{r.esc(race_summary(rows))}</p>' + results_table(LABEL[kind], rows)
    html += _list(recoveries(rows) + (firsts(rows, api.finishes) if kind == "race" else []))
    stale = False
    if kind == "race":
        got = fresh_standings(api, season, rnd, due["race"], rows)
        if got:
            html += standings_html(got[0], got[1], rnd, rows)
        else:  # stale or missing: shown in a later edition, once the source has caught up
            stale = True
            html += '<p class="muted">The standings for this round are not up to date at the source yet; they will follow in a later edition.</p>'
    return html, stale


def run(now, window_start, st, api, season="current"):
    """{"html", "state", "stats"}. st: {"reported": [session ids], "pending": {id: iso end}}. A failing or not-yet-published session
    is kept as pending (and mentioned) rather than lost; one failure never stops the others."""
    reported, pending = list(st.get("reported", [])), dict(st.get("pending", {}))
    schedule = api.schedule(season)
    due = due_sessions(schedule, now, window_start, reported, pending)
    parts, waiting, failed, shown, queued_now = {}, [], 0, 0, set()
    for d in due:
        stale = False
        try:
            html, stale = session_html(d, api)
        except Exception:
            failed += 1
            html = None
        name = d["race"]["raceName"]
        if html is None:
            pending.setdefault(d["id"], d["end"].isoformat())
            waiting.append(f"{name} {LABEL[d['session']].lower()}")
            continue
        pending.pop(d["id"], None)
        reported.append(d["id"])
        if stale:
            pending[f"{d['season']}-{d['round']}-standings"] = d["end"].isoformat()
            queued_now.add(f"{d['season']}-{d['round']}-standings")
        shown += 1
        parts.setdefault(d["round"], [name, []])[1].append(html)
    for sid in sorted(k for k in pending if k.endswith("-standings") and k not in reported):  # standings held back from an earlier edition
        season_, rnd_, _ = sid.split("-")
        race = next((x for x in schedule if x["season"] == season_ and x["round"] == rnd_), None)
        if not race or sid in queued_now:
            continue
        try:
            rows = ((api.results(season_, rnd_)) or {}).get("Results")
            got = fresh_standings(api, season_, int(rnd_), race, rows) if rows else None
        except Exception:
            got = None
        if got:
            pending.pop(sid)
            reported.append(sid)
            shown += 1
            parts.setdefault(int(rnd_), [race["raceName"], []])[1].append(standings_html(got[0], got[1], int(rnd_), rows))
        else:
            waiting.append(f"{race['raceName']} standings")
    out = "".join(f"<h3>{r.esc(name)}</h3>" + "".join(blocks) for _, (name, blocks) in sorted(parts.items()))
    if waiting:
        out += (f'<p class="muted">Not published by the data source yet, so they will appear in a later edition: {r.esc(", ".join(waiting))}.</p>')
    horizon = now - LOOKBACK
    pending = {k: v for k, v in pending.items() if datetime.fromisoformat(v) >= horizon}
    return {"html": out, "state": {"reported": reported[-60:], "pending": pending},
            "stats": {"due": len(due), "shown": shown, "waiting": len(waiting), "failed": failed, "calls": api.calls}}
