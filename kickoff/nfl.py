"""NFL: the week's scoreboard, weekly leaders by position group, highlights, a computed Player of the Week, division tables and (from week 14)
the playoff picture. All by code from exact data, so no Claude cost.

Edition rhythm (the edition's Singapore weekday decides the extras; new games are always shown as they finish):
  Mon  Sunday's games, weekly leaders so far, highlights.   Tue  the Sunday-night game and any others, highlights.
  Wed  the whole week's scoreboard, weekly leaders again (late-game entries marked "new", or a line saying nothing changed), highlights of the
       Monday-night game, Player of the Week, division tables and, from week 14, the playoff picture.   Sat  Thursday night's game.
Which games are new is decided by the state ({"reported": [game ids]}), not the clock, so nothing is lost or shown twice."""
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from kickoff import render as r

ET = ZoneInfo("America/New_York")
HOME = "🏠"
MINE = {"JAX", "PIT"}                      # D's teams: the Jaguars and the Steelers
LOOKBACK = timedelta(days=6)
PLAYOFF_PICTURE_FROM = 14                  # week of the regular season
POST_ROUNDS = {1: "Wild Card Round", 2: "Divisional Round", 3: "Conference Championships", 5: "Super Bowl"}
NEW_MARK = "⁠NEW"                     # becomes a small "new" tag after the table is built (cell text is escaped)
MIN_PASS_ATTEMPTS = 15                     # for the weekly passer-rating list
RB_POS, WR_POS, TE_POS = ("RB", "FB"), ("WR",), ("TE",)
RUSH_POS = ("DE", "DT", "LB", "OLB", "ILB", "MLB", "EDGE", "NT", "DL")
BACK_POS = ("CB", "S", "FS", "SS", "DB")
KICK_POS = ("K", "PK")


def utc(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


# ---- Numbers from the box score -------------------------------------------------------------------

def num(v):
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return 0.0


def pair(v):
    """'10/21' or '3-15' -> (10, 21); anything else (0, 0)."""
    m = re.match(r"\s*(\d+)\s*[/-]\s*(\d+)", str(v))
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def passer_rating(comp, att, yds, td, ints):
    """The NFL passer rating (0 to 158.3)."""
    if att == 0:
        return 0.0
    cap = lambda x: max(0.0, min(2.375, x))  # noqa: E731
    return (cap((comp / att - 0.3) * 5) + cap((yds / att - 3) * 0.25) + cap(td / att * 20) + cap(2.375 - ints / att * 25)) / 6 * 100


def stat(p, cat, label):
    return (p["stats"].get(cat) or {}).get(label, "-")


def n(p, cat, label):
    return num(stat(p, cat, label))


def players_of(box, positions, game_id=None):
    """Every player in a box score as one record: {id, name, short, team, pos, game, stats: {category: {label: value}}}."""
    out = []
    for side in box["players"]:
        by = {}
        for cat in side["statistics"]:
            for a in cat["athletes"]:
                ath = a["athlete"]
                first, last = (ath.get("firstName") or "").strip(), (ath.get("lastName") or "").strip()
                p = by.setdefault(ath["id"], {"id": ath["id"], "name": ath["displayName"], "game": game_id, "team": side["team"]["abbreviation"],
                                              "short": f"{first[0]}. {last}" if first and last else ath["displayName"], "pos": positions.get(ath["id"]), "stats": {}})
                p["stats"][cat["name"]] = dict(zip(cat["labels"], a["stats"]))
        out += by.values()
    return out


def unknown_ids(box, positions):
    """Athletes in the box score whose position is not known yet, by team id."""
    out = {}
    for side in box["players"]:
        for cat in side["statistics"]:
            for a in cat["athletes"]:
                if a["athlete"]["id"] not in positions:
                    out.setdefault(side["team"]["id"], set()).add(a["athlete"]["id"])
    return out


# ---- Games ----------------------------------------------------------------------------------------

def parse_game(e):
    """A game as plain data. status is 'final', 'live', 'scheduled' or 'other' (postponed and so on)."""
    c, t = e["competitions"][0], e["status"]["type"]
    status = "final" if t["name"] == "STATUS_FINAL" else {"in": "live", "pre": "scheduled"}.get(t["state"], "other")
    sides = {x["homeAway"]: x for x in c["competitors"]}
    side = lambda x: {"id": x["team"]["id"], "abbr": x["team"]["abbreviation"], "name": x["team"]["displayName"], "short": x["team"]["shortDisplayName"],  # noqa: E731
                      "score": int(x["score"]) if status in ("final", "live") and str(x.get("score", "")).isdigit() else None,
                      "record": next((rec["summary"] for rec in x.get("records", []) if rec.get("name") == "overall"), "")}
    names = [nm for b in c.get("broadcasts", []) for nm in b.get("names", [])]
    return {"id": e["id"], "date": utc(e["date"]), "week": e["week"]["number"], "status": status, "ot": status == "final" and (e["status"].get("period") or 0) > 4,
            "neutral": bool(c.get("neutralSite")), "broadcast": names[0] if names else "", "home": side(sides["home"]), "away": side(sides["away"])}


def slot(g):
    """The kickoff group a game belongs to: its day (US Eastern) and part of the day. Games in the same group sit together; a line separates groups."""
    et = g["date"].astimezone(ET)
    h = et.hour + et.minute / 60
    return (et.date().isoformat(), "morning" if h < 11 else "early" if h < 14.5 else "late" if h < 18 else "night")


def winner(g):
    a, h = g["away"]["score"], g["home"]["score"]
    return None if a == h else ("away" if a > h else "home")


def week_name(week, season_type):
    return POST_ROUNDS.get(week, f"Playoffs {week}") if season_type == 3 else f"Week {week}"


# ---- Scoreboard -----------------------------------------------------------------------------------

def scoreboard_html(games, title, played, total, byes=()):
    """Two rows per game (away above home), the home team marked with a house, the winner in bold, a thicker line between kickoff groups."""
    if not games:
        return ""
    rows, prev = [], None
    for g in sorted(games, key=lambda g: g["date"]):
        if prev is not None and slot(g) != prev:
            rows.append('<tr class="gap"><td></td><td></td><td></td></tr>')
        prev, w = slot(g), winner(g)
        for side in ("away", "home"):
            t = g[side]
            mark = f' <span class="home">{HOME}</span>' if side == "home" and not g["neutral"] else ""
            cls = " ".join(x for x in (side[0], "w" if w == side else "", "mine" if t["abbr"] in MINE else "") if x)
            ot = '<span class="muted">OT</span>' if g["ot"] and side == "away" else ""
            rec = f' <span class="rec">{r.esc(t["record"])}</span>' if t["record"] else ""
            rows.append(f'<tr class="{cls}"><td class="tm">{r.esc(t["short"])}{mark}{rec}</td><td class="sc">{t["score"]}</td><td class="ot">{ot}</td></tr>')
    sub = f'<span class="prog">{played}/{total} games played</span>' if total else ""
    html = (f'<div class="nflsb"><table><colgroup><col style="width:68%"><col style="width:16%"><col style="width:16%"></colgroup>'
            f'<thead><tr><th class="tt" colspan="3">{r.esc(title)}{sub}</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
    if byes:
        html += f'<p class="muted">On bye: {r.esc(", ".join(byes))}.</p>'
    return html


# ---- Weekly leaders -------------------------------------------------------------------------------

def _top(players, pool, key, qualifies=lambda p: True, k=3):
    return sorted([p for p in players if p["pos"] in pool and qualifies(p)], key=key, reverse=True)[:k]


def top_qbs(players):
    rating = lambda p: passer_rating(pair(stat(p, "passing", "C/ATT"))[0], pair(stat(p, "passing", "C/ATT"))[1], n(p, "passing", "YDS"), n(p, "passing", "TD"), n(p, "passing", "INT"))  # noqa: E731
    return _top(players, ("QB",), lambda p: (rating(p), n(p, "passing", "YDS")), lambda p: pair(stat(p, "passing", "C/ATT"))[1] >= MIN_PASS_ATTEMPTS)


def top_rbs(players):
    return _top(players, RB_POS, lambda p: (n(p, "rushing", "YDS"), n(p, "rushing", "TD")), lambda p: n(p, "rushing", "CAR") > 0)


def top_wrs(players):
    return _top(players, WR_POS, lambda p: (n(p, "receiving", "YDS"), n(p, "receiving", "TD")), lambda p: n(p, "receiving", "REC") > 0)


def top_tes(players):
    return _top(players, TE_POS, lambda p: (n(p, "receiving", "YDS"), n(p, "receiving", "TD")), lambda p: n(p, "receiving", "REC") > 0)


def top_rushers(players):
    return _top(players, RUSH_POS, lambda p: (n(p, "defensive", "SACKS"), n(p, "defensive", "TFL"), n(p, "defensive", "QB HTS"), n(p, "defensive", "TOT")),
                lambda p: n(p, "defensive", "SACKS") > 0)


def top_backs(players):
    return _top(players, BACK_POS, lambda p: (n(p, "interceptions", "INT"), n(p, "defensive", "PD"), n(p, "defensive", "TOT")),
                lambda p: n(p, "interceptions", "INT") > 0 or n(p, "defensive", "PD") >= 2)


def top_kickers(players):
    return _top(players, KICK_POS, lambda p: (pair(stat(p, "kicking", "FG"))[0], n(p, "kicking", "LONG"), n(p, "kicking", "PTS")), lambda p: pair(stat(p, "kicking", "FG"))[1] > 0)


def returns(p):
    """(yards, touchdowns) over kick and punt returns."""
    return (n(p, "kickReturns", "YDS") + n(p, "puntReturns", "YDS"), n(p, "kickReturns", "TD") + n(p, "puntReturns", "TD"))


def best_returner(players):
    got = sorted([p for p in players if returns(p)[0] > 0], key=lambda p: (returns(p)[1], returns(p)[0]), reverse=True)
    return got[0] if got else None


def best_punter(players, min_punts=3):
    got = sorted([p for p in players if p["pos"] == "P" and n(p, "punting", "NO") >= min_punts], key=lambda p: (n(p, "punting", "AVG"), n(p, "punting", "In 20")), reverse=True)
    return got[0] if got else None


def _name(p, new):
    return p["short"] + (NEW_MARK if p["id"] in new else "")


def _tag(html):
    return html.replace(NEW_MARK, ' <span class="new">new</span>')


def _board(title, cols, widths, rows, mine, extra=" nfl"):
    classes = ["mine" if t in MINE else "" for t in mine]
    return _tag(r.compact(r.table(title, cols, rows, row_classes=classes), widths, extra))


def _rating(p):
    c, a = pair(stat(p, "passing", "C/ATT"))
    return passer_rating(c, a, n(p, "passing", "YDS"), n(p, "passing", "TD"), n(p, "passing", "INT"))


GROUPS = ("qb", "rb", "wr", "te", "rush", "back", "kick")


def leaders(players):
    """{group: top players} for the seven position groups, plus 'ret' and 'punt' for the best returner and punter."""
    return {"qb": top_qbs(players), "rb": top_rbs(players), "wr": top_wrs(players), "te": top_tes(players), "rush": top_rushers(players),
            "back": top_backs(players), "kick": top_kickers(players)}


def leader_ids(lead):
    return {g: [p["id"] for p in lead[g]] for g in GROUPS}


def leaders_html(lead, players, new=frozenset()):
    """The seven top-three tables, then the best returner and punter."""
    ctx = lambda ps: [p["team"] for p in ps]  # noqa: E731
    html = ""
    qb = lead["qb"]
    html += _board("Top QBs · Passer Rating", [("#", True), ("Player", False), ("Tm", False), ("C/ATT", True), ("YDS", True), ("TD-INT", True), ("RTG", True)], (5, 31, 8, 14, 10, 14, 18),
                   [[i + 1, _name(p, new), p["team"], stat(p, "passing", "C/ATT"), int(n(p, "passing", "YDS")), f"{int(n(p, 'passing', 'TD'))}-{int(n(p, 'passing', 'INT'))}", f"{_rating(p):.1f}"] for i, p in enumerate(qb)], ctx(qb)) if qb else ""
    rb = lead["rb"]
    html += _board("Top RBs · Rushing", [("#", True), ("Player", False), ("Tm", False), ("CAR", True), ("YDS", True), ("AVG", True), ("TD", True)], (6, 31, 10, 13, 14, 13, 13),
                   [[i + 1, _name(p, new), p["team"], int(n(p, "rushing", "CAR")), int(n(p, "rushing", "YDS")), stat(p, "rushing", "AVG"), int(n(p, "rushing", "TD"))] for i, p in enumerate(rb)], ctx(rb)) if rb else ""
    for key, title in (("wr", "Top WRs · Receiving"), ("te", "Top TEs · Receiving")):
        ps = lead[key]
        html += _board(title, [("#", True), ("Player", False), ("Tm", False), ("REC", True), ("YDS", True), ("TD", True), ("LNG", True)], (6, 31, 10, 13, 14, 13, 13),
                       [[i + 1, _name(p, new), p["team"], int(n(p, "receiving", "REC")), int(n(p, "receiving", "YDS")), int(n(p, "receiving", "TD")), int(n(p, "receiving", "LONG"))] for i, p in enumerate(ps)], ctx(ps)) if ps else ""
    ps = lead["rush"]
    html += _board("Top Pass Rushers · Sacks", [("#", True), ("Player", False), ("Pos", False), ("Tm", False), ("SACK", True), ("TFL", True), ("QBH", True)], (5, 28, 10, 11, 15, 14, 17),
                   [[i + 1, _name(p, new), p["pos"], p["team"], f"{n(p, 'defensive', 'SACKS'):g}", f"{n(p, 'defensive', 'TFL'):g}", int(n(p, "defensive", "QB HTS"))] for i, p in enumerate(ps)], ctx(ps)) if ps else ""
    ps = lead["back"]
    html += _board("Top Secondary · Interceptions", [("#", True), ("Player", False), ("Pos", False), ("Tm", False), ("INT", True), ("PD", True), ("TOT", True)], (5, 28, 10, 11, 15, 14, 17),
                   [[i + 1, _name(p, new), p["pos"], p["team"], int(n(p, "interceptions", "INT")), int(n(p, "defensive", "PD")), int(n(p, "defensive", "TOT"))] for i, p in enumerate(ps)], ctx(ps)) if ps else ""
    ps = lead["kick"]
    html += _board("Top Special Teams · Kickers", [("#", True), ("Player", False), ("Tm", False), ("FG", True), ("LNG", True), ("PTS", True)], (6, 34, 10, 16, 16, 18),
                   [[i + 1, _name(p, new), p["team"], stat(p, "kicking", "FG"), int(n(p, "kicking", "LONG")), int(n(p, "kicking", "PTS"))] for i, p in enumerate(ps)], ctx(ps)) if ps else ""
    lines = []
    ret, pt = best_returner(players), best_punter(players)
    if ret:
        y, td = returns(ret)
        lines.append(f"Returner: {ret['short']} ({ret['team']}), {int(y)} return yards" + (f" and {int(td)} touchdown{'s' if td > 1 else ''}" if td else "") + ".")
    if pt:
        lines.append(f"Punter: {pt['short']} ({pt['team']}), {stat(pt, 'punting', 'AVG')} yards a punt on {int(n(pt, 'punting', 'NO'))} punts, {int(n(pt, 'punting', 'In 20'))} inside the 20.")
    return html + _list(lines)


# ---- Highlights and Player of the Week ------------------------------------------------------------

def points(p):
    """The score that ranks highlights and picks the Player of the Week: fantasy-style offence, with defence and special teams weighted up so
    they can compete. Easy to change; D wants to see it for a few weeks first."""
    pts = n(p, "passing", "YDS") * 0.04 + n(p, "passing", "TD") * 4 - n(p, "passing", "INT") * 2
    pts += (n(p, "rushing", "YDS") + n(p, "receiving", "YDS")) * 0.1 + (n(p, "rushing", "TD") + n(p, "receiving", "TD")) * 6 + n(p, "receiving", "REC") * 0.5
    pts -= n(p, "fumbles", "LOST") * 2
    pts += n(p, "defensive", "SACKS") * 5 + n(p, "interceptions", "INT") * 6 + n(p, "defensive", "PD") * 1.5 + n(p, "defensive", "TFL") * 1.5
    pts += n(p, "defensive", "QB HTS") + (n(p, "defensive", "TD") + n(p, "interceptions", "TD")) * 8
    made, _ = pair(stat(p, "kicking", "FG"))
    pts += made * 3 + (2 if n(p, "kicking", "LONG") >= 50 and made else 0) + returns(p)[1] * 8
    return round(pts, 1)


def _result(p, games):
    """'in the 43-36 win over TEN' for a player's game."""
    g = games[p["game"]]
    mine, theirs = (g["home"], g["away"]) if g["home"]["abbr"] == p["team"] else (g["away"], g["home"])
    hi, lo = max(mine["score"], theirs["score"]), min(mine["score"], theirs["score"])
    verb = "tie with" if hi == lo else ("win over" if mine["score"] > theirs["score"] else "loss to")
    return f"in the {hi}-{lo} {verb} {theirs['abbr']}"


def _s(x, one, many=None):
    x = int(x)
    return f"{x} {one}" if x == 1 else f"{x} {many or one + 's'}"


def standout_text(p, kinds, games):
    """One line of context for a player who met a threshold. `kinds` are the thresholds met: 'pass', 'rush', 'rb', 'rec', 'def', 'st'."""
    parts = []
    if "pass" in kinds:
        c, a = pair(stat(p, "passing", "C/ATT"))
        parts.append(f"{c}/{a} for {int(n(p, 'passing', 'YDS'))} yards, {_s(n(p, 'passing', 'TD'), 'touchdown')} and {_s(n(p, 'passing', 'INT'), 'interception')}")
    if "rush" in kinds or "rb" in kinds:
        parts.append(f"{int(n(p, 'rushing', 'YDS'))} rushing yards on {_s(n(p, 'rushing', 'CAR'), 'carry', 'carries')}")
    if "rb" in kinds and (n(p, "rushing", "TD") + n(p, "receiving", "TD")) >= 1:
        parts.append(_s(n(p, "rushing", "TD") + n(p, "receiving", "TD"), "touchdown"))
    if "rec" in kinds:
        parts.append(f"{_s(n(p, 'receiving', 'REC'), 'catch', 'catches')} for {int(n(p, 'receiving', 'YDS'))} yards" + (f" and {_s(n(p, 'receiving', 'TD'), 'touchdown')}" if n(p, "receiving", "TD") else ""))
    if "def" in kinds:
        bits = []
        if n(p, "defensive", "SACKS"):
            bits.append(_s(n(p, "defensive", "SACKS"), "sack"))
        if n(p, "interceptions", "INT"):
            bits.append(_s(n(p, "interceptions", "INT"), "interception"))
        if n(p, "defensive", "TD") + n(p, "interceptions", "TD"):
            bits.append("a defensive touchdown")
        parts.append(", ".join(bits))
    if "st" in kinds:
        bits = []
        if returns(p)[1]:
            bits.append("a return touchdown")
        if n(p, "kicking", "LONG") >= 55 and pair(stat(p, "kicking", "FG"))[0]:
            bits.append(f"a {int(n(p, 'kicking', 'LONG'))}-yard field goal")
        parts.append(" and ".join(bits))
    return f"{p['short']} ({p['team']}): " + "; ".join(x for x in parts if x) + f" {_result(p, games)}."


def kinds_of(p):
    """Which of the spec's thresholds a player met."""
    k = set()
    py, ptd, pint = n(p, "passing", "YDS"), n(p, "passing", "TD"), n(p, "passing", "INT")
    if p["pos"] == "QB":
        if py >= 350 or ptd >= 4 or (py >= 300 and ptd >= 3 and pint == 0):
            k.add("pass")
        if n(p, "rushing", "YDS") >= 100:
            k.add("rush")
    if p["pos"] in RB_POS and (n(p, "rushing", "YDS") >= 150 or n(p, "rushing", "TD") + n(p, "receiving", "TD") >= 3):
        k.add("rb")
    if p["pos"] in WR_POS + TE_POS and (n(p, "receiving", "YDS") >= 150 or n(p, "receiving", "TD") >= 3):
        k.add("rec")
    if p["pos"] in RUSH_POS + BACK_POS and (n(p, "defensive", "SACKS") >= 3 or n(p, "interceptions", "INT") >= 2 or n(p, "defensive", "TD") + n(p, "interceptions", "TD") >= 1):
        k.add("def")
    if returns(p)[1] >= 1 or (p["pos"] in KICK_POS and n(p, "kicking", "LONG") >= 55 and pair(stat(p, "kicking", "FG"))[0]):
        k.add("st")
    return k


def highlights(players, games, limit=5):
    """The ranked standouts (spec thresholds), at most five, best first: [(points, line)]."""
    out = [(points(p), standout_text(p, kinds_of(p), games)) for p in players if kinds_of(p)]
    return sorted(out, key=lambda t: -t[0])[:limit]


def player_of_the_week(players, games, k=3):
    """The top scorers of the week by `points`: [(points, player, line)], the first is the Player of the Week."""
    top = sorted(players, key=lambda p: (-points(p), p["short"]))[:k]
    return [(points(p), p, _pline(p, games)) for p in top]


def _pline(p, games):
    bits = []
    if p["pos"] == "QB" or n(p, "passing", "YDS") >= 100:
        c, a = pair(stat(p, "passing", "C/ATT"))
        bits.append(f"{c}/{a}, {int(n(p, 'passing', 'YDS'))} yards, {int(n(p, 'passing', 'TD'))} TD, {int(n(p, 'passing', 'INT'))} INT")
    if n(p, "rushing", "CAR"):
        bits.append(f"{int(n(p, 'rushing', 'YDS'))} rushing yards on {int(n(p, 'rushing', 'CAR'))} carries" + (f", {int(n(p, 'rushing', 'TD'))} TD" if n(p, "rushing", "TD") else ""))
    if n(p, "receiving", "REC"):
        bits.append(f"{int(n(p, 'receiving', 'REC'))} catches, {int(n(p, 'receiving', 'YDS'))} yards" + (f", {int(n(p, 'receiving', 'TD'))} TD" if n(p, "receiving", "TD") else ""))
    d = []
    if n(p, "defensive", "SACKS"):
        d.append(_s(n(p, "defensive", "SACKS"), "sack"))
    if n(p, "interceptions", "INT"):
        d.append(_s(n(p, "interceptions", "INT"), "interception"))
    if d:
        bits.append(", ".join(d))
    if pair(stat(p, "kicking", "FG"))[1]:
        bits.append(f"{stat(p, 'kicking', 'FG')} field goals")
    if returns(p)[1]:
        bits.append("a return touchdown")
    return f"{p['short']} ({p['team']}): " + "; ".join(bits) + f" {_result(p, games)}."


# ---- Standings: divisions and playoff picture -----------------------------------------------------

def _stat(entry, name, field="displayValue"):
    return next((s.get(field) for s in entry["stats"] if s["name"] == name), None)


def record_of(entry):
    w, l, t = (int(float(_stat(entry, k, "value") or 0)) for k in ("wins", "losses", "ties"))
    return f"{w}-{l}" + (f"-{t}" if t else "")


def division_html(standings):
    """Eight small tables, AFC then NFC, in ESPN's order inside each division."""
    out = ""
    for conf in standings["children"]:
        for div in conf["children"]:
            ents = div["standings"]["entries"]
            rows = [[e["team"]["shortDisplayName"], record_of(e), _stat(e, "pointsFor"), _stat(e, "pointsAgainst"), _stat(e, "streak") or "-"] for e in ents]
            out += r.compact(r.table(div["name"], [("Team", False), ("W-L", True), ("PF", True), ("PA", True), ("Strk", True)], rows, row_classes=["mine" if e["team"]["abbreviation"] in MINE else "" for e in ents]),
                             (36, 17, 15, 15, 17), " nfl div")
    return out


def playoff_html(standings, seeds_shown=10):
    """Each conference's seeds 1 to 10 with a line after the seventh: seeds 1 to 4 lead their divisions, 5 to 7 are wild cards."""
    out = ""
    for conf in standings["children"]:
        ents = sorted((e for d in conf["children"] for e in d["standings"]["entries"] if _stat(e, "playoffSeed")), key=lambda e: int(_stat(e, "playoffSeed", "value") or 99))[:seeds_shown]
        rows = [[_stat(e, "playoffSeed"), e["team"]["shortDisplayName"], record_of(e), "DIV" if int(_stat(e, "playoffSeed", "value")) <= 4 else ("WC" if int(_stat(e, "playoffSeed", "value")) <= 7 else "")] for e in ents]
        classes = [" ".join(x for x in ("cut" if i == 6 else "", "mine" if e["team"]["abbreviation"] in MINE else "") if x) for i, e in enumerate(ents)]
        out += r.compact(r.table(f"{''.join(w[0] for w in conf['name'].split())} Playoff Picture", [("Seed", True), ("Team", False), ("W-L", True), ("", False)], rows, row_classes=classes), (14, 44, 20, 22), " nfl div")
    return out


# ---- Page -----------------------------------------------------------------------------------------

LABELS = ("Player of the Week", "Also")


def _list(items):
    def one(text):
        head, sep, rest = text.partition(": ")
        return f"<strong>{r.esc(head)}:</strong> {r.esc(rest)}" if sep and head in LABELS else r.esc(text)
    return '<ul class="standouts">' + "".join(f"<li>{one(i)}</li>" for i in items) + "</ul>" if items else ""


def standings_ok(standings):
    return bool(standings and standings.get("children"))


# ---- The whole block ------------------------------------------------------------------------------

def run(now, day, st, source):
    """{"html", "state", "stats", "week"}. now: UTC; day: the edition's date in Singapore (its weekday decides the extras);
    st: {"reported": [game ids], "positions": {athlete id: position}, "leaders": {"week", "ids"}}. A failing source never raises:
    that part is left out and counted in stats["failed"]."""
    stats = {"week": None, "games": 0, "completed": 0, "new": 0, "shown": 0, "boxes": 0, "failed": 0, "unknown_positions": 0, "calls": 0}
    reported, positions = list(st.get("reported", [])), dict(st.get("positions", {}))
    keep = {"reported": reported, "positions": positions, "leaders": st.get("leaders")}
    empty = {"html": "", "state": keep, "stats": stats, "week": None}
    try:
        sb = source.scoreboard()
    except Exception:
        stats["failed"] += 1
        return empty
    season_type = (sb.get("season") or {}).get("type")
    if season_type == 1:  # preseason: not covered
        return empty
    week = sb["week"]["number"]
    games = [parse_game(e) for e in sb["events"]]
    byes = [t["shortDisplayName"] for t in sb["week"].get("teamsOnBye", [])]
    if week > 1 and season_type == 2 and not any(g["status"] == "final" for g in games):  # the scoreboard has moved on to the next week
        try:
            prev = source.scoreboard(week - 1, season_type)
            prev_games = [parse_game(e) for e in prev["events"]]
            if any(g["status"] == "final" for g in prev_games):
                week, games, byes = week - 1, prev_games, [t["shortDisplayName"] for t in prev["week"].get("teamsOnBye", [])]
        except Exception:
            stats["failed"] += 1
    by_id = {g["id"]: g for g in games}
    completed = [g for g in games if g["status"] == "final"]
    new = [g for g in completed if g["id"] not in set(reported) and timedelta(0) <= now - g["date"] <= LOOKBACK]
    stats.update(week=week, games=len(games), completed=len(completed), new=len(new))
    wed, wrap_days = day.weekday() == 2, (0, 2)
    shown_games = completed if wed else new
    need_boxes = completed if day.weekday() in wrap_days else new
    boxes = {}
    for g in need_boxes:
        try:
            boxes[g["id"]] = source.box(g["id"])
        except Exception:
            stats["failed"] += 1
    stats["boxes"] = len(boxes)
    for b in boxes.values():  # positions for anyone new (the box score has none): one roster per team, only when needed
        for team_id in unknown_ids(b, positions):
            try:
                positions.update(source.roster(team_id))
            except Exception:
                stats["failed"] += 1
    players = {gid: players_of(b, positions, gid) for gid, b in boxes.items()}
    all_players = [p for ps in players.values() for p in ps]
    new_players = [p for g in new for p in players.get(g["id"], [])]
    stats["unknown_positions"] = sum(1 for p in all_players if p["pos"] is None)
    html = scoreboard_html(shown_games, week_name(week, season_type), len(completed), len(games), byes) if shown_games else ""
    leaders_shown = None
    if day.weekday() in wrap_days and all_players and (new or wed):
        lead = leaders(all_players)
        ids = leader_ids(lead)
        snap = st.get("leaders") if (st.get("leaders") or {}).get("week") == week else None
        fresh = {p["id"] for g in GROUPS for p in lead[g] if snap and p["id"] not in snap["ids"].get(g, [])} if snap else set()
        head = f'<h4>Weekly Leaders</h4><p class="muted">From {len(completed)} of {len(games)} games played.</p>'
        if wed and snap and not fresh:
            html += head + '<p class="muted">No change in the top three of any group since Monday.</p>'
        else:
            html += head + leaders_html(lead, all_players, fresh)
        leaders_shown = {"week": week, "ids": ids}
    hl = highlights(new_players, by_id) if new_players else []
    if hl:
        html += "<h4>Highlights</h4>" + _list([t for _, t in hl])
    if wed and all_players:
        potw = player_of_the_week(all_players, by_id)
        html += "<h4>Player of the Week</h4>" + _list([("Player of the Week: " if i == 0 else "Also: ") + line for i, (_, _, line) in enumerate(potw)])
    if wed and season_type == 2:
        try:
            standings = source.standings()
            if standings_ok(standings):
                html += "<h4>Division Standings</h4>" + division_html(standings)
                if week >= PLAYOFF_PICTURE_FROM:
                    html += "<h4>Playoff Picture</h4>" + playoff_html(standings)
        except Exception:
            stats["failed"] += 1
    stats["shown"] = len(shown_games)
    reported += [g["id"] for g in shown_games if g["id"] not in set(reported)]
    keep.update(reported=reported[-300:], leaders=leaders_shown or st.get("leaders"))
    stats["calls"] = getattr(source, "calls", 0)
    return {"html": html, "state": keep, "stats": stats, "week": week}
