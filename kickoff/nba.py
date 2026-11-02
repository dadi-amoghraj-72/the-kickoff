"""NBA: every game finished since the last edition, in two tiers (games with a tracked player first, with the star's line and a one-line story,
then every other game as one compact line), ranked standouts and, on Tuesdays, the conference standings. All by code from exact data, so no
Claude cost.

Which games are new is decided by the state ({"reported": [game ids]}), not the clock, so nothing is lost or shown twice. Most NBA games end
after the 8am Singapore edition, so a result usually lands in the next day's edition.
Tracked players are followed by ESPN player id (so a trade changes nothing). D's list stays for good; anyone else who has three standout
games in 30 days joins automatically and drops off after eight weeks without a standout."""
from datetime import timedelta
from zoneinfo import ZoneInfo

from kickoff import render as r
from kickoff.nfl import DOG, HOME_SVG, dog_of, utc

ET = ZoneInfo("America/New_York")
LOOKBACK = timedelta(hours=60)             # unreported finished games older than this are ignored (a first run must not dump a month)
TRACKED = {  # D's list (SPEC.md, Source: NBA.com 2026-27 season previews): ESPN id -> name
    "5104157": "Victor Wembanyama", "4278073": "Shai Gilgeous-Alexander", "3112335": "Nikola Jokić", "3945274": "Luka Dončić",
    "3934672": "Jalen Brunson", "3136195": "Karl-Anthony Towns", "3032977": "Giannis Antetokounmpo", "1966": "LeBron James",
    "3059318": "Joel Embiid", "3917376": "Jaylen Brown", "3908809": "Donovan Mitchell", "3992": "James Harden", "3975": "Stephen Curry",
    "3202": "Kevin Durant", "4594268": "Anthony Edwards", "4065648": "Jayson Tatum", "4279888": "Ja Morant", "6606": "Damian Lillard",
    "4277905": "Trae Young", "6583": "Anthony Davis", "4396993": "Tyrese Haliburton", "4395628": "Zion Williamson",
    "5041939": "Cooper Flagg", "4432166": "Cade Cunningham"}
WATCHED = ("1966", "3992")                 # LeBron James and James Harden: always a line (even when they did not play) and a career milestone watch
WATCH_TEAMS = {"1966": "PHI", "3992": "CLE"}   # where they play at the start; the state keeps the latest team, so a trade is followed
POINTS, BIG_REB, BLOCKS, STEALS = 40, 20, 5, 5   # standout thresholds
AUTO_HITS, AUTO_DAYS, AUTO_DROP_DAYS = 3, 30, 56  # three standouts in 30 days joins; eight weeks without one drops
MILESTONE_PTS, MILESTONE_AST = 500, 250    # a career-total milestone line shows when the next thousand is within this many
CLUTCH_SECONDS = 5.0                       # a go-ahead score in the last five seconds of the fourth quarter or overtime is a game-winner
COMEBACK, ROUT, CLOSE = 15, 25, 3
MAX_STANDOUTS = 5
TAGGED = ("triple-double", "20-20 game")  # kinds worth naming in a standout line; the points, blocks and steals show in the stat line itself


# ---- Games ----------------------------------------------------------------------------------------

def parse_game(e):
    """A game as plain data. status is 'final', 'live', 'scheduled' or 'other'."""
    c, t = e["competitions"][0], e["status"]["type"]
    status = "final" if t["name"] == "STATUS_FINAL" else {"in": "live", "pre": "scheduled"}.get(t["state"], "other")
    sides = {x["homeAway"]: x for x in c["competitors"]}
    side = lambda x: {"id": x["team"]["id"], "abbr": x["team"]["abbreviation"], "name": x["team"]["displayName"], "short": x["team"]["shortDisplayName"],  # noqa: E731
                      "score": int(x["score"]) if status == "final" and str(x.get("score", "")).isdigit() else None,
                      "record": next((rec["summary"] for rec in x.get("records", []) if rec.get("type", rec.get("name")) in ("total", "overall")), "")}
    return {"id": e["id"], "date": utc(e["date"]), "status": status, "ot": status == "final" and (e["status"].get("period") or 0) > 4,
            "home": side(sides["home"]), "away": side(sides["away"])}


def winner(g):
    a, h = g["away"]["score"], g["home"]["score"]
    return None if a == h else ("away" if a > h else "home")


def day_of(g):
    return g["date"].astimezone(ET).date()


def underdog_win(g):
    return g["status"] == "final" and bool(g.get("dog")) and winner(g) == g["dog"]


def seconds(clock):
    """'47.6' -> 47.6, '1:07' -> 67."""
    if ":" in clock:
        m, s = clock.split(":")
        return int(m) * 60 + float(s)
    return float(clock)


def deciding_play(g, box):
    """The scoring play after which the winner led for good, when it came in the last CLUTCH_SECONDS of regulation or overtime; else None."""
    w = winner(g)
    if not w or not box:
        return None
    sign = 1 if w == "home" else -1
    prev = 0
    flip = None
    for p in box["plays"]:
        diff = sign * (p["home"] - p["away"])
        if diff > 0 and prev <= 0:
            flip = p
        prev = diff
    if flip and flip["period"] >= 4 and seconds(flip["clock"]) <= CLUTCH_SECONDS:
        return flip
    return None


def biggest_deficit(g, box):
    """The most points the winner ever trailed by."""
    w = winner(g)
    if not w or not box:
        return 0
    sign = 1 if w == "home" else -1
    return max([0] + [-sign * (p["home"] - p["away"]) for p in box["plays"]])


# ---- Players ----------------------------------------------------------------------------------------

def num(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def players_of(box, game):
    """Everyone in a box score as plain data; `dnp` is true for anyone who did not play."""
    out = []
    for t in box["players"]:
        opp = game["away"] if t["team"] == game["home"]["abbr"] else game["home"]
        mine = game["home"] if t["team"] == game["home"]["abbr"] else game["away"]
        for a in t["athletes"]:
            d = dict(zip(t["labels"], a["stats"]))
            played = not a["dnp"] and bool(a["stats"]) and num(d.get("MIN")) > 0
            out.append({"id": a["id"], "name": a["name"], "team": t["team"], "opp": opp, "mine": mine, "game": game["id"], "dnp": not played,
                        "reason": (a.get("reason") or "").lower().capitalize(), "starter": a["starter"],
                        **{k: num(d.get(k)) for k in ("MIN", "PTS", "REB", "AST", "STL", "BLK", "TO")},
                        "fg": d.get("FG", ""), "tp": d.get("3PT", ""), "ft": d.get("FT", "")})
    return out


def doubles(p):
    return sum(1 for k in ("PTS", "REB", "AST", "STL", "BLK") if p[k] >= 10)


def kinds_of(p, deciding_ids=()):
    """Why a performance is a standout: a list of short tags, empty when it is not one."""
    if p["dnp"]:
        return []
    k = []
    if p["PTS"] >= POINTS:
        k.append(f"{POINTS}-point game")
    if doubles(p) >= 3:
        k.append("triple-double")
    if p["PTS"] >= BIG_REB and p["REB"] >= BIG_REB:
        k.append("20-20 game")
    if p["BLK"] >= BLOCKS:
        k.append(f"{p['BLK']} blocks")
    if p["STL"] >= STEALS:
        k.append(f"{p['STL']} steals")
    if p["id"] in deciding_ids:
        k.append("game-winner")
    return k


def weight(p, kinds):
    return p["PTS"] + 1.2 * p["REB"] + 1.5 * p["AST"] + 3 * p["STL"] + 3 * p["BLK"] + 8 * len(kinds)


def line(p, extras=True):
    """'43 pts, 7 reb, 4 ast, 6 blk'; steals and blocks only when they are 2 or more."""
    bits = [f"{p['PTS']} pts", f"{p['REB']} reb", f"{p['AST']} ast"]
    if extras:
        bits += [f"{p[k]} {lab}" for k, lab in (("STL", "stl"), ("BLK", "blk")) if p[k] >= 2]
    return ", ".join(bits)


def result_of(p, games):
    """'121-111 win over Minnesota' from the player's side."""
    g = games[p["game"]]
    mine, opp = p["mine"]["score"], p["opp"]["score"]
    return f"{max(mine, opp)}-{min(mine, opp)} {'win over' if mine > opp else 'loss to'} {p['opp']['short']}" + (" in overtime" if g["ot"] else "")


def standout_text(p, kinds, games, plays):
    text = f"{p['name']} ({p['team']}): {line(p)}"
    if "game-winner" in kinds:
        pl = plays[p["game"]]
        text += f", the game-winner with {pl['clock']}s left" if ":" not in pl["clock"] else f", the game-winner with {pl['clock']} left"
    elif [k for k in kinds if k in TAGGED]:
        text += f" ({', '.join(k for k in kinds if k in TAGGED)})"
    return f"{text}; {result_of(p, games)}"


def standouts(players, games, boxes, limit=MAX_STANDOUTS):
    """The ranked standout lines, best first, and the hits as [(player id, game id)] for the auto-join count."""
    plays, deciders = {}, {}
    for gid, g in games.items():
        pl = deciding_play(g, boxes.get(gid))
        if pl:
            plays[gid] = pl
            deciders[gid] = pl.get("athlete")
    found = []
    for p in players:
        kinds = kinds_of(p, {deciders[p["game"]]} if p["game"] in deciders and deciders[p["game"]] else ())
        if kinds:
            found.append((weight(p, kinds), p, kinds))
    found.sort(key=lambda x: (-x[0], x[1]["name"]))
    texts = [standout_text(p, k, games, plays) for _, p, k in found[:limit]]
    return texts, [(p["id"], p["game"]) for _, p, _ in found]


def update_tracking(st, hits, games, names, day):
    """Auto-join and drop-off. hits: [(player id, game id)] for this run. Returns the tracked ids and writes st["auto"] / st["hits"]."""
    auto, record = dict(st.get("auto", {})), {k: list(v) for k, v in st.get("hits", {}).items()}
    today = day.isoformat()
    for pid, gid in hits:
        if [gid, today] not in record.get(pid, []) and gid not in [h[0] for h in record.get(pid, [])]:
            record.setdefault(pid, []).append([gid, today])
        if pid in auto:
            auto[pid]["last"] = today
    cutoff = (day - timedelta(days=AUTO_DAYS)).isoformat()
    for pid in list(record):
        record[pid] = [h for h in record[pid] if h[1] >= cutoff]
        if not record[pid]:
            del record[pid]
    for pid, hs in record.items():
        if pid not in TRACKED and pid not in auto and len(hs) >= AUTO_HITS:
            auto[pid] = {"name": names.get(pid, pid), "last": today}
    drop = (day - timedelta(days=AUTO_DROP_DAYS)).isoformat()
    auto = {k: v for k, v in auto.items() if v["last"] >= drop}
    st["auto"], st["hits"] = auto, record
    return set(TRACKED) | set(auto)


# ---- Stories and milestones ---------------------------------------------------------------------

def story(g, box):
    """One factual sentence about a game."""
    w = winner(g)
    win, lose = g[w], g["away" if w == "home" else "home"]
    margin = win["score"] - lose["score"]
    pl = deciding_play(g, box)
    back = biggest_deficit(g, box)
    if pl:
        clock = pl["clock"] + "s" if ":" not in pl["clock"] else pl["clock"]
        what = "free throw" if "free throw" in pl["text"] else "three" if "three" in pl["text"] else "basket"
        return f"{win['short']} took the lead for good with a {what} in the last {clock}" + (", after overtime" if g["ot"] else "") + "."
    if back >= COMEBACK:
        return f"{win['short']} came back from {back} down" + (" to win in overtime" if g["ot"] else "") + "."
    if g["ot"]:
        return f"{win['short']} won in overtime, {win['score']}-{lose['score']}."
    if margin <= CLOSE:
        return f"{win['short']} held on by {margin}."
    if margin >= ROUT:
        return f"{win['short']} ran away with it by {margin}."
    return f"{win['short']} won by {margin}."


def milestone(career, pid):
    """'Career: 43,522 pts (478 to 44,000)' for the two watched players, from ESPN's career totals; the distance to the next thousand shows
    only when it is close (500 points, 250 assists)."""
    if not career:
        return ""
    parts = []
    for key, label, near in (("PTS", "pts", MILESTONE_PTS), ("AST", "ast", MILESTONE_AST)):
        have = career.get(key, 0)
        nxt = -(-have // 1000) * 1000
        if key == "PTS" or 0 < nxt - have <= near:
            parts.append(f"{have:,} {label}" + (f" ({nxt - have:,} to {nxt:,})" if 0 < nxt - have <= near else ""))
    return "Career: " + ", ".join(parts)


# ---- Rendering ----------------------------------------------------------------------------------

def day_label(d):
    return f"{d:%a} {d.day} {d:%b}"


def _team_rows(g, w, ot):
    rows = []
    for side in ("away", "home"):
        t = g[side]
        mark = f" {HOME_SVG}" if side == "home" else ""
        rec = f' <span class="rec">{r.esc(t["record"])}</span>' if t["record"] else ""
        star = DOG if side == w and underdog_win(g) else ""
        tag = "OT" if side == "away" and ot else ""
        cls = " ".join(x for x in (side[0], "w" if w == side else "") if x)
        rows.append(f'<tr class="{cls}"><td class="tm">{r.esc(t["name"])}{star}{mark}{rec}</td><td class="sc">{t["score"]}</td><td class="ot">{tag}</td></tr>')
    return rows


def star_html(items, many_days, played, total, dogs):
    """items: [(game, [player lines], story)] in order. One table: title row with the counts, then per game the two teams, the stars' lines and the story."""
    rows, prev = [], None
    for g, lines, text in items:
        if many_days and day_of(g) != prev:
            rows.append(f'<tr class="day"><td colspan="3">{r.esc(day_label(day_of(g)))}</td></tr>')
        prev = day_of(g)
        rows += _team_rows(g, winner(g), g["ot"])
        notes = "".join(f'<div class="pl">{r.esc(x)}</div>' for x in lines) + f'<div class="story">{r.esc(text)}</div>'
        rows.append(f'<tr class="note"><td colspan="3">{notes}</td></tr>')
    sub = f'<span class="prog">{played} of {total} games' + (f' · {DOG} {dogs} underdog win{"s" if dogs != 1 else ""}' if dogs else "") + "</span>"
    return (f'<div class="nflsb"><table><colgroup><col style="width:75%"><col style="width:12%"><col style="width:13%"></colgroup>'
            f'<thead><tr><th class="tt" colspan="3">Star Games{sub}</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def other_html(games, many_days, title="Other Games", dog_note=""):
    """One compact line per game: away team, score, home team (house icon), the winner in bold."""
    rows, prev = [], None
    for g in games:
        if many_days and day_of(g) != prev:
            rows.append(f'<tr class="day"><td colspan="3">{r.esc(day_label(day_of(g)))}</td></tr>')
        prev = day_of(g)
        w = winner(g)
        star = DOG if underdog_win(g) else ""
        a, h = g["away"], g["home"]
        score = f'{a["score"]}–{h["score"]}' + (" OT" if g["ot"] else "")
        rows.append(f'<tr class="one"><td class="aw{" w" if w == "away" else ""}">{r.esc(a["short"])}{star if w == "away" else ""}</td>'
                    f'<td class="mid">{score}</td><td class="hm{" w" if w == "home" else ""}">{r.esc(h["short"])}{star if w == "home" else ""} {HOME_SVG}</td></tr>')
    sub = f'<span class="prog">{len(games)} game{"s" if len(games) != 1 else ""}{dog_note}</span>'
    return (f'<div class="nflsb nbaone"><table><colgroup><col style="width:38%"><col style="width:24%"><col style="width:38%"></colgroup>'
            f'<thead><tr><th class="tt" colspan="3">{title}{sub}</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def _list(items):
    return '<ul class="standouts">' + "".join(f"<li>{r.esc(i)}</li>" for i in items) + "</ul>" if items else ""


def standings_ok(std):
    return bool(std) and len(std.get("children", [])) == 2 and all(len(c.get("standings", {}).get("entries", [])) >= 15 for c in std["children"])


def standings_html(std):
    """Both conferences, by playoff seed: blue for the top six, lilac for the play-in places (7 to 10)."""
    out = ""
    for c in std["children"]:
        rows, zones = [], []
        get = lambda e, name: next((s["displayValue"] for s in e["stats"] if s["name"] == name), "")  # noqa: E731
        for e in sorted(c["standings"]["entries"], key=lambda e: num(get(e, "playoffSeed")) or 99):
            seed = num(get(e, "playoffSeed"))
            rows.append([seed, e["team"]["abbreviation"], get(e, "overall"), get(e, "gamesBehind") if seed > 1 else "-", get(e, "streak")])
            zones.append("blue" if seed <= 6 else "lilac" if seed <= 10 else None)
        out += r.compact(r.table(c["name"], [("#", True), ("Team", False), ("W-L", True), ("GB", True), ("Strk", True)], rows, zones=zones),
                         (12, 28, 22, 18, 20), " nba")
    return out


# ---- The run ------------------------------------------------------------------------------------

def run(now, day, st, source):
    """{"html", "state", "stats"}. now: UTC; day: the edition's date in Singapore; st: {"reported": [game ids], "auto": {...}, "hits": {...}, "dogs": {...}}.
    A failing source never raises: that part is left out and counted in stats["failed"]."""
    stats = {"games": 0, "new": 0, "star": 0, "boxes": 0, "failed": 0, "standouts": 0, "calls": 0}
    reported, dogs = list(st.get("reported", [])), dict(st.get("dogs", {}))
    keep = {"reported": reported, "auto": st.get("auto", {}), "hits": st.get("hits", {}), "dogs": dogs, "teams": st.get("teams", {})}
    today = now.astimezone(ET).date()
    games = {}
    for back in (2, 1, 0):
        try:
            sb = source.scoreboard(today - timedelta(days=back))
        except Exception:
            stats["failed"] += 1
            continue
        for e in sb.get("events", []):
            g = parse_game(e)
            games[g["id"]] = g
    new = sorted((g for g in games.values() if g["status"] == "final" and g["id"] not in set(reported) and timedelta(0) <= now - g["date"] <= LOOKBACK),
                 key=lambda g: g["date"])
    stats.update(games=len(games), new=len(new))
    boxes = {}
    for g in new:
        try:
            boxes[g["id"]] = source.box(g["id"])
        except Exception:
            stats["failed"] += 1
    stats["boxes"] = len(boxes)
    new = [g for g in new if g["id"] in boxes]            # a game whose box score failed is tried again next run
    for g in new:
        g["dog"] = dog_of(boxes[g["id"]])
        dogs[g["id"]] = g["dog"] or ""
    by_id = {g["id"]: g for g in new}
    players = [p for g in new for p in players_of(boxes[g["id"]], g)]
    names = {p["id"]: p["name"] for p in players}
    texts, hits = standouts(players, by_id, boxes)
    tracked = update_tracking(keep, hits, by_id, names, day)
    stats["standouts"] = len(texts)
    html = ""
    if new:
        many_days = len({day_of(g) for g in new}) > 1
        star_ids = {p["game"] for p in players if p["id"] in tracked and not p["dnp"]}
        # the watched pair always get a line when their team played, even when they sat out (ESPN's box score then leaves an inactive player out)
        watch_lines, teams = {}, dict(WATCH_TEAMS, **st.get("teams", {}))
        for pid in WATCHED:
            listed = next((p for p in players if p["id"] == pid), None)
            if listed:
                teams[pid] = listed["team"]
                watch_lines[listed["game"]] = watch_lines.get(listed["game"], []) + [listed]
                continue
            g = next((g for g in new if teams[pid] in (g["home"]["abbr"], g["away"]["abbr"])), None)
            if g:
                watch_lines[g["id"]] = watch_lines.get(g["id"], []) + [{"id": pid, "name": TRACKED[pid], "dnp": True, "reason": "", "game": g["id"]}]
        keep["teams"] = {pid: teams[pid] for pid in WATCHED}
        star_ids |= set(watch_lines)
        star = [g for g in new if g["id"] in star_ids]
        rest = [g for g in new if g["id"] not in star_ids]
        stats["star"] = len(star)
        careers = {}
        for pid in WATCHED:
            if any(p["id"] == pid for ps in watch_lines.values() for p in ps):
                try:
                    careers[pid] = source.career(pid)
                except Exception:
                    stats["failed"] += 1

        def lines_for(g):
            out = []
            mine = [p for p in players if p["game"] == g["id"] and p["id"] in tracked and p["id"] not in WATCHED and not p["dnp"]]
            for p in sorted(mine, key=lambda p: -weight(p, kinds_of(p))):
                out.append(f"{p['name']}: {line(p)} · {p['fg']}\u00a0FG")
            for p in watch_lines.get(g["id"], ()):
                if p["dnp"]:
                    out.append(f"{p['name']}: did not play" + (f" ({p['reason'].lower()})" if p["reason"] else ""))
                else:
                    out.append(f"{p['name']}: {line(p)} · {p['fg']}\u00a0FG")
                m = milestone(careers.get(p["id"]), p["id"])
                if m:
                    out.append(m)
            return out
        dogs_n = sum(1 for g in new if underdog_win(g))
        if star:
            order = sorted(star, key=lambda g: (g["date"].astimezone(ET).date(), -max([weight(p, kinds_of(p)) for p in players if p["game"] == g["id"] and p["id"] in tracked and not p["dnp"]] or [0])))
            html += star_html([(g, lines_for(g), story(g, boxes[g["id"]])) for g in order], many_days, len(star), len(new), dogs_n)
        if rest:
            dog_note = f' · {DOG} {dogs_n} underdog win{"s" if dogs_n != 1 else ""}' if dogs_n and not star else ""
            html += other_html(rest, many_days, "Other Games" if star else "Scores", dog_note)
        if texts:
            html += "<h4>Standouts</h4>" + _list(texts)
    if day.weekday() == 1:  # Tuesday is the table day
        try:
            std = source.standings()
            if standings_ok(std):
                html += "<h4>Standings</h4>" + standings_html(std)
        except Exception:
            stats["failed"] += 1
    if new:
        reported += [g["id"] for g in new]
    keep["reported"] = reported[-400:]
    stats["calls"] = getattr(source, "calls", 0)
    return {"html": html, "state": keep, "stats": stats}
