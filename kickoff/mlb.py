"""MLB: a quiet weekly round-up for most of the season, daily coverage of the whole league for the last week of the regular season and in the
postseason, and a closing note when the World Series is decided. All by code from exact data, so no Claude cost.

Three modes, each worked out from the data (nothing to switch on or off):
  weekly  (Thursday editions until the Dodgers have played DAILY_FROM games): the Dodgers' week, Ohtani's batting and the two pitchers' starts,
          the six division tables and both wild-card races, with movement arrows against the last table shown;
  daily   (from the Dodgers' DAILY_FROM-th game to the end of the regular season): every game finished since the last edition with a line
          under it only when a batter or pitcher stood out, and each league's playoff race;
  postseason: one series table per series that had a game (best of 3, 5 or 7, the rows made in advance), then the closing note.
The Dodgers' own games always carry Ohtani's and Yamamoto's lines (and the reason when one did not play). Which games are new is decided by the
state, not the clock, as in the NBA and NFL sections."""
import re
from datetime import timedelta
from zoneinfo import ZoneInfo

from kickoff import render as r
from kickoff.nfl import DOG, dog_of, utc

ET = ZoneInfo("America/New_York")
SGT = ZoneInfo("Asia/Singapore")
LAD = "19"                                   # ESPN team id of the Los Angeles Dodgers
OHTANI, YAMAMOTO = ("39832", "Shohei Ohtani"), ("4872587", "Yoshinobu Yamamoto")
DAILY_FROM, SEASON_GAMES = 155, 162          # D's trigger: from the Dodgers' 155th game the whole league is covered every day
WEEKDAY = 3                                  # the weekly round-up comes in the Thursday edition
LOOKBACK, WEEK_LOOKBACK = timedelta(hours=36), timedelta(days=8)   # unreported finished games older than this are ignored (a first run must not dump a month)
CODE_FIX = {"KC": "KCR", "SD": "SDP", "SF": "SFG", "TB": "TBR"}   # the four ESPN team codes that are not three letters, made three (WSH, CHW, ATH are left as ESPN has them)
HR_GAME, HITS_GAME, RBI_GAME, K_GAME = 2, 4, 5, 10     # a batter or pitcher worth a line under a game; D's choice, to be reviewed after a month of real use
QUALITY_IP = 7                                         # a starter with this many innings and no earned run
MAX_NOTABLE = 2
ROUND_NAMES = {"ALDS": "AL Division Series", "NLDS": "NL Division Series", "ALCS": "AL Championship Series", "NLCS": "NL Championship Series",
               "ALWC": "AL Wild Card Series", "NLWC": "NL Wild Card Series"}
LEAGUE_FIRST = ("National League", "American League")                  # the Dodgers' league first
DIVISION_ORDER = ("West", "Central", "East")                           # the Dodgers' division first within a league


def code(abbr):
    return CODE_FIX.get(abbr, abbr)


def num(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def day_label(d):
    return f"{d:%a} {d.day} {d:%b}"


# ---- Games ----------------------------------------------------------------------------------------

def parse_game(e):
    """A game as plain data. status: 'final', 'live', 'scheduled' or 'other'. phase: 'regular', 'post' (postseason) or 'other' (spring training...).
    headline: ESPN's note for the game ('NLCS - Game 4'). innings: the innings played (more than 9 is extra innings)."""
    c, t = e["competitions"][0], e["status"]["type"]
    status = "final" if t["name"] == "STATUS_FINAL" else {"in": "live", "pre": "scheduled"}.get(t["state"], "other")
    sides = {x["homeAway"]: x for x in c["competitors"]}
    side = lambda x: {"id": x["team"]["id"], "abbr": code(x["team"]["abbreviation"]), "name": x["team"]["displayName"],  # noqa: E731
                      "score": int(x["score"]) if status in ("final", "live") and str(x.get("score", "")).isdigit() else None}
    return {"id": e["id"], "date": utc(e["date"]), "status": status, "innings": (e["status"].get("period") or 0) if status == "final" else 0,
            "detail": t.get("shortDetail", ""), "season": (e.get("season") or {}).get("year"),
            "headline": next((n.get("headline", "") for n in c.get("notes", [])), ""),
            "phase": {2: "regular", 3: "post"}.get((e.get("season") or {}).get("type"), "other"),
            "home": side(sides["home"]), "away": side(sides["away"])}


def winner(g):
    a, h = g["away"]["score"], g["home"]["score"]
    return None if a == h else ("away" if a > h else "home")


def day_of(g):
    return g["date"].astimezone(ET).date()


def involves(g, team_id):
    return team_id in (g["home"]["id"], g["away"]["id"])


def underdog_win(g):
    return g["status"] == "final" and bool(g.get("dog")) and winner(g) == g["dog"]


def order_key(g):
    """The Dodgers' game first, then everyone else by first pitch."""
    return (0 if involves(g, LAD) else 1, g["date"])


def round_of(headline):
    """('NL Championship Series', 7): the round of a postseason game from ESPN's note ('NLCS - Game 4') and how many games it is the best of."""
    key = headline.split(" - ")[0].strip()            # ESPN adds things after the game number ('ALCS - Game 4 Rain - Makeup on Oct 18')
    low = key.lower()
    best = 3 if "wild" in low or low.endswith("wc") else 5 if "division" in low or low.endswith("ds") else 7
    return ROUND_NAMES.get(key, key), best


# ---- Player lines --------------------------------------------------------------------------------------

def bat_of(stats):
    """A batting line as numbers, from a game log row (AB, H, HR, RBI, SB...) or a box score row ('H-AB' ... which has no stolen bases)."""
    if "AB" in stats:
        ab, h = num(stats.get("AB")), num(stats.get("H"))
    else:
        h, _, ab = (stats.get("H-AB") or "0-0").partition("-")
        h, ab = num(h), num(ab)
    return {"h": h, "ab": ab, "hr": num(stats.get("HR")), "rbi": num(stats.get("RBI")), "bb": num(stats.get("BB")), "sb": num(stats.get("SB"))}


def pit_of(stats, dec=""):
    """A pitching line as numbers; ip stays text ('6.1'). dec: 'W', 'L', 'S', 'H' or ''."""
    d = re.match(r"[A-Z]+", (stats.get("Dec") or dec or "").strip())
    d = d.group(0) if d else ""
    return {"ip": stats.get("IP", "0"), "er": num(stats.get("ER")), "k": num(stats.get("K")), "h": num(stats.get("H")), "dec": d if d in ("W", "L", "S") else ""}


def innings(ip):
    """'6.2' -> 6 + 2/3."""
    whole, _, frac = str(ip).partition(".")
    return num(whole) + num(frac) / 3


def count(n, word):
    return word if n == 1 else f"{n} {word}"


def fmt(who, parts):
    """'Name (LAD): 2-for-4, HR, 3 RBI' as html, the parts flagged True in the accent colour. parts: [(text, flag)]."""
    return r.esc(who) + ": " + ", ".join(f'<span class="n">{r.esc(t)}</span>' if hl else r.esc(t) for t, hl in parts)


def bat_line(who, b):
    parts = [(f"{b['h']}-for-{b['ab']}", False)]
    if b["hr"]:
        parts.append((count(b["hr"], "HR"), True))
    if b["rbi"]:
        parts.append((f"{b['rbi']} RBI", b["rbi"] >= RBI_GAME))
    if b["bb"]:
        parts.append((count(b["bb"], "BB"), False))
    if b["sb"]:
        parts.append((count(b["sb"], "SB"), True))
    return fmt(who, parts)


def pit_line(who, p, hl=()):
    parts = [(f"{p['ip']} IP", "ip" in hl), (f"{p['er']} ER", "er" in hl), (f"{p['k']} K", "k" in hl)]
    if p["dec"]:
        parts.append((f"({p['dec']})", False))
    return fmt(who, parts).replace(", (", " (")


def dnp_text(who, box, pid):
    """'Shohei Ohtani (LAD): DNP (Out, Elbow)': ESPN's injury listing for the game when there is one, else a plain DNP."""
    inj = (box or {}).get("injuries", {}).get(pid)
    if inj and inj.get("status"):
        return f"{who}: DNP ({inj['status']}, {inj['type']})" if inj.get("type") else f"{who}: DNP ({inj['status']})"
    return f"{who}: DNP"


def lad_side(g):
    return g["home"]["abbr"] if g["home"]["id"] == LAD else g["away"]["abbr"]


def lad_lines(g, box, logs):
    """Ohtani's and Yamamoto's lines for a Dodgers game, as (played, did not play): whoever pitched first, then Ohtani at the plate; and a DNP line with
    the reason for Ohtani, and for Yamamoto only when ESPN lists him injured. logs: {"bat": {game id: stats}, "opit": ..., "ypit": ...}
    from the game logs, or None when that feed failed (the box score's own line is used, which has no stolen bases)."""
    side = lad_side(g)
    mine = (box or {}).get("teams", {}).get(side, {"batters": [], "pitchers": []})

    def stats(pid, key, pool):
        if logs is not None:
            return logs[key].get(g["id"])
        p = next((x for x in pool if x["id"] == pid), None)
        return dict(p["stats"], Dec=p.get("dec", "")) if p else None
    out, down = [], []
    for (pid, name), key in ((OHTANI, "opit"), (YAMAMOTO, "ypit")):
        p, who = stats(pid, key, mine["pitchers"]), f"{name} ({side})"
        if p is not None:
            out.append(pit_line(who, pit_of(p)))
        elif pid == YAMAMOTO[0] and ((box or {}).get("injuries", {}).get(pid) or {}).get("status"):
            down.append(r.esc(dnp_text(who, box, pid)))
    b = stats(OHTANI[0], "bat", mine["batters"])
    if b is not None:
        out.append(bat_line(f"{OHTANI[1]} ({side})", bat_of(b)))
    else:
        down.insert(0, r.esc(dnp_text(f"{OHTANI[1]} ({side})", box, OHTANI[0])))
    return out, down


def notable_lines(g, box, skip=()):
    """Up to MAX_NOTABLE lines for the best individual games: a batter with 2+ homers, 4+ hits or 5+ RBI; a pitcher with 10+ strikeouts, or 7+
    scoreless innings as a starter; a no-hit game by a team's pitchers. `skip`: player ids already shown. Best first."""
    found = []
    for abbr, side in box["teams"].items():
        for b in side["batters"]:
            if b["id"] in skip:
                continue
            x = bat_of(b["stats"])
            if x["hr"] >= HR_GAME or x["h"] >= HITS_GAME or x["rbi"] >= RBI_GAME:
                found.append((x["hr"] * 4 + x["h"] + x["rbi"] * 1.5, bat_line(f"{b['name']} ({code(abbr)})", x)))
        for p in side["pitchers"]:
            if p["id"] in skip:
                continue
            x = pit_of(p["stats"], p.get("dec", ""))
            hl = {"k"} if x["k"] >= K_GAME else set()
            if p["starter"] and innings(x["ip"]) >= QUALITY_IP and x["er"] == 0:
                hl |= {"ip", "er"}
            if hl:
                found.append((x["k"] + innings(x["ip"]) * 2, pit_line(f"{p['name']} ({code(abbr)})", x, hl)))
    found.sort(key=lambda t: -t[0])
    return [t for _, t in found[:MAX_NOTABLE]]


def game_notes(g, box, logs):
    """The lines under one game: the Dodgers' players when they played, then any standout individual game. [] for a game with neither."""
    played, down = lad_lines(g, box, logs) if involves(g, LAD) else ([], [])
    shown = {OHTANI[0], YAMAMOTO[0]} if involves(g, LAD) else set()
    return played + (notable_lines(g, box, shown) if box else []) + down      # a DNP line always sits below every player who played


# ---- Rendering ----------------------------------------------------------------------------------

def tag_text(g, many_days):
    bits = []
    if many_days:
        bits.append(day_label(day_of(g)))
    if g["status"] == "live":
        bits.append("In progress" + (f" · {g['detail']}" if g.get("detail") else ""))
    if g["phase"] == "post" and g["headline"]:
        bits.append(g["headline"].replace(" - ", " · "))
    return " · ".join(bits)


def game_rows(g, notes, many_days):
    w = winner(g) if g["status"] == "final" else None
    star = DOG if underdog_win(g) else ""
    a, h = g["away"], g["home"]
    score = f'{a["score"]}–{h["score"]}' + (f' ({g["innings"]})' if g["innings"] > 9 else "")
    tag = tag_text(g, many_days)
    rows = [f'<tr class="tag"><td colspan="3">{r.esc(tag)}</td></tr>'] if tag else []
    rows.append(f'<tr class="one{"" if notes else " end"}"><td class="aw{" w" if w == "away" else ""}">{r.esc(a["name"])}{star if w == "away" else ""}</td>'
                f'<td class="mid">{score}</td><td class="hm{" w" if w == "home" else ""}">{r.esc(h["name"])}{star if w == "home" else ""}</td></tr>')
    if notes:
        rows.append('<tr class="note end"><td colspan="3">' + "".join(f'<div class="pl"><span class="t">{x}</span></div>' for x in notes) + "</td></tr>")
    return rows


def games_html(items, many_days, dogs):
    """items: [(game, notes)] already in order. One table titled Last Night's Games; the underdog count sits under the title."""
    rows = [x for g, notes in items for x in game_rows(g, notes, many_days)]
    sub = f'<span class="prog">{DOG} {dogs} underdog win{"s" if dogs != 1 else ""}</span>' if dogs else ""
    return (f'<div class="nflsb nbaone"><table><colgroup><col style="width:35%"><col style="width:30%"><col style="width:35%"></colgroup>'
            f'<thead><tr><th class="tt" colspan="3">Last Night\'s Games{sub}</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def titled(caption, sub, columns, body, widths, zones=None):
    """A compact table with a centred title and a muted line (counts, season numbers) under it."""
    html = r.compact(r.table(caption, columns, body, zones=zones), widths, " nba")
    return html.replace("</th></tr>", f'<span class="prog">{r.esc(sub)}</span></th></tr>', 1) if sub else html


# ---- Standings ----------------------------------------------------------------------------------

def _stat(e, name):
    return next((s["displayValue"] for s in e["stats"] if s["name"] == name), "")


def teams_of(std):
    """Every team of a standings feed as plain data: league, division, wins, losses, seed (99 when out), clincher mark, games back, streak."""
    out = []
    for lg in std["children"]:
        for dv in lg["children"]:
            for e in dv["standings"]["entries"]:
                out.append({"abbr": code(e["team"]["abbreviation"]), "league": lg["name"], "division": dv["name"], "w": num(_stat(e, "wins")), "l": num(_stat(e, "losses")),
                            "seed": num(_stat(e, "playoffSeed")) or 99, "mark": _stat(e, "clincher"), "gb": _stat(e, "gamesBehind"), "strk": _stat(e, "streak"),
                            "pct": float(_stat(e, "winPercent") or 0), "overall": _stat(e, "overall")})
    return out


def standings_ok(std):
    return bool(std) and len(std.get("children", [])) == 2 and all(len(lg.get("children", [])) == 3 and all(len(d["standings"]["entries"]) == 5 for d in lg["children"]) for lg in std["children"])


def short_league(name):
    return name.replace("National League", "NL").replace("American League", "AL")


def division_tables(teams, before=None):
    """The six division tables, the Dodgers' division first. Blue: the division leader; lilac: a wild-card place. +/- is the places moved since the
    last table shown (`before`: {division name: {team code: place}}). Returns (html, {division name: {team code: place}})."""
    out, places = "", {}
    keys = sorted({(t["league"], t["division"]) for t in teams}, key=lambda k: (LEAGUE_FIRST.index(k[0]), DIVISION_ORDER.index(k[1].split()[-1])))
    for league, division in keys:
        rows = sorted((t for t in teams if t["division"] == division), key=lambda t: (-t["pct"], -t["w"]))
        places[division] = {t["abbr"]: i for i, t in enumerate(rows, 1)}
        prev = (before or {}).get(division)
        body = [[i, t["abbr"], t["overall"], t["gb"], t["strk"], r.move(prev[t["abbr"]] - i) if prev and t["abbr"] in prev else ""] for i, t in enumerate(rows, 1)]
        zones = ["blue" if i == 1 else "lilac" if t["seed"] in (4, 5, 6) else None for i, t in enumerate(rows, 1)]
        out += r.compact(r.table(short_league(division), [("#", True), ("Team", False), ("W-L", True), ("GB", True), ("Strk", True), ("+/-", True)], body, zones=zones),
                         (10, 22, 20, 16, 16, 16), " nba")
    return out, places


def behind(t, ref):
    """Games behind (or ahead of, with a +) the team in the last playoff place: '–' for that team itself."""
    d = ((ref["w"] - t["w"]) + (t["l"] - ref["l"])) / 2
    return "–" if d == 0 else f"+{abs(d):g}" if d < 0 else f"{d:g}"


def race_table(teams, league, first, last, title, before=None, offset=0):
    """One league's seeds `first` to `last` (1 to 6 are in the playoffs): blue for a division winner (1 to 3), lilac for a wild card, plain for the teams
    out. ✓ after a code: the team has clinched a place; ✗: it is out. The GB column counts from the sixth seed."""
    rows = sorted((t for t in teams if t["league"] == league), key=lambda t: t["seed"])
    ref = next(t for t in rows if t["seed"] == 6)
    show = [t for t in rows if first <= t["seed"] <= last]
    mark = lambda t: t["abbr"] + (" ✓" if t["mark"] in ("*", "x", "y", "z") else " ✗" if t["mark"] == "e" else "")  # noqa: E731
    body = [[t["seed"] - offset, mark(t), t["overall"], behind(t, ref), r.move(before[t["abbr"]] - t["seed"]) if before and t["abbr"] in before else ""] for t in show]
    zones = ["blue" if t["seed"] <= 3 else "lilac" if t["seed"] <= 6 else None for t in show]
    return r.compact(r.table(title, [("#", True), ("Team", False), ("W-L", True), ("GB", True), ("+/-", True)], body, zones=zones), (10, 30, 22, 20, 18), " nba")


def races(teams, first, last, before=None, wild=False):
    """Both leagues' race tables, the National League first. wild=True: the wild-card race (seeds 4 to 9), numbered 1 to 6."""
    out = ""
    for league in LEAGUE_FIRST:
        out += race_table(teams, league, first, last, f"{short_league(league)} {'Wild Card Race' if wild else 'Playoff Race'}", before, 3 if wild else 0)
    return out


# ---- Weekly round-up ----------------------------------------------------------------------------

def lad_result(x):
    """(opponent code with @ when away, 'W 5–2' from the Dodgers' side, won) for one schedule row of the Dodgers."""
    home = x["home"]["id"] == LAD
    mine, theirs = (x["home"], x["away"]) if home else (x["away"], x["home"])
    won = mine["score"] > theirs["score"]
    return ("" if home else "@") + code(theirs["abbr"]), f"{'W' if won else 'L'} {mine['score']}–{theirs['score']}", won


def week_html(games, finals, logs, boxes):
    """The Dodgers' week as tables. games: the schedule rows of the week (oldest first); finals: all the Dodgers' finished regular-season rows;
    logs: the game logs by game id; boxes: {game id: box score} for games where Ohtani did not bat (the reason he sat)."""
    wins = sum(1 for x in games if lad_result(x)[2])
    season_w = sum(1 for x in finals if lad_result(x)[2])
    sub = f"Wk: {wins}-{len(games) - wins} · Season: {season_w}-{len(finals) - season_w} · G{len(finals)}/{SEASON_GAMES}"
    local = lambda x: utc(x["date"]).astimezone(ET).date()  # noqa: E731
    rows = [[f"{local(x):%a} {local(x).day}", lad_result(x)[0], lad_result(x)[1]] for x in games]
    out = titled("Dodgers", sub, [("Day", False), ("Opp", False), ("Result", False)], rows, (28, 32, 40))
    bat = [(x, bat_of(logs["bat"][x["id"]])) for x in games if x["id"] in logs["bat"]]
    if bat:
        tot = {k: sum(b[k] for _, b in bat) for k in ("h", "ab", "hr", "rbi", "sb")}
        last = logs["bat"][bat[-1][0]["id"]]
        body = [[f"{local(x):%a} {lad_result(x)[0]}", f"{b['h']}-{b['ab']}", b["hr"], b["rbi"], b["sb"]] for x, b in bat]
        body.append(["Week", f"{tot['h']}-{tot['ab']}", tot["hr"], tot["rbi"], tot["sb"]])
        out += titled("Ohtani · Batting", f"Season: {last.get('AVG', '')} AVG · {last.get('OPS', '')} OPS",
                      [("Game", False), ("H-AB", True), ("HR", True), ("RBI", True), ("SB", True)], body, (28, 18, 16, 19, 19))
    missed = [x for x in games if x["id"] not in logs["bat"] and x["id"] not in logs["opit"]]    # a start without a turn at bat is not a missed game
    if missed:
        why = "; ".join(f"{local(x):%a} {local(x).day}: " + dnp_text(OHTANI[1], boxes.get(x["id"]), OHTANI[0]).split(": ", 1)[1] for x in missed)
        out += f'<p class="muted">Ohtani did not bat: {r.esc(why)}.</p>'
    starts = [(name, x, logs[key][x["id"]]) for name, key in (("Ohtani", "opit"), ("Yamamoto", "ypit")) for x in games if x["id"] in logs[key]]
    starts.sort(key=lambda s: s[1]["date"])
    if starts:
        body = [[n, f"{local(x):%a} {lad_result(x)[0]}", p.get("IP", ""), p.get("ER", ""), p.get("K", ""), pit_of(p)["dec"] or "–"] for n, x, p in starts]
        era = ", ".join(f"{n} {[p for m, _, p in starts if m == n][-1].get('ERA', '')}" for n in ("Yamamoto", "Ohtani") if any(m == n for m, _, _ in starts))
        out += titled("Pitching", f"ERA: {era}" if era else "", [("Pitcher", False), ("Game", False), ("IP", True), ("ER", True), ("K", True), ("Dec", True)], body, (28, 28, 12, 10, 10, 12))
    else:
        out += '<p class="muted">No starts this week from Ohtani or Yamamoto.</p>'
    return out


# ---- Postseason series ----------------------------------------------------------------------------

def series_of(g):
    return frozenset((g["home"]["id"], g["away"]["id"]))


def row_of(g):
    """A schedule-style row built from a scoreboard game: used when ESPN's team schedule does not list a game the scoreboard has just shown."""
    side = lambda t: {"id": t["id"], "abbr": t["abbr"], "short": t["name"].split()[-1], "name": t["name"], "score": t["score"]}  # noqa: E731
    return {"id": g["id"], "date": g["date"].isoformat(), "status": "STATUS_FINAL" if g["status"] == "final" else "STATUS_IN_PROGRESS", "headline": g["headline"],
            "home": side(g["home"]), "away": side(g["away"])}


def tally(g0, sched):
    """(first-column team, second-column team, {team id: wins}, games needed to win, best-of) for a series. The team that hosted game 1 (the higher seed)
    is the first column."""
    name, best = round_of(g0["headline"])
    games = sorted(sched, key=lambda x: x["date"])
    top = games[0]["home"] if games else g0["home"]
    bot = games[0]["away"] if games else g0["away"]
    wins = {top["id"]: 0, bot["id"]: 0}
    for x in games:
        if x["status"] == "STATUS_FINAL" and x["home"]["score"] is not None:
            wins[x["home"]["id"] if x["home"]["score"] > x["away"]["score"] else x["away"]["id"]] += 1
    return top, bot, wins, best // 2 + 1, best


def series_html(g0, sched, notes_by_game, seeds=None):
    """One table for one series: the two teams with their series wins in large numbers either side of the word 'series', then a row for every
    game it could take (3, 5 or 7) made in advance: the score once played (the winner in bold) with the notes under it, 'if necessary' for games that may
    not be needed. g0: a game of the series; sched: the series' schedule rows."""
    name, _ = round_of(g0["headline"])
    games = sorted(sched, key=lambda x: x["date"])
    top, bot, wins, need, best = tally(g0, sched)
    over = max(wins.values()) >= need
    rows = []
    for n in range(1, best + 1):
        x = games[n - 1] if n <= len(games) else None
        if x and x["status"] == "STATUS_FINAL":
            sc = {x["home"]["id"]: x["home"]["score"], x["away"]["id"]: x["away"]["score"]}
            rows.append({"mid": f"G{n} · {day_label(utc(x['date']).astimezone(ET).date())}", "a": sc[top["id"]], "b": sc[bot["id"]],
                         "win": "a" if sc[top["id"]] > sc[bot["id"]] else "b", "notes": notes_by_game.get(x["id"], [])})
        elif x and "IN_PROGRESS" in x["status"] and x["home"]["score"] is not None:   # on now: the score so far; shown final in the next edition
            sc = {x["home"]["id"]: x["home"]["score"], x["away"]["id"]: x["away"]["score"]}
            rows.append({"mid": f"G{n} · In progress", "a": sc[top["id"]], "b": sc[bot["id"]], "win": None})
        else:
            if x:
                when = utc(x["date"]).astimezone(SGT)
                mid = f"G{n} · {when:%a} {when.day} {when:%b}, {when:%-I:%M%p}".replace("AM", "am").replace("PM", "pm") + " SGT"
            else:
                mid = f"G{n} · " + ("–" if over else "if necessary" if n > need else "to be scheduled")
            rows.append({"mid": mid, "pre": True})
    seed = lambda t: (seeds or {}).get(code(t["abbr"]))  # noqa: E731
    left = (f'({seed(top)})\u00a0' if seed(top) else "") + top["name"]
    right = bot["name"] + (f'\u00a0({seed(bot)})' if seed(bot) else "")
    return r.series_table(name, left, right, wins[top["id"]], wins[bot["id"]], "series", rows)


def closing_html(year, g0, sched, teams, lad_post):
    """The season's closing note once the World Series is decided: the champions, then how the Dodgers' season ended. sched: the World Series rows;
    teams: teams_of() of the final standings; lad_post: the Dodgers' postseason schedule rows (empty when they missed the playoffs)."""
    top, bot, wins, need, _ = tally(g0, sched)
    champ, other = (top, bot) if wins[top["id"]] >= need else (bot, top)
    text = f"That's the {year} MLB season. The {champ['short']} are World Series champions, beating the {other['short']} {wins[champ['id']]}-{wins[other['id']]}."
    rec = next((t["overall"] for t in teams if t["abbr"] == "LAD"), "")
    played = [x for x in lad_post if x["status"] == "STATUS_FINAL"]
    if not played:
        text += f" The Dodgers ({rec}) missed the playoffs."
    elif champ["id"] == LAD:
        text += f" The Dodgers ({rec}) are champions."
    else:
        rnd = round_of(played[-1]["headline"])[0]
        mine = [x for x in played if round_of(x["headline"])[0] == rnd]
        w = sum(1 for x in mine if lad_result(x)[2])
        opp = next(x["away"] if x["home"]["id"] == LAD else x["home"] for x in mine)
        text += f" The Dodgers finished {rec} and went out in the {rnd}, {w}-{len(mine) - w} to the {opp['short']}."
    return f"<p>{r.esc(text)}</p>"


# ---- The run ------------------------------------------------------------------------------------

def game_logs(source, year):
    """{"bat": {game id: stats}, "opit": ..., "ypit": ...}: Ohtani's batting and pitching and Yamamoto's pitching, game by game (three calls)."""
    return {key: {x["id"]: x["stats"] for x in source.gamelog(pid, year, cat)}
            for key, pid, cat in (("bat", OHTANI[0], "batting"), ("opit", OHTANI[0], "pitching"), ("ypit", YAMAMOTO[0], "pitching"))}


def run(now, day, st, source):
    """{"html", "state", "stats"}. now: UTC; day: the edition's date in Singapore; st: {"reported", "week_reported", "series_notes", "div", "seeds", "opened",
    "closed"}. A failing source never raises: that part is left out and counted in stats["failed"]."""
    stats = {"games": 0, "new": 0, "boxes": 0, "failed": 0, "series": 0, "live": 0, "week": 0, "mode": "", "calls": 0}
    keep = {"reported": list(st.get("reported", [])), "week_reported": list(st.get("week_reported", [])), "series_notes": dict(st.get("series_notes", {})),
            "div": st.get("div"), "seeds": st.get("seeds"), "opened": st.get("opened"), "closed": st.get("closed")}
    today = now.astimezone(ET).date()
    year = today.year
    games = {}
    for back in (2, 1, 0):
        try:
            for e in source.scoreboard(today - timedelta(days=back)).get("events", []):
                g = parse_game(e)
                games[g["id"]] = g
        except Exception:
            stats["failed"] += 1
    new = sorted((g for g in games.values() if g["status"] == "final" and g["id"] not in set(keep["reported"]) and timedelta(0) <= now - g["date"] <= LOOKBACK), key=lambda g: g["date"])
    live = [g for g in games.values() if g["status"] == "live"]          # on now: shown with the score so far, and as a final in the next edition
    stats.update(games=len(games), new=len(new), live=len(live))
    regular, post = [g for g in new + live if g["phase"] == "regular"], [g for g in new + live if g["phase"] == "post"]
    sched, finals = None, []
    if regular or day.weekday() == WEEKDAY:
        try:
            sched = source.schedule(LAD, year, 2)
            finals = [x for x in sched if x["status"] == "STATUS_FINAL"]
        except Exception:
            stats["failed"] += 1
    daily = sched is not None and len(finals) >= DAILY_FROM and bool(regular)
    weekly = sched is not None and len(finals) < DAILY_FROM and day.weekday() == WEEKDAY
    boxes, logs, logs_tried = {}, None, False

    def logs_now():
        nonlocal logs, logs_tried
        if not logs_tried:
            logs_tried = True
            try:
                logs = game_logs(source, year)
            except Exception:
                stats["failed"] += 1
        return logs

    def box(gid):
        if gid not in boxes:
            try:
                boxes[gid] = source.box(gid)
            except Exception:
                stats["failed"] += 1
                boxes[gid] = None
        return boxes[gid]

    html = ""
    if daily:
        stats["mode"] = "daily"
        shown = [g for g in regular if g["status"] == "live" or box(g["id"])]            # a game whose box score failed is tried again next run
        for g in shown:
            if g["status"] == "final":
                g["dog"] = dog_of(boxes[g["id"]])
        if any(involves(g, LAD) and g["status"] == "final" for g in shown):
            logs_now()
        items = [(g, game_notes(g, boxes[g["id"]], logs) if g["status"] == "final" else []) for g in sorted(shown, key=order_key)]
        if shown:
            html += games_html(items, len({day_of(g) for g in shown}) > 1, sum(1 for g in shown if underdog_win(g)))
        keep["reported"] += [g["id"] for g in shown if g["status"] == "final"]
        try:
            teams = teams_of(source.standings())
            html += race_pair(teams, keep["seeds"])
            keep["seeds"] = {t["abbr"]: t["seed"] for t in teams}
        except Exception:
            stats["failed"] += 1
    elif weekly:
        window = [x for x in finals if x["id"] not in set(keep["week_reported"]) and timedelta(0) <= now - utc(x["date"]) <= WEEK_LOOKBACK]
        if window:
            stats["mode"], stats["week"] = "weekly", len(window)
            wlogs = logs_now()
            miss = {x["id"]: box(x["id"]) for x in window if wlogs is not None and x["id"] not in wlogs["bat"]}
            html += week_html(window, finals, wlogs or {"bat": {}, "opit": {}, "ypit": {}}, miss)
            keep["week_reported"] = (keep["week_reported"] + [x["id"] for x in window])[-60:]
            try:
                teams = teams_of(source.standings())
                tables, places = division_tables(teams, keep["div"])
                html += tables + races(teams, 4, 9, keep["seeds"], wild=True)
                keep["div"], keep["seeds"] = places, {t["abbr"]: t["seed"] for t in teams}
            except Exception:
                stats["failed"] += 1
            if keep["opened"] != year:
                html = f"<p>The {year} MLB season is under way.</p>" + html
                keep["opened"] = year
    if post:
        stats["mode"] = "postseason"
        seeds, teams = {}, []
        try:
            teams = teams_of(source.standings(year))
            seeds = {t["abbr"]: t["seed"] for t in teams}
        except Exception:
            stats["failed"] += 1
        done = {}
        for g in sorted(post, key=order_key):
            done.setdefault(series_of(g), g)
        closing = None
        for pair, g0 in done.items():
            try:
                sched3 = [x for x in source.schedule(g0["home"]["id"], year, 3) if {x["home"]["id"], x["away"]["id"]} == set(pair)]
            except Exception:
                stats["failed"] += 1
                continue
            sched3 += [row_of(g) for g in post if series_of(g) == pair and g["id"] not in {x["id"] for x in sched3}]    # a game the scoreboard shows but the schedule lacks
            for x in sched3:                                     # notes for every finished game of the series, kept in the state once made
                if x["status"] != "STATUS_FINAL" or x["id"] in keep["series_notes"]:
                    continue
                bx = box(x["id"])
                if bx is None:
                    continue
                gg = {"id": x["id"], "home": {**x["home"], "abbr": code(x["home"]["abbr"])}, "away": {**x["away"], "abbr": code(x["away"]["abbr"])}}
                if involves(gg, LAD):
                    logs_now()
                keep["series_notes"][x["id"]] = game_notes(gg, bx, logs)
            html += series_html(g0, sched3, keep["series_notes"], seeds)
            stats["series"] += 1
            top, bot, wins, need, _ = tally(g0, sched3)
            if round_of(g0["headline"])[0] == "World Series" and max(wins.values()) >= need and keep["closed"] != year:
                closing = (g0, sched3)
        keep["reported"] += [g["id"] for g in post if g["status"] == "final"]
        if closing and teams:
            try:
                html += closing_html(year, closing[0], closing[1], teams, source.schedule(LAD, year, 3))
                keep["closed"] = year
            except Exception:
                stats["failed"] += 1
    stats["boxes"] = sum(1 for b in boxes.values() if b)
    keep["reported"] = keep["reported"][-400:]
    keep["series_notes"] = dict(list(keep["series_notes"].items())[-120:])
    stats["calls"] = getattr(source, "calls", 0)
    return {"html": html, "state": keep, "stats": stats}


def race_pair(teams, before):
    return races(teams, 1, 8, before)
