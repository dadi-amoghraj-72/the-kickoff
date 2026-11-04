"""The F1 block: results tables after Qualifying, after the Sprint and after the Race (not practice), with the driver and
constructor standings after each race. Everything is built by code from exact data (no Claude), and a session whose
results are not published yet is retried in later editions instead of being dropped.

Standouts (D's spec): Biggest Mover, Big Moment (early or front-runner retirements), first wins and podiums, and standout qualifying laps."""
import re
from datetime import datetime, timedelta, timezone

from kickoff import render as r

# (key in the schedule, our name, how long after the start the results are normally in)
SESSIONS = (("Qualifying", "qualifying", timedelta(minutes=75)), ("Sprint", "sprint", timedelta(minutes=60)), ("race", "race", timedelta(minutes=150)))
ORDER = {"qualifying": 0, "sprint": 1, "race": 2}
LABEL = {"qualifying": "Qualifying", "sprint": "Sprint", "race": "Race"}
MOVER_PLACES = 4           # places gained from the grid, for a driver to be named Biggest Mover
EARLY_LAPS = 5             # a retirement within this many laps is an early exit
FRONT_GRID = 5             # a retirement from this grid slot or better is worth a line
POLE_MARGIN = 0.300        # seconds: a pole this far clear is called out
LOOKBACK = timedelta(days=6)  # a session whose results never arrive is given up on after this long
TEAM = {"RB F1 Team": "Racing Bulls"}


ABBR = {"Red Bull": "RBR", "Ferrari": "FER", "Mercedes": "MER", "McLaren": "MCL", "Alpine": "ALP", "Racing Bulls": "RB", "Haas": "HAA",
        "Williams": "WIL", "Audi": "AUD", "Cadillac": "CAD", "Aston Martin": "AMR"}


def abbr(name):
    """Three-letter team code for the driver tables, where the full name will not fit a phone beside the +/- column."""
    full = team(name)
    return ABBR.get(full, full[:3].upper())


def short_name(d):
    """'M. Verstappen': first initial and surname. A double given name uses its last part (Andrea Kimi Antonelli is K. Antonelli, as he is
    known). Falls back to the three-letter code if the source sent no names."""
    given, family = (d.get("givenName") or "").split(), d.get("familyName") or ""
    return f"{given[-1][0]}. {family}" if given and family else d.get("code") or family


def heading(race, total):
    """Two lines (D, 2026-11-04): 'Race 19/23' and under it 'Mexico City Grand Prix, Mexico City' (a line break between them)."""
    place = ((race.get("Circuit") or {}).get("Location") or {}).get("locality")
    return f"Race {int(race['round'])}/{total}\n{race['raceName']}" + (f", {place}" if place else "")


def heading_html(text):
    return r.esc(text).replace(chr(10), "<br>")


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
    rounds = max((int(x["round"]) for x in schedule), default=0)
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
                out.append({"id": sid, "season": race["season"], "round": int(race["round"]), "session": name, "race": race, "end": end, "rounds": rounds})
    return sorted(out, key=lambda s: (s["round"], ORDER[s["session"]]))


# ---- Tables --------------------------------------------------------------------------------------

def _gap(row, winner_laps):
    status = row.get("status", "")
    if status == "Finished":
        t = (row.get("Time") or {}).get("time", "")
        return re.sub(r"^(\d+:\d+:\d+)\.\d+$", r"\1", t)  # the winner's race time to the second: the full 2:20:28.772 is too wide for a phone
    behind = re.match(r"\+(\d+) Lap", status)
    if behind:
        return f"+{behind.group(1)} lap" + ("s" if behind.group(1) != "1" else "")
    if status == "Lapped" and winner_laps and row.get("laps"):
        n = winner_laps - int(row["laps"])
        return f"+{n} lap" + ("s" if n != 1 else "") if n > 0 else (row.get("Time") or {}).get("time", "")
    return {"Disqualified": "DSQ", "Did not start": "DNS"}.get(status, "DNF")


def _tight(html, widths, extra=""):
    return r.compact(html, widths, extra)


def classified(x):
    return x.get("status") in ("Finished", "Lapped") or bool(re.match(r"\+\d+ Lap", x.get("status", "")))


def places_gained(x):
    """Places gained from the grid (negative: lost); None for a driver who did not finish, or started from the pit lane."""
    grid = int(x.get("grid") or 0)
    return grid - int(x["position"]) if grid > 0 and classified(x) else None


def moved(x):
    n = places_gained(x)
    return "–" if not n else (f"▲{n}" if n > 0 else f"▼{-n}")


def results_table(caption, rows):
    """Race or sprint: position, driver, places gained, gap to the winner (or why out), points."""
    laps = int(rows[0]["laps"]) if rows and rows[0].get("laps") else 0
    body = [[x["position"], short_name(x["Driver"]), moved(x), _gap(x, laps), f"{int(float(x['points'])):02d}"] for x in rows]
    podium = ["p1", "p2", "p3"] + [""] * (len(body) - 3)          # gold, silver and bronze for the first three (D, 2026-11-04)
    return _tight(r.table(f"{caption} Results", [("P", True), ("Driver", False), ("+/-", True), ("Gap", True), ("Pts", True)], body, row_classes=podium[:len(body)]), (9, 34, 12, 29, 16), " race")


def best_time(row):
    """(session, time) of the last session this driver set a time in: Q3 for the front ten, Q2 or Q1 for those knocked out. A driver
    in Q3 who set no time shows his Q2 time, marked Q2, so the order of the table always makes sense."""
    return next(((k, row[k]) for k in ("Q3", "Q2", "Q1") if row.get(k)), ("", ""))


def qualifying_table(rows):
    body = [[x["position"], short_name(x["Driver"]), *best_time(x)] for x in rows]
    return _tight(r.table("Qualifying Results", [("P", True), ("Driver", False), ("Q", False), ("Time", True)], body, row_classes=["p1"] + [""] * (len(body) - 1)), (12, 44, 16, 28))   # pole in gold (D)


def _plat(v):
    return r.Raw(f'<span class="plat">{r.esc(v)}</span>')


def driver_standings_table(standings, rnd, limit=10, teams=None, decided=False):
    """teams: {driverId: team they drove for in the race just run}. The standings list several teams for a driver who has moved, in
    no order we can rely on, so the race's own result decides; the first listed team is only the fallback. The leader's row is gold, and platinum once the title is decided."""
    rows = (standings or {}).get("DriverStandings") or []
    teams = teams or {}
    body = [[x["position"], short_name(x["Driver"]), abbr(teams.get(x["Driver"]["driverId"]) or (x.get("Constructors") or [{"name": ""}])[0]["name"]), int(float(x["points"]))]
            for x in rows[:limit]]
    if decided and body:
        body[0] = [_plat(v) for v in body[0]]
    classes = ["hl" if i == 0 and not decided else "" for i in range(len(body))]
    return _tight(r.table(f"Drivers' standings: top {min(limit, len(rows))}", [("P", True), ("Driver", False), ("Team", False), ("Pts", True)], body, row_classes=classes), (12, 44, 20, 24)) if body else ""


def constructor_standings_table(standings, rnd, decided=False):
    rows = (standings or {}).get("ConstructorStandings") or []
    body = [[x["position"], team(x["Constructor"]["name"]), int(float(x["points"]))] for x in rows]
    if decided and body:
        body[0] = [_plat(v) for v in body[0]]
    classes = ["hl" if i == 0 and not decided else "" for i in range(len(body))]
    return _tight(r.table("Constructors' standings", [("P", True), ("Team", False), ("Pts", True)], body, row_classes=classes), (12, 60, 28)) if body else ""


# ---- Round-up lines and standouts ----------------------------------------------------------------

def _name(row):
    return row["Driver"]["familyName"]


def seconds(text):
    """'1:34.035' -> 94.035; '+13.078' -> 13.078; anything else None."""
    m = re.fullmatch(r"\+?(?:(\d+):)?(\d+(?:\.\d+)?)", (text or "").strip())
    return int(m.group(1) or 0) * 60 + float(m.group(2)) if m else None


def race_summary(rows):
    """Who won (and from where), the margin and how many did not finish; then, on a second line, the fastest lap."""
    if not rows:
        return ""
    win = rows[0]
    grid = int(win.get("grid") or 0)
    start = "from pole" if grid == 1 else (f"from P{grid} on the grid" if grid > 1 else "from the pit lane")
    out = f"{_full(win)} ({team(win['Constructor']['name'])}) won {start}"
    if len(rows) > 1 and seconds((rows[1].get("Time") or {}).get("time")) is not None and rows[1].get("status") == "Finished":
        out += f", {(rows[1]['Time']['time']).lstrip('+')}s ahead of {_full(rows[1])}"
    out += "."
    out_n = sum(1 for x in rows if x.get("status") not in ("Finished", "Lapped") and not re.match(r"\+\d+ Lap", x.get("status", "")))
    if out_n:
        out += f" {out_n} did not finish."
    fastest = next((x for x in rows if (x.get("FastestLap") or {}).get("rank") == "1"), None)
    if fastest:  # always on a line of its own
        out += f"\nFastest lap: {_full(fastest)}, {fastest['FastestLap']['Time']['time']}."
    return out


def summary_html(text, rows):
    """The race blurb as html: lines apart, and the fastest lap's time in purple, as on the F1 broadcast (D, 2026-11-04)."""
    fastest = next((x for x in rows if (x.get("FastestLap") or {}).get("rank") == "1"), None)
    html = r.esc(text).replace(chr(10), "<br>")
    if fastest:
        t = r.esc(fastest["FastestLap"]["Time"]["time"])
        html = html.replace(f", {t}.", f', <span class="fl">{t}</span>.')
    return html


def quali_summary(rows):
    if not rows:
        return ""
    pole = rows[0]
    out = f"Pole: {_full(pole)} ({team(pole['Constructor']['name'])}), {best_time(pole)[1]}"
    gap = pole_margin(rows)
    if gap is not None:
        out += f", {gap:.3f}s ahead of {_full(rows[1])}"
    return out + "."


def pole_margin(rows):
    """Seconds between pole and second place, from their Q3 laps (None when either did not set one)."""
    if len(rows) < 2:
        return None
    a, b = seconds(rows[0].get("Q3")), seconds(rows[1].get("Q3"))
    return round(b - a, 3) if a is not None and b is not None else None


def _full(row):
    """'Kimi Antonelli', 'Max Verstappen': the given name he is known by (the last of several: Andrea Kimi Antonelli is Kimi) and his surname."""
    given = (row["Driver"].get("givenName") or "").split()
    return f"{given[-1] if given else ''} {row['Driver']['familyName']}".strip()


def biggest_mover(rows):
    """The driver who gained most places from the grid, if it is worth a line."""
    best = max((x for x in rows if (places_gained(x) or 0) >= MOVER_PLACES), key=lambda x: places_gained(x), default=None)
    if not best:
        return []
    return [f"Biggest Mover: {_full(best)} ({team(best['Constructor']['name'])}), P{best['grid']} on the grid to P{best['position']} (▲{places_gained(best)})."]


def big_moments(rows):
    """What the results alone can show: drivers out in the first laps, and a front-row-to-top-five starter who did not finish. The
    source gives no cause (it just says 'Retired'), so none is claimed."""
    winner_laps = int(rows[0]["laps"]) if rows and rows[0].get("laps") else 0
    out = [x for x in rows if not classified(x) and x.get("status") not in ("Disqualified", "Did not start")]
    lines, used = [], set()
    early = {}
    for x in out:
        if int(x.get("laps") or 0) <= EARLY_LAPS:
            early.setdefault(int(x.get("laps") or 0), []).append(x)
    for laps, group in sorted(early.items()):
        names = " and ".join(_name(x) for x in group) if len(group) < 3 else f"{len(group)} drivers"
        teams = {team(x["Constructor"]["name"]) for x in group}
        tail = f" (both {teams.copy().pop()})" if len(group) == 2 and len(teams) == 1 else ""
        when = "on lap 1" if laps == 0 else f"after {laps} lap" + ("s" if laps != 1 else "")
        lines.append(f"Big Moment: {names}{tail} out {when}.")
        used.update(id(x) for x in group)
    for x in out:
        grid = int(x.get("grid") or 0)
        if id(x) not in used and 0 < grid <= FRONT_GRID and winner_laps and int(x.get("laps") or 0) < winner_laps:
            lines.append(f"Big Moment: {_name(x)} ({team(x['Constructor']['name'])}), who started P{grid}, out after {x['laps']} laps.")
    return lines[:2]


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


def _label(text):
    head, sep, rest = text.partition(": ")
    return f"<strong>{r.esc(head)}:</strong> {r.esc(rest)}" if sep and head in ("Biggest Mover", "Big Moment") else r.esc(text)


def _list(items):
    return '<ul class="standouts">' + "".join(f"<li>{_label(i)}</li>" for i in items) + "</ul>" if items else ""


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


def standings_html(ds, cs, rnd, race_rows, schedule=None):
    teams = {x["Driver"]["driverId"]: x["Constructor"]["name"] for x in race_rows}
    dec_d, dec_c = titles_decided(ds, cs, schedule, rnd) if schedule else (False, False)
    return driver_standings_table(ds, rnd, teams=teams, decided=dec_d) + constructor_standings_table(cs, rnd, decided=dec_c)


# ---- The championships: a closing note when a title is decided ------------------------------------

RACE_MAX, SPRINT_MAX = 25, 8            # a driver's most points from a Grand Prix and from a sprint
TEAM_RACE_MAX, TEAM_SPRINT_MAX = 25 + 18, 8 + 7       # a team's: a one-two


def remaining_max(schedule, rnd, race_pts, sprint_pts):
    """The most points anyone can still score after round `rnd`: every later round's race, and its sprint where the schedule has one."""
    return sum(race_pts + (sprint_pts if "Sprint" in x else 0) for x in schedule if int(x["round"]) > rnd)


def titles_decided(ds, cs, schedule, rnd):
    """(drivers' title decided, constructors' title decided) after round `rnd`: the leader's lead over second place is more than the points still on offer (a tie is never called)."""
    def decided(rows, race_pts, sprint_pts):
        return len(rows) >= 2 and float(rows[0]["points"]) - float(rows[1]["points"]) > remaining_max(schedule, rnd, race_pts, sprint_pts)
    return (decided((ds or {}).get("DriverStandings") or [], RACE_MAX, SPRINT_MAX), decided((cs or {}).get("ConstructorStandings") or [], TEAM_RACE_MAX, TEAM_SPRINT_MAX))


def title_notes(ds, cs, schedule, rnd, season, closed=()):
    """([html notes], new closed keys): a note for each title that is mathematically decided after round `rnd` (titles_decided) and has not been said. "Kimi Antonelli (Mercedes) is the 2026
    Drivers' World Champion with 4 races to spare." After the last round no 'to spare'."""
    notes, new = [], []
    left = sum(1 for x in schedule if int(x["round"]) > rnd)
    spare = "" if left == 0 else f" with {left} race{'s' if left != 1 else ''} to spare"
    dec_d, dec_c = titles_decided(ds, cs, schedule, rnd)
    if dec_d and f"{season}-drivers" not in closed:
        d = ds["DriverStandings"][0]
        team_ = d["Constructors"][-1]["name"] if d.get("Constructors") else ""
        notes.append(_full(d) + (f" ({team(team_)})" if team_ else "") + f" is the {season} Drivers' World Champion{spare}.")
        new.append(f"{season}-drivers")
    if dec_c and f"{season}-constructors" not in closed:
        notes.append(f"{team(cs['ConstructorStandings'][0]['Constructor']['name'])} are the {season} Constructors' World Champions{spare}.")
        new.append(f"{season}-constructors")
    return [f'<p class="f1sum">{r.esc(n)}</p>' for n in notes], new


# ---- One session, and the whole block ------------------------------------------------------------

def session_html(due, api, story=None, used=None, capture=None, schedule=None, rows_out=None):
    """(HTML, standings still to come) for one due session, or (None, False) when its results are not published yet. Raises when the source fails.
    story: optional, for Sunday races only: story(race, rows, start, extras) -> (html, usage). Its tokens are added into `used`.
    A failing story is left out; it never costs the tables."""
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
    if rows_out is not None:
        rows_out[(season, rnd, kind)] = rows
    standouts = biggest_mover(rows) + big_moments(rows) + (firsts(rows, api.finishes) if kind == "race" else [])
    html = f'<p class="f1sum">{summary_html(race_summary(rows), rows)}</p>'
    if kind == "race" and story:
        try:
            text, usage = story(due["race"], rows, start_of(due["race"], "race"), standouts)
        except Exception:
            text, usage = "", {"input": 0, "output": 0}
        html += text
        if used is not None:
            used["input"] += usage["input"]
            used["output"] += usage["output"]
    html += results_table(LABEL[kind], rows) + _list(standouts)
    stale = False
    if kind == "race":
        got = fresh_standings(api, season, rnd, due["race"], rows)
        if got:
            html += standings_html(got[0], got[1], rnd, rows, schedule)
            if capture is not None:
                capture[int(rnd)] = got
        else:  # stale or missing: shown in a later edition, once the source has caught up
            stale = True
            html += '<p class="muted">The standings for this round are not up to date at the source yet; they will follow in a later edition.</p>'
    return html, stale


def run(now, window_start, st, api, season="current", story=None):
    """{"html", "state", "stats"}. st: {"reported": [session ids], "pending": {id: iso end}}. A failing or not-yet-published session
    is kept as pending (and mentioned) rather than lost; one failure never stops the others."""
    reported, pending, closed = list(st.get("reported", [])), dict(st.get("pending", {})), list(st.get("closed", []))
    schedule = api.schedule(season)
    got_standings = {}
    due = due_sessions(schedule, now, window_start, reported, pending)
    parts, waiting, failed, shown, queued_now, used = {}, [], 0, 0, set(), {"input": 0, "output": 0}
    race_rows = {}                                         # the race results read this run, for The Big Stuff
    for d in due:
        stale = False
        try:
            html, stale = session_html(d, api, story, used, got_standings, schedule, race_rows)
        except Exception:
            failed += 1
            html = None
        name = d["race"]["raceName"]
        title = heading(d["race"], d["rounds"])
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
        parts.setdefault(d["round"], [title, []])[1].append(html)
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
            parts.setdefault(int(rnd_), [heading(race, max(int(x["round"]) for x in schedule)), []])[1].append(standings_html(got[0], got[1], int(rnd_), rows, schedule))
            got_standings[int(rnd_)] = got
        else:
            waiting.append(f"{race['raceName']} standings")
    for rnd_, got in sorted(got_standings.items()):            # a title decided by this round's standings: said once
        try:
            notes, new_keys = title_notes(got[0], got[1], schedule, rnd_, str(schedule[0]["season"]), closed)
        except Exception:
            notes, new_keys = [], []
        if notes and rnd_ in parts:
            parts[rnd_][1].extend(notes)
            closed += new_keys
    out = "".join(f"<h3>{heading_html(name)}</h3>" + "".join(blocks) for _, (name, blocks) in sorted(parts.items()))
    if waiting:
        out += (f'<p class="muted">Not published by the data source yet, so they will appear in a later edition: {r.esc(", ".join(waiting))}.</p>')
    horizon = now - LOOKBACK
    pending = {k: v for k, v in pending.items() if datetime.fromisoformat(v) >= horizon}
    try:                                                   # for The Big Stuff: each Grand Prix whose race result was shown this morning (always a headline)
        from kickoff import events
        races = [(next(x["raceName"] for x in schedule if x["season"] == s_ and x["round"] == r_), _full(rows[0]), team(rows[0]["Constructor"]["name"]))
                 for (s_, r_, k_), rows in race_rows.items() if k_ == "race" and rows]
        story_events = events.f1(races)
    except Exception:
        story_events = []
    races_in = []
    try:
        races_in = [(rows, next(x["raceName"] for x in schedule if x["season"] == s_ and x["round"] == r_)) for (s_, r_, k_), rows in race_rows.items() if k_ == "race" and rows]
    except Exception:
        pass
    return {"html": out, "state": {"reported": reported[-60:], "pending": pending, "closed": closed[-10:]},
            "stats": {"due": len(due), "shown": shown, "waiting": len(waiting), "failed": failed, "calls": api.calls, "claude_tokens": used}, "events": story_events,
            "young_in": {"f1": races_in}}
