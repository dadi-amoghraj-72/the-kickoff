"""NBA: "Last Night's Games" (every game finished since the last edition, one compact line each, the tracked players' lines and the best
performer of the game under it), ranked standouts, the conference standings with movement arrows every day, NBA Cup tags and group tables,
and, in the playoffs, one table per series. All by code from exact data, so no Claude cost.

Which games are new is decided by the state ({"reported": [game ids]}), not the clock, so nothing is lost or shown twice. Most NBA games end
after the 8am Singapore edition, so a result usually lands in the next day's edition.
Tracked players are followed by ESPN player id (so a trade changes nothing). D's list stays for good; anyone else who has three standout
games in 30 days joins automatically and drops off after eight weeks without a standout."""
import re
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from kickoff import render as r
from kickoff.nfl import DOG, HOME_SVG, dog_of, utc

ET = ZoneInfo("America/New_York")
SGT = ZoneInfo("Asia/Singapore")
LOOKBACK = timedelta(hours=60)             # unreported finished games older than this are ignored (a first run must not dump a month)
TRACKED = {  # D's list (SPEC.md, Source: NBA.com 2026-27 season previews): ESPN id -> name
    "5104157": "Victor Wembanyama", "4278073": "Shai Gilgeous-Alexander", "3112335": "Nikola Jokić", "3945274": "Luka Dončić",
    "3934672": "Jalen Brunson", "3136195": "Karl-Anthony Towns", "3032977": "Giannis Antetokounmpo", "1966": "LeBron James",
    "3059318": "Joel Embiid", "3917376": "Jaylen Brown", "3908809": "Donovan Mitchell", "3992": "James Harden", "3975": "Stephen Curry",
    "3202": "Kevin Durant", "4594268": "Anthony Edwards", "4065648": "Jayson Tatum", "4279888": "Ja Morant", "6606": "Damian Lillard",
    "4277905": "Trae Young", "6583": "Anthony Davis", "4396993": "Tyrese Haliburton", "4395628": "Zion Williamson",
    "5041939": "Cooper Flagg", "4432166": "Cade Cunningham"}
TEAMS = {  # where each starts the season; the state keeps the latest team seen, so a trade is followed
    "5104157": "SAS", "4278073": "OKC", "3112335": "DEN", "3945274": "LAL", "3934672": "NYK", "3136195": "NYK", "3032977": "MIA", "1966": "PHI",
    "3059318": "PHI", "3917376": "PHI", "3908809": "CLE", "3992": "CLE", "3975": "GSW", "3202": "HOU", "4594268": "MIN", "4065648": "BOS",
    "4279888": "POR", "6606": "POR", "4277905": "WAS", "6583": "WAS", "4396993": "IND", "4395628": "NOP", "5041939": "DAL", "4432166": "DET"}
FIRST = ("LAL", "PHI", "CLE", "SAS", "BOS")  # D's teams: their games always come first, in this order; every other game follows by tip-off time
POINTS, BIG_REB, BLOCKS, STEALS = 40, 20, 5, 5   # standout thresholds
REBOUNDS, GUARD_REBOUNDS, ASSISTS = 15, 10, 15   # rebounds (10 for a guard, 15 for anyone else) and assists; D's choice, to be reviewed after a month of real use
GUARDS = ("G", "PG", "SG")                       # ESPN's box score lists positions as G, F or C
AUTO_HITS, AUTO_DAYS, AUTO_DROP_DAYS = 3, 30, 56  # three standouts in 30 days joins; eight weeks without one drops
CLUTCH_SECONDS = 5.0                       # a go-ahead score in the last five seconds of the fourth quarter or overtime is a game-winner
MAX_STANDOUTS = 5
TAGGED = ("triple-double", "20-20 game")   # kinds worth naming in a standout line; the points, blocks and steals show in the stat line itself
SERIES_GAMES = 7
CUP_SCAN = (date(2026, 10, 20), date(2026, 12, 20))   # the Cup's group stage and knockouts fall in this window; scanned once to learn the groups
CUP_HOME = ("Quarterfinals", "Semifinals")            # Cup rounds that are played in a home arena (group games and the final are not)


CODE_FIX = {"GS": "GSW", "NO": "NOP", "NY": "NYK", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS"}   # ESPN's odd team codes, made the standard NBA three letters


def code(abbr):
    return CODE_FIX.get(abbr, abbr)


NAME_FIX = {"LA Clippers": "Los Angeles Clippers"}   # ESPN calls only this team "LA"; every other team is City + nickname, so the Lakers' neighbour follows suit


def team_name(name):
    return NAME_FIX.get(name, name)


# ---- Games ----------------------------------------------------------------------------------------

def parse_game(e):
    """A game as plain data. status is 'final', 'live', 'scheduled' or 'other'. phase: 'regular', 'playin' or 'playoffs'; cup: the Cup round
    ('Group Play', 'Quarterfinals', ...) or None; headline: ESPN's note for the game ('East 1st Round - Game 3', 'NBA Cup - Group Play')."""
    c, t = e["competitions"][0], e["status"]["type"]
    status = "final" if t["name"] == "STATUS_FINAL" else {"in": "live", "pre": "scheduled"}.get(t["state"], "other")
    sides = {x["homeAway"]: x for x in c["competitors"]}
    side = lambda x: {"id": x["team"]["id"], "abbr": code(x["team"]["abbreviation"]), "name": team_name(x["team"]["displayName"]), "short": x["team"]["shortDisplayName"],  # noqa: E731
                      "score": int(x["score"]) if status in ("final", "live") and str(x.get("score", "")).isdigit() else None,
                      "record": next((rec["summary"] for rec in x.get("records", []) if rec.get("type", rec.get("name")) in ("total", "overall")), "")}
    headline = next((n.get("headline", "") for n in c.get("notes", [])), "")
    season_type = (e.get("season") or {}).get("type")
    playin = "play-in" in headline.lower() or "play in" in headline.lower()
    cup = None
    if headline.startswith("NBA Cup"):
        cup = headline.split(" - ", 1)[1] if " - " in headline else "Championship"
    series = c.get("series") or {}
    return {"id": e["id"], "date": utc(e["date"]), "status": status, "ot": status == "final" and (e["status"].get("period") or 0) > 4,
            "neutral": bool(c.get("neutralSite")), "detail": t.get("shortDetail", ""), "headline": headline, "cup": cup, "season": (e.get("season") or {}).get("year"),
            "phase": "playin" if playin else "playoffs" if season_type == 3 else "regular",
            "series": series.get("summary") if series.get("type") == "playoff" else None,
            "home": side(sides["home"]), "away": side(sides["away"])}


def winner(g):
    a, h = g["away"]["score"], g["home"]["score"]
    return None if a == h else ("away" if a > h else "home")


def day_of(g):
    return g["date"].astimezone(ET).date()


def underdog_win(g):
    return g["status"] == "final" and bool(g.get("dog")) and winner(g) == g["dog"]


def house(g):
    """The home-court icon matters only from the play-in on (and for the home Cup knockout rounds); never at a neutral site."""
    return not g["neutral"] and (g["phase"] in ("playin", "playoffs") or g["cup"] in CUP_HOME)


def order_key(g):
    """D's teams first (FIRST, in that order), then everyone else by tip-off time."""
    rank = [FIRST.index(t["abbr"]) for t in (g["away"], g["home"]) if t["abbr"] in FIRST]
    return (min(rank) if rank else len(FIRST), g["date"])


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
    prev, flip = 0, None
    for p in box["plays"]:
        diff = sign * (p["home"] - p["away"])
        if diff > 0 and prev <= 0:
            flip = p
        prev = diff
    if flip and flip["period"] >= 4 and seconds(flip["clock"]) <= CLUTCH_SECONDS:
        return flip
    return None


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
        mine = game["home"] if code(t["team"]) == game["home"]["abbr"] else game["away"]
        opp = game["away"] if mine is game["home"] else game["home"]
        for a in t["athletes"]:
            d = dict(zip(t["labels"], a["stats"]))
            played = not a["dnp"] and bool(a["stats"]) and num(d.get("MIN")) > 0
            out.append({"id": a["id"], "name": a["name"], "team": code(t["team"]), "opp": opp, "mine": mine, "game": game["id"], "dnp": not played,
                        "reason": (a.get("reason") or "").capitalize(), "starter": a["starter"], "pos": a.get("pos", ""),
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
    if p["REB"] >= (GUARD_REBOUNDS if p.get("pos") in GUARDS else REBOUNDS) and "triple-double" not in k and "20-20 game" not in k:
        k.append(f"{p['REB']} rebounds")
    if p["AST"] >= ASSISTS and "triple-double" not in k:
        k.append(f"{p['AST']} assists")
    if p["BLK"] >= BLOCKS:
        k.append(f"{p['BLK']} blocks")
    if p["STL"] >= STEALS:
        k.append(f"{p['STL']} steals")
    if p["id"] in deciding_ids:
        k.append("game-winner")
    return k


def weight(p, kinds=()):
    return p["PTS"] + 1.2 * p["REB"] + 1.5 * p["AST"] + 3 * p["STL"] + 3 * p["BLK"] + 8 * len(kinds)


def line(p):
    """'43 pts, 7 reb, 4 ast, 6 blk'; steals and blocks only when they are 2 or more."""
    bits = [f"{p['PTS']} pts", f"{p['REB']} reb", f"{p['AST']} ast"]
    bits += [f"{p[k]} {lab}" for k, lab in (("STL", "stl"), ("BLK", "blk")) if p[k] >= 2]
    return ", ".join(bits)


def full_line(p):
    return f"{p['name']} ({p['team']}): {line(p)} · {p['fg']}\u00a0FG"


def standout_text(p, kinds, games, plays):
    text = f"{p['name']} ({p['team']}): {line(p)}"
    if "game-winner" in kinds:
        clock = plays[p["game"]]["clock"]
        text += f", the game-winner with {clock}s left" if ":" not in clock else f", the game-winner with {clock} left"
    elif [k for k in kinds if k in TAGGED]:
        text += f" ({', '.join(k for k in kinds if k in TAGGED)})"
    return text


STAT_KEYS = (("PTS", "pts"), ("REB", "reb"), ("AST", "ast"), ("STL", "stl"), ("BLK", "blk"))


def marks_of(p, kinds):
    """Which parts of a standout line earned it, so they can be shown in colour: stat labels ('pts', 'stl', ...), 'tag' for a named tag such as
    triple-double, 'gw' for the game-winner. 40 points marks points; a triple-double marks each category of 10 or more; 5 steals marks steals."""
    m = set()
    if f"{POINTS}-point game" in kinds:
        m.add("pts")
    if "triple-double" in kinds:
        m |= {lab for key, lab in STAT_KEYS if p[key] >= 10}
    if "20-20 game" in kinds:
        m |= {"pts", "reb"}
    if any(k.endswith(" rebounds") for k in kinds):
        m.add("reb")
    if any(k.endswith(" assists") for k in kinds):
        m.add("ast")
    if p["BLK"] >= BLOCKS:
        m.add("blk")
    if p["STL"] >= STEALS:
        m.add("stl")
    if [k for k in kinds if k in TAGGED]:
        m.add("tag")
    if "game-winner" in kinds:
        m.add("gw")
    return m


def standout_html(text, marks):
    """A standout line as HTML with the marked parts (see marks_of) in the accent colour; the result after the ';' stays plain."""
    head, sep, tail = text.partition("; ")
    out = r.esc(head)
    for lab in ("pts", "reb", "ast", "stl", "blk"):
        if lab in marks:
            out = re.sub(rf"(\d+ {lab})\b", r'<span class="hl">\1</span>', out, count=1)
    if "tag" in marks:
        out = re.sub(r"(\((?:triple-double|20-20 game)[^)]*\))", r'<span class="hl">\1</span>', out, count=1)
    if "gw" in marks:
        out = re.sub(r"(the game-winner with [^;]*)$", r'<span class="hl">\1</span>', out, count=1)
    return out + (sep + r.esc(tail) if sep else "")


def standouts(players, games, boxes, limit=MAX_STANDOUTS):
    """The ranked standout lines, best first, and the hits as [(player id, game id)] for the auto-join count."""
    rows, hits = standouts_marked(players, games, boxes, limit)
    return [t for t, _ in rows], hits


def standouts_marked(players, games, boxes, limit=MAX_STANDOUTS):
    """The same as standouts(), but each line comes with its marks: [(text, marks)]."""
    plays, deciders = {}, {}
    for gid, g in games.items():
        pl = deciding_play(g, boxes.get(gid))
        if pl:
            plays[gid] = pl
            deciders[gid] = pl.get("athlete")
    found = []
    for p in players:
        kinds = kinds_of(p, {deciders[p["game"]]} if deciders.get(p["game"]) else ())
        if kinds:
            found.append((weight(p, kinds), p, kinds))
    found.sort(key=lambda x: (-x[0], x[1]["name"]))
    return [(standout_text(p, k, games, plays), marks_of(p, k)) for _, p, k in found[:limit]], [(p["id"], p["game"]) for _, p, _ in found]


def update_tracking(st, hits, names, day):
    """Auto-join and drop-off. hits: [(player id, game id)] for this run. Returns the tracked ids and writes st["auto"] / st["hits"]."""
    auto, record = {k: dict(v) for k, v in st.get("auto", {}).items()}, {k: list(v) for k, v in st.get("hits", {}).items()}
    today = day.isoformat()
    for pid, gid in hits:
        if gid not in [h[0] for h in record.get(pid, [])]:
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


def dnp_text(pid, name, team, box, p=None):
    """'LeBron James (PHI): DNP (Out, Knee)': ESPN's injury listing for the game, else the box score's own reason, else a plain DNP."""
    inj = (box or {}).get("injuries", {}).get(pid)
    if inj and inj.get("status"):
        reason = f"{inj['status']}, {inj['type']}" if inj.get("type") else inj["status"]
        return f"{name} ({team}): DNP ({reason})"
    if p and p.get("reason"):
        return f"{name} ({team}): DNP ({p['reason']})"
    return f"{name} ({team}): DNP"


def game_notes(g, box, players, tracked, info):
    """The lines under a game: each tracked player's stat line (best first), then the best performer of the game when he is not one of those, and
    last each tracked player of the two teams who did not play (DNP and the reason): the DNP lines always sit below every player who played. `players`: everyone in this game's box score;
    info: {"teams": latest team of each tracked player, "auto": names of the auto-added players}."""
    here = {p["id"]: p for p in players}
    mine = sorted((p for p in players if p["id"] in tracked and not p["dnp"]), key=lambda p: -weight(p, kinds_of(p)))
    out = [full_line(p) for p in mine]
    played = [p for p in players if not p["dnp"]]
    if played:
        best = max(played, key=lambda p: (weight(p, kinds_of(p)), p["name"]))
        if best["id"] not in {p["id"] for p in mine}:
            out.append(full_line(best))
    teams = {g["home"]["abbr"], g["away"]["abbr"]}
    for pid in sorted(tracked, key=lambda x: list(TRACKED).index(x) if x in TRACKED else 999):  # the DNP lines come last, below every player who played
        p = here.get(pid)
        if p and not p["dnp"]:
            continue
        if p or info["teams"].get(pid) in teams:
            out.append(dnp_text(pid, TRACKED.get(pid) or info["auto"].get(pid, pid), p["team"] if p else info["teams"][pid], box, p))
    return out


# ---- Rendering ----------------------------------------------------------------------------------

def note_html(text):
    """A note line as HTML: the numbers of pts, reb, ast, stl and blk in the accent colour."""
    return re.sub(r"(\d+) (pts|reb|ast|stl|blk)\b", r'<span class="n">\1</span> \2', r.esc(text))


GAME_COLOURS = 15   # one colour per game of the day (a full NBA night is at most 15 games); locked pastel palette, defined in the stylesheet as .gc0 to .gc14
PALETTE_DARK = ('#E3A6A0', '#C8EAB8', '#A0D0E3', '#E4B8EA', '#E3C1A0', '#B8EABC', '#A0B5E3', '#EAB8DC', '#E3DCA0', '#B8EAD0', '#A6A0E3', '#EAB8C8', '#D0E3A0', '#B8EAE4', '#C1A0E3')    # on the dark theme (soft pastels)
PALETTE_LIGHT = ('#783B36', '#4B7836', '#366578', '#703678', '#785636', '#36783B', '#364B78', '#783665', '#787036', '#367856', '#3B3678', '#78364B', '#657836', '#367870', '#563678')   # on the light theme (the same hues, muted and deeper so they read on a pale page)


def game_colours(games):
    """{team code: colour number}: the games shown above, in their order, each get a colour and both of its teams share it."""
    out = {}
    for i, g in enumerate(games):
        out[g["away"]["abbr"]] = out[g["home"]["abbr"]] = i % GAME_COLOURS
    return out


def paint(html, colours):
    """Colour the team codes in a standings or Cup table that played in tonight's games: the code is wrapped in a coloured span, nothing else changes."""
    for abbr, n in colours.items():
        html = html.replace(f'<td class="">{abbr}</td>', f'<td class=""><span class="gc{n}">{abbr}</span></td>')
    return html


def day_label(d):
    return f"{d:%a} {d.day} {d:%b}"


def tag_text(g, many_days):
    """The small line above a game: its day (when the games span two), the Cup round or playoff note."""
    bits = []
    if many_days:
        bits.append(day_label(day_of(g)))
    if g["status"] == "live":
        bits.append("In progress" + (f" · {g['detail']}" if g.get("detail") else ""))
    if g["cup"]:
        bits.append("NBA Cup" if g["cup"] == "Championship" else f"NBA Cup · {g['cup']}")
    elif g["headline"]:
        bits.append(g["headline"].replace(" - ", " · "))
    return " · ".join(bits)


def game_rows(g, notes, many_days):
    w = winner(g)
    star = DOG if underdog_win(g) else ""
    a, h = g["away"], g["home"]
    score = f'{a["score"]}–{h["score"]}' + (" OT" if g["ot"] else "")
    if g["status"] == "live":
        w = None
    icon = f" {HOME_SVG}" if house(g) else ""
    tag = tag_text(g, many_days)
    rows = [f'<tr class="tag"><td colspan="3">{r.esc(tag)}</td></tr>'] if tag else []
    cls = "one" + ("" if notes else " end")
    rows.append(f'<tr class="{cls}"><td class="aw{" w" if w == "away" else ""}">{r.esc(a["name"])}{star if w == "away" else ""}</td>'
                f'<td class="mid">{score}</td><td class="hm{" w" if w == "home" else ""}">{r.esc(h["name"])}{star if w == "home" else ""}{icon}</td></tr>')
    if notes:
        rows.append('<tr class="note end"><td colspan="3">' + "".join(f'<div class="pl"><span class="t">{note_html(x)}</span></div>' for x in notes) + "</td></tr>")
    return rows


def games_html(items, many_days, dogs):
    """items: [(game, notes)] already in order. One table titled Last Night's Games; the underdog count sits under the title."""
    rows = [x for g, notes in items for x in game_rows(g, notes, many_days)]
    sub = f'<span class="prog">{DOG} {dogs} underdog win{"s" if dogs != 1 else ""}</span>' if dogs else ""
    return (f'<div class="nflsb nbaone"><table><colgroup><col style="width:35%"><col style="width:30%"><col style="width:35%"></colgroup>'
            f'<thead><tr><th class="tt" colspan="3">Last Night\'s Games{sub}</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def _list(items):
    return '<ul class="standouts">' + "".join(f"<li>{r.esc(i)}</li>" for i in items) + "</ul>" if items else ""


def move(n):
    return "–" if not n else (f"▲{n}" if n > 0 else f"▼{-n}")


def standings_ok(std):
    return bool(std) and len(std.get("children", [])) == 2 and all(len(c.get("standings", {}).get("entries", [])) >= 15 for c in std["children"])


def _stat(e, name):
    return next((s["displayValue"] for s in e["stats"] if s["name"] == name), "")


def seeds_of(std):
    """{conference name: {team code: seed}}."""
    return {c["name"]: {code(e["team"]["abbreviation"]): num(_stat(e, "playoffSeed")) for e in c["standings"]["entries"]} for c in std["children"]}


def standings_html(std, before=None):
    """Both conferences by playoff seed: blue for the top six, lilac for the play-in places (7 to 10). +/- is the places moved since the last
    table that was shown (`before`, from seeds_of); no arrows the first time."""
    out = ""
    for c in std["children"]:
        rows, zones = [], []
        prev = (before or {}).get(c["name"])
        for e in sorted(c["standings"]["entries"], key=lambda e: num(_stat(e, "playoffSeed")) or 99):
            seed, abbr = num(_stat(e, "playoffSeed")), code(e["team"]["abbreviation"])
            rows.append([seed, abbr, _stat(e, "overall"), _stat(e, "gamesBehind") if seed > 1 else "-", _stat(e, "streak"),
                         move(prev[abbr] - seed) if prev and abbr in prev else ""])
            zones.append("blue" if seed <= 6 else "lilac" if seed <= 10 else None)
        out += r.compact(r.table(c["name"], [("#", True), ("Team", False), ("W-L", True), ("GB", True), ("Strk", True), ("+/-", True)], rows, zones=zones),
                         (10, 22, 20, 16, 16, 16), " nba")
    return out


# ---- NBA Cup ----------------------------------------------------------------------------------------

def cup_groups(games):
    """The Cup groups, learned from who plays whom in group games: [sorted team codes] (each is a connected set of five). games: {id: [away, home, ...]}."""
    adj = {}
    for a, h, *_ in games.values():
        adj.setdefault(a, set()).add(h)
        adj.setdefault(h, set()).add(a)
    seen, out = set(), []
    for t in sorted(adj):
        if t in seen:
            continue
        stack, comp = [t], set()
        while stack:
            x = stack.pop()
            if x not in comp:
                comp.add(x)
                stack += adj[x]
        seen |= comp
        out.append(sorted(comp))
    return out


def cup_table(group, games):
    """Rows [(team, wins, losses, point difference)] best first: wins, then point difference (the NBA's longer tie-break list is not modelled)."""
    rec = {t: [0, 0, 0] for t in group}
    for a, h, sa, sh, *_ in games.values():
        if a in rec and h in rec and sa is not None and sh is not None:
            for t, mine, theirs in ((a, sa, sh), (h, sh, sa)):
                rec[t][0 if mine > theirs else 1] += 1
                rec[t][2] += mine - theirs
    return sorted(((t, *v) for t, v in rec.items()), key=lambda x: (-x[1], -x[3], x[0]))


def cup_html(groups, games, conf_of):
    """Six group tables (three East, three West). Blue marks each group's leader and lilac the best runner-up in the conference (together the
    four teams per conference in position to reach the quarter-finals)."""
    by_conf = {}
    for g in groups:
        by_conf.setdefault(conf_of.get(g[0], "Groups"), []).append(g)
    out = ""
    for conf in sorted(by_conf):
        tables = [cup_table(g, games) for g in sorted(by_conf[conf])]
        played = lambda row: row[1] + row[2] > 0  # noqa: E731  (nobody is "in position" before a game has been played)
        wildcard = max((t[1] for t in tables if len(t) > 1 and played(t[1])), key=lambda x: (x[1], x[3]), default=None)
        for i, rows in enumerate(tables, 1):
            body = [[t, f"{w}-{l}", f"{pd:+d}" if pd else "0"] for t, w, l, pd in rows]
            zones = ["blue" if j == 0 and played(rows[0]) else "lilac" if wildcard and rows[j][0] == wildcard[0] else None for j in range(len(rows))]
            out += r.compact(r.table(f"{conf} Cup Group {i}", [("Team", False), ("W-L", True), ("PD", True)], body, zones=zones), (40, 30, 30), " nba")
    return out


# ---- Playoff series ----------------------------------------------------------------------------------

def series_of(g):
    return frozenset((g["home"]["id"], g["away"]["id"]))


def seeds_by_team(std):
    """{team code: playoff seed} across both conferences, from a standings feed."""
    return {abbr: seed for conf in seeds_of(std).values() for abbr, seed in conf.items()}


def series_html(g0, sched, notes_by_game, seeds=None):
    """One table for one series: the two teams as headers with their series wins beside them, then SERIES_GAMES rows made in advance: the
    game number and date, the score once played (winner in bold) with the player notes under it, 'if necessary' for games not yet scheduled.
    g0: a game of the series (names and round); sched: the series' games (schedule rows)."""
    games = sorted(sched, key=lambda x: x["date"])
    top = games[0]["home"] if games else g0["home"]            # the team that hosted game 1 (the higher seed) is the first column
    bot = games[0]["away"] if games else g0["away"]
    wins = {top["id"]: 0, bot["id"]: 0}
    for x in games:
        if x["status"] == "STATUS_FINAL" and x["home"]["score"] is not None:
            wins[x["home"]["id"] if x["home"]["score"] > x["away"]["score"] else x["away"]["id"]] += 1
    over = max(wins.values()) >= 4
    rnd = re.sub(r" - Game \d+$", "", g0["headline"])
    rows = []
    for n in range(1, SERIES_GAMES + 1):
        x = games[n - 1] if n <= len(games) else None
        if x and x["status"] == "STATUS_FINAL":
            sc = {x["home"]["id"]: x["home"]["score"], x["away"]["id"]: x["away"]["score"]}
            lw = "w" if sc[top["id"]] > sc[bot["id"]] else ""
            rw = "w" if sc[bot["id"]] > sc[top["id"]] else ""
            d = utc(x["date"]).astimezone(ET).date()
            note = notes_by_game.get(x["id"], [])
            rows.append(f'<tr class="one{"" if note else " end"}"><td class="aw {lw}">{sc[top["id"]]}</td><td class="mid">G{n} · {day_label(d)}</td><td class="hm {rw}">{sc[bot["id"]]}</td></tr>')
            if note:
                rows.append('<tr class="note end"><td colspan="3">' + "".join(f'<div class="pl"><span class="t">{note_html(t)}</span></div>' for t in note) + "</td></tr>")
        elif x and "IN_PROGRESS" in x["status"] and x["home"]["score"] is not None:   # on now: the score so far, and the game is shown final next edition
            sc = {x["home"]["id"]: x["home"]["score"], x["away"]["id"]: x["away"]["score"]}
            rows.append(f'<tr class="one end"><td class="aw">{sc[top["id"]]}</td><td class="mid">G{n} · In progress</td><td class="hm">{sc[bot["id"]]}</td></tr>')
        else:
            if x:
                when = utc(x["date"]).astimezone(SGT)
                mid = f"G{n} · {when:%a} {when.day} {when:%b}, {when:%-I:%M%p}".replace("AM", "am").replace("PM", "pm") + " SGT"
            else:
                mid = f"G{n} · " + ("–" if over else "if necessary" if n >= 5 else "to be scheduled")
            rows.append(f'<tr class="one end pre"><td class="mid" colspan="3">{r.esc(mid)}</td></tr>')
    seed = lambda t: (seeds or {}).get(t["abbr"])  # noqa: E731
    left = (f'({seed(top)})\u00a0' if seed(top) else "") + team_name(top.get("name", top["short"]))
    right = team_name(bot.get("name", bot["short"])) + (f'\u00a0({seed(bot)})' if seed(bot) else "")
    head = (f'<tr><th class="tt" colspan="3">{r.esc(rnd)}</th></tr>'
            f'<tr class="sh"><th class="aw" colspan="3"><span class="tn">{r.esc(left)}</span><span class="tn r">{r.esc(right)}</span></th></tr>'
            f'<tr class="sc"><th colspan="3"><span class="ws">{wins[top["id"]]}</span><span class="lab">series</span><span class="ws">{wins[bot["id"]]}</span></th></tr>')
    return (f'<div class="nflsb nbaone ser"><table><colgroup><col style="width:30%"><col style="width:40%"><col style="width:30%"></colgroup>'
            f'<thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div>')


# ---- The run ------------------------------------------------------------------------------------

def run(now, day, st, source):
    """{"html", "state", "stats"}. now: UTC; day: the edition's date in Singapore; st: {"reported", "auto", "hits", "dogs", "teams", "seeds", "cup_games",
    "series_notes"}. A failing source never raises: that part is left out and counted in stats["failed"]."""
    stats = {"games": 0, "new": 0, "boxes": 0, "failed": 0, "standouts": 0, "series": 0, "cup_new": 0, "live": 0, "calls": 0}
    reported, dogs = list(st.get("reported", [])), dict(st.get("dogs", {}))
    keep = {"reported": reported, "auto": st.get("auto", {}), "hits": st.get("hits", {}), "dogs": dogs, "teams": dict(TEAMS, **st.get("teams", {})),
            "seeds": st.get("seeds"), "cup_games": dict(st.get("cup_games", {})), "series_notes": dict(st.get("series_notes", {}))}
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
    # NBA Cup: learn the groups once from the whole window, then keep each group game's result in the state
    cup_games = keep["cup_games"]
    if not cup_games and CUP_SCAN[0] <= today <= CUP_SCAN[1]:
        d = CUP_SCAN[0]
        while d <= CUP_SCAN[1]:
            try:
                for e in source.scoreboard(d).get("events", []):
                    g = parse_game(e)
                    if g["cup"] == "Group Play":
                        cup_games[g["id"]] = [g["away"]["abbr"], g["home"]["abbr"], g["away"]["score"], g["home"]["score"]]
            except Exception:                              # the source is down: one failure, not sixty
                stats["failed"] += 1
                break
            d += timedelta(days=1)
    for g in games.values():
        if g["cup"] == "Group Play":
            cup_games[g["id"]] = [g["away"]["abbr"], g["home"]["abbr"], g["away"]["score"], g["home"]["score"]]
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
    players = {g["id"]: players_of(boxes[g["id"]], g) for g in new}
    flat = [p for ps in players.values() for p in ps]
    names = {p["id"]: p["name"] for p in flat}
    rows, hits = standouts_marked(flat, by_id, boxes)
    texts = [t for t, _ in rows]
    tracked = update_tracking(keep, hits, names, day)
    for p in flat:                                         # the latest team of every tracked player (a trade is followed)
        if p["id"] in tracked:
            keep["teams"][p["id"]] = p["team"]
    stats["standouts"] = len(texts)
    info = {"teams": keep["teams"], "auto": {k: v["name"] for k, v in keep["auto"].items()}}
    html = ""
    colours = {}
    live = [g for g in games.values() if g["status"] == "live"]   # on now: shown with the score so far, and as a final in the next edition
    stats["live"] = len(live)
    playoff_new = [g for g in new + live if g["phase"] == "playoffs"]
    plain = [g for g in new if g["phase"] != "playoffs"]
    plain_live = [g for g in live if g["phase"] != "playoffs"]
    if plain or plain_live:
        many_days = len({day_of(g) for g in plain + plain_live}) > 1
        items = [(g, game_notes(g, boxes[g["id"]], players[g["id"]], tracked, info) if g["id"] in boxes else []) for g in sorted(plain + plain_live, key=order_key)]
        html += games_html(items, many_days, sum(1 for g in plain + plain_live if underdog_win(g)))
        colours = game_colours([g for g, _ in items])
    if playoff_new:                                         # one table per series that had a game finish (or is on now)
        seeds = {}
        try:                                                # the regular-season seeds of the two teams go beside their names
            seeds = seeds_by_team(source.standings(playoff_new[0]["season"]))
        except Exception:
            stats["failed"] += 1
        done = {}
        for g in sorted(playoff_new, key=order_key):
            done.setdefault(series_of(g), g)
        for key, g0 in done.items():
            try:
                sched = source.schedule(g0["home"]["id"], g0["season"])
            except Exception:
                stats["failed"] += 1
                continue
            sched = [{**x, "home": {**x["home"], "abbr": code(x["home"]["abbr"])}, "away": {**x["away"], "abbr": code(x["away"]["abbr"])}}
                     for x in sched if {x["home"]["id"], x["away"]["id"]} == set(key)]
            for x in sched:                                 # notes for every finished game of the series, kept in the state once made
                if x["status"] != "STATUS_FINAL" or x["id"] in keep["series_notes"]:
                    continue
                if x["id"] in boxes:
                    bx, gg = boxes[x["id"]], by_id[x["id"]]
                else:
                    try:
                        bx = source.box(x["id"])
                    except Exception:
                        stats["failed"] += 1
                        continue
                    gg = {"id": x["id"], "home": dict(x["home"]), "away": dict(x["away"]), "ot": False,
                          "status": "final", "phase": "playoffs", "cup": None, "headline": x["headline"], "neutral": False}
                keep["series_notes"][x["id"]] = game_notes(gg, bx, players_of(bx, gg), tracked, info)
            html += series_html(g0, sched, keep["series_notes"], seeds)
            stats["series"] += 1
    if texts:
        html += "<h4>Standouts</h4>" + '<ul class="standouts">' + "".join(f"<li>{standout_html(t, m)}</li>" for t, m in rows) + "</ul>"
    std = None
    playoffs_on = any(g["phase"] == "playoffs" for g in games.values())   # once the playoffs are on, the regular-season tables are not needed
    if (games or new) and not playoffs_on:                  # the standings come every day there is basketball until then
        try:
            std = source.standings()
        except Exception:
            stats["failed"] += 1
    cup_new = [g for g in new + live if g["cup"] == "Group Play"]
    stats["cup_new"] = len(cup_new)
    conf_of = {}
    if std and standings_ok(std):
        html += "<h4>Standings</h4>" + paint(standings_html(std, keep["seeds"]), colours)
        keep["seeds"] = seeds_of(std)
        conf_of = {t: c.replace(" Conference", "") for c, ts in keep["seeds"].items() for t in ts}
    if cup_games and cup_new:                               # the Cup tables come only on days Cup group games are in the edition
        html += "<h4>NBA Cup</h4>" + paint(cup_html(cup_groups(cup_games), cup_games, conf_of), colours)
    if new:
        reported += [g["id"] for g in new]
    keep["reported"] = reported[-400:]
    keep["series_notes"] = dict(list(keep["series_notes"].items())[-120:])
    stats["calls"] = getattr(source, "calls", 0)
    return {"html": html, "state": keep, "stats": stats}
