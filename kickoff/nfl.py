"""NFL: the week's scoreboard, weekly leaders by position group, highlights, a computed Player of the Week, division tables and (from week 14)
the playoff picture. All by code from exact data, so no Claude cost.

Edition rhythm (the edition's Singapore weekday decides the extras; a scoreboard of the whole week, with games still to play marked YTP,
appears whenever games have newly finished, and always on Wednesday):
  Mon  Sunday's games, weekly leaders so far, highlights.   Tue  the Sunday-night game and any others, highlights.
  Wed  the whole week's scoreboard, weekly leaders again (late-game entries marked "new", or a line saying nothing changed), highlights of the
       Monday-night game, Player of the Week, division tables and, from week 14, the playoff picture.   Sat  Thursday night's game.
Which games are new is decided by the state ({"reported": [game ids]}), not the clock, so nothing is lost or shown twice."""
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from kickoff import render as r

ET = ZoneInfo("America/New_York")
HOME_SVG = ('<svg class="home" viewBox="0 0 16 16" width="13" height="13" role="img" aria-label="Home team">'
            '<path fill="currentColor" d="M8 1.2 0.8 7.6h2.1V14h3.6v-3.9h3V14h3.6V7.6h2.1z"/></svg>')
MY_QBS = (("Trevor Lawrence", "JAX"), ("Aaron Rodgers", "PIT"))   # always shown under the top three quarterbacks, with their rank
BLOWOUT = 24                               # a win by this many points or more is a highlight
COMEBACK = 14                              # a win after trailing by this many points or more is a highlight
LONG_PLAY = 60                             # a scoring play of this many yards or more can be the longest play of the week
TURNOVERS = 4                              # a team with this many giveaways is a highlight
OFF_POS, DEF_POS, ST_POS = ("QB", "RB", "FB", "WR", "TE"), ("DE", "DT", "LB", "OLB", "ILB", "MLB", "EDGE", "NT", "DL", "CB", "S", "FS", "SS", "DB"), ("K", "PK", "P")
DOG = '<span class="dog" title="Underdog win">*</span>'
RETURN_YARDS = 100                         # a returner is listed for a touchdown or for this many return yards in the game
LOOKBACK = timedelta(days=6)
PLAYOFF_PICTURE_FROM = 14                  # week of the regular season
POST_ROUNDS = {1: "Wild Card Round", 2: "Divisional Round", 3: "Conference Championships", 5: "Super Bowl"}
NEW_MARK = "⁠NEW"                     # becomes a small "new" tag after the table is built (cell text is escaped)
MIN_PASS_ATTEMPTS = 10                     # for the weekly passer-rating list
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
            "neutral": bool(c.get("neutralSite")), "broadcast": names[0] if names else "", "detail": t.get("shortDetail", ""), "home": side(sides["home"]), "away": side(sides["away"])}


def slot(g):
    """The kickoff group a game belongs to: its day (US Eastern) and part of the day. Games in the same group sit together; a line separates groups."""
    et = g["date"].astimezone(ET)
    h = et.hour + et.minute / 60
    return (et.date().isoformat(), "morning" if h < 11 else "early" if h < 14.5 else "late" if h < 18 else "night")


def winner(g):
    a, h = g["away"]["score"], g["home"]["score"]
    return None if a == h else ("away" if a > h else "home")


def dog_of(box):
    """Which side was the underdog before kickoff, 'away' or 'home', from the pre-game line (ESPN's flag, else the moneylines); None when unknown or a pick-em."""
    o = (box or {}).get("odds")
    if not o:
        return None
    if o.get("away_dog"):
        return "away"
    if o.get("home_dog"):
        return "home"
    a, h = o.get("away_ml"), o.get("home_ml")
    if isinstance(a, (int, float)) and isinstance(h, (int, float)) and a != h:
        return "away" if a > h else "home"
    return None


def underdog_win(g):
    """True when the pre-game underdog won outright."""
    return g["status"] == "final" and bool(g.get("dog")) and winner(g) == g["dog"]


def week_name(week, season_type):
    return POST_ROUNDS.get(week, f"Playoffs {week}") if season_type == 3 else f"Week {week}"


# ---- Scoreboard -----------------------------------------------------------------------------------

def best_game(games):
    """The most dramatic finished game: points scored, overtime and a close finish count; a rout does not. Returns the game or None."""
    finals = [g for g in games if g["status"] == "final" and g["home"]["score"] is not None]
    drama = lambda g: ((g["home"]["score"] + g["away"]["score"]) / 10 + (5 if g["ot"] else 0)  # noqa: E731
                       + (4 if abs(g["home"]["score"] - g["away"]["score"]) <= 3 else 2 if abs(g["home"]["score"] - g["away"]["score"]) <= 7 else 0))
    return max(finals, key=lambda g: (drama(g), g["date"])) if finals else None


def summary_html(games, played, total):
    """The box above the week's scoreboard: games played (with the rest still to come), underdog wins out of the games that had a clear underdog, and the
    best game (teams and score only)."""
    if not total:
        return ""
    items = [("Games played", f"{played}/{total}", "", "Rest still to play" if played < total else "")]
    known = [g for g in games if g["status"] == "final" and g.get("dog")]
    if known:
        items.append(("Underdogs won", f"{sum(1 for g in known if underdog_win(g))}/{len(known)}", "", ""))
    best = best_game(games)
    if best:
        items.append(("Best game", "", f"{best['away']['abbr']} {best['away']['score']}-{best['home']['score']} {best['home']['abbr']}", ""))
    return r.summary_box(items)


def scoreboard_html(games, title, played, total, byes=()):
    """Every game of the week, two rows per game (away above home): full team names, the home team marked with a house (none at neutral
    sites), the winner in bold, records and an OT tag, an "In progress" tag line above a game being played, YTP (yet to play) in the middle of the score for a game
    still to come, and a thicker line between kickoff groups."""
    if not games:
        return ""
    rows, prev = [], None
    for g in sorted(games, key=lambda g: g["date"]):
        if prev is not None and slot(g) != prev:
            rows.append('<tr class="gap"><td></td><td></td><td></td></tr>')
        prev, w = slot(g), (winner(g) if g["status"] == "final" else None)
        yet = g["status"] in ("scheduled", "other")
        if g["status"] == "live":  # on now: the score so far; it shows as a final in the next edition
            rows.append(f'<tr class="tag"><td colspan="3">In progress{" · " + r.esc(g["detail"]) if g.get("detail") else ""}</td></tr>')
        for side in ("away", "home"):
            t = g[side]
            mark = f" {HOME_SVG}" if side == "home" and not g["neutral"] else ""
            rec = f' <span class="rec">{r.esc(t["record"])}</span>' if t["record"] else ""
            star = DOG if side == w and underdog_win(g) else ""
            if yet:
                score = '<td class="sc ytp" rowspan="2">YTP</td>' if side == "away" else ""
            else:
                score = f'<td class="sc">{t["score"]}</td>'
            tag = ""
            if side == "away" and g["status"] == "final" and g["ot"]:
                tag = "OT"
            cls = " ".join(x for x in (side[0], "w" if w == side else "") if x)
            rows.append(f'<tr class="{cls}"><td class="tm">{r.esc(t["name"])}{star}{mark}{rec}</td>{score}<td class="ot">{tag}</td></tr>')
    html = summary_html(games, played, total) + (f'<div class="nflsb"><table><colgroup><col style="width:75%"><col style="width:12%"><col style="width:13%"></colgroup>'
                                                 f'<thead><tr><th class="tt" colspan="3">{r.esc(title)}</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
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


def top_returners(players, k=3):
    """Anyone who returned for a touchdown or for RETURN_YARDS yards or more (kicks and punts together), touchdowns first."""
    got = [p for p in players if returns(p)[1] >= 1 or returns(p)[0] >= RETURN_YARDS]
    return sorted(got, key=lambda p: (returns(p)[1], returns(p)[0]), reverse=True)[:k]


def top_punters(players, k=3, min_punts=3):
    return _top(players, ("P",), lambda p: (n(p, "punting", "AVG"), n(p, "punting", "In 20")), lambda p: n(p, "punting", "NO") >= min_punts, k)


def qb_ranking(players):
    """Every quarterback with enough attempts, best passer rating first."""
    return _top(players, ("QB",), lambda p: (_rating(p), n(p, "passing", "YDS")), lambda p: pair(stat(p, "passing", "C/ATT"))[1] >= MIN_PASS_ATTEMPTS, k=999)


def my_qbs(players, top):
    """D's quarterbacks who played and are not already in the top three: [(rank, player)], rank '–' when they threw too few passes to be ranked."""
    ranked = qb_ranking(players)
    out = []
    for name, team in MY_QBS:
        p = next((x for x in players if x["name"] == name and x["team"] == team and x["pos"] == "QB" and "passing" in x["stats"]), None)
        if p and all(p["id"] != t["id"] for t in top):
            out.append((next((i + 1 for i, q in enumerate(ranked) if q["id"] == p["id"]), "–"), p))
    return out


def _name(p, new):
    return p["short"] + (NEW_MARK if p["id"] in new else "")


def _tag(html):
    return html.replace(NEW_MARK, ' <span class="new">new</span>')


def _board(title, cols, widths, rows, classes=None, extra=" nfl"):
    return _tag(r.compact(r.table(title, cols, rows, row_classes=classes), widths, extra))


def _rating(p):
    c, a = pair(stat(p, "passing", "C/ATT"))
    return passer_rating(c, a, n(p, "passing", "YDS"), n(p, "passing", "TD"), n(p, "passing", "INT"))


GROUPS = ("qb", "rb", "wr", "te", "rush", "back", "kick", "punt", "ret")


def leaders(players):
    """{group: top players} for the position groups, plus the special-teams punters and returners, plus 'mine': D's quarterbacks with their ranks."""
    top = top_qbs(players)
    return {"qb": top, "rb": top_rbs(players), "wr": top_wrs(players), "te": top_tes(players), "rush": top_rushers(players), "back": top_backs(players),
            "kick": top_kickers(players), "punt": top_punters(players), "ret": top_returners(players), "mine": my_qbs(players, top)}


def leader_ids(lead):
    return {g: [p["id"] for p in lead[g]] for g in GROUPS}


def special_html(lead, new=frozenset()):
    """One table: kickers, then punters, then returners, each with a sub-heading row naming its measures."""
    rows, classes = [], []
    for part, label, measures in (("kick", "Kickers", ("FG", "LNG", "PTS")), ("punt", "Punters", ("PUNTS", "AVG", "IN20")), ("ret", "Returners", ("RET", "YDS", "TD"))):
        ps = lead[part]
        if not ps:
            continue
        rows.append(["", label, *measures])
        classes.append("sub")
        for i, p in enumerate(ps):
            if part == "kick":
                cells = [stat(p, "kicking", "FG"), int(n(p, "kicking", "LONG")), int(n(p, "kicking", "PTS"))]
            elif part == "punt":
                cells = [int(n(p, "punting", "NO")), stat(p, "punting", "AVG"), int(n(p, "punting", "In 20"))]
            else:
                cells = [int(n(p, "kickReturns", "NO") + n(p, "puntReturns", "NO")), int(returns(p)[0]), int(returns(p)[1])]
            rows.append([i + 1, f"{_name(p, new)} ({p['team']})", *cells])
            classes.append("")
    if not rows:
        return ""
    return _board("Top special teams performances", [("#", True), ("Player", False), ("", True), ("", True), ("", True)], (7, 47, 15, 15, 16), rows, classes, " nfl st")


def leaders_html(lead, players, new=frozenset()):
    """The position tables (top three each), D's quarterbacks under the quarterbacks, then the special-teams table."""
    html = ""
    qb = lead["qb"]
    extra = lead["mine"]
    qb_rows = [[i + 1, _name(p, new), p["team"], stat(p, "passing", "C/ATT"), int(n(p, "passing", "YDS")), f"{int(n(p, 'passing', 'TD'))}-{int(n(p, 'passing', 'INT'))}", f"{_rating(p):.1f}"] for i, p in enumerate(qb)]
    qb_rows += [[rank, p["short"], p["team"], stat(p, "passing", "C/ATT"), int(n(p, "passing", "YDS")), f"{int(n(p, 'passing', 'TD'))}-{int(n(p, 'passing', 'INT'))}", f"{_rating(p):.1f}"] for rank, p in extra]
    qb_classes = ["cut" if (extra and i == len(qb) - 1) else "" for i in range(len(qb_rows))]
    html += _board("Top QB performances", [("#", True), ("Player", False), ("Tm", False), ("C/ATT", True), ("YDS", True), ("TD-INT", True), ("RTG", True)], (7, 27, 10, 14, 10, 14, 18), qb_rows, qb_classes) if qb_rows else ""
    rb = lead["rb"]
    html += _board("Top RB performances", [("#", True), ("Player", False), ("Tm", False), ("CAR", True), ("YDS", True), ("AVG", True), ("TD", True)], (6, 31, 10, 13, 14, 13, 13),
                   [[i + 1, _name(p, new), p["team"], int(n(p, "rushing", "CAR")), int(n(p, "rushing", "YDS")), stat(p, "rushing", "AVG"), int(n(p, "rushing", "TD"))] for i, p in enumerate(rb)]) if rb else ""
    for key, title in (("wr", "Top WR performances"), ("te", "Top TE performances")):
        ps = lead[key]
        html += _board(title, [("#", True), ("Player", False), ("Tm", False), ("REC", True), ("YDS", True), ("TD", True), ("LNG", True)], (6, 31, 10, 13, 14, 13, 13),
                       [[i + 1, _name(p, new), p["team"], int(n(p, "receiving", "REC")), int(n(p, "receiving", "YDS")), int(n(p, "receiving", "TD")), int(n(p, "receiving", "LONG"))] for i, p in enumerate(ps)]) if ps else ""
    ps = lead["rush"]
    html += _board("Top pass rusher performances", [("#", True), ("Player", False), ("Pos", False), ("Tm", False), ("SACK", True), ("TFL", True), ("QBH", True)], (5, 28, 10, 11, 15, 14, 17),
                   [[i + 1, _name(p, new), p["pos"], p["team"], f"{n(p, 'defensive', 'SACKS'):g}", f"{n(p, 'defensive', 'TFL'):g}", int(n(p, "defensive", "QB HTS"))] for i, p in enumerate(ps)]) if ps else ""
    ps = lead["back"]
    html += _board("Top secondary performances", [("#", True), ("Player", False), ("Pos", False), ("Tm", False), ("INT", True), ("PD", True), ("TOT", True)], (5, 28, 10, 11, 15, 14, 17),
                   [[i + 1, _name(p, new), p["pos"], p["team"], int(n(p, "interceptions", "INT")), int(n(p, "defensive", "PD")), int(n(p, "defensive", "TOT"))] for i, p in enumerate(ps)]) if ps else ""
    return html + special_html(lead, new)


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


def st_points(p):
    """Special-teams points only: field goals (50+ yarders worth more) and return touchdowns."""
    made, _ = pair(stat(p, "kicking", "FG"))
    return round(made * 3 + (2 if n(p, "kicking", "LONG") >= 50 and made else 0) + returns(p)[1] * 8, 1)


def rare_bonus(p):
    """Defensive feats rare enough to outweigh the points scale: three or more interceptions, or four or more sacks."""
    return 6 if n(p, "interceptions", "INT") >= 3 or n(p, "defensive", "SACKS") >= 4 else 0


def players_of_the_week(players, games, extras=4):
    """The week's top individual performances: [(label, line)]. The best offensive player, the best defender (rare feats such as three
    interceptions get a bonus so a defender is not outscored by a quarterback's yards) and the best special-teams player (our own formula, not the
    NFL's official award), then up to four honourable mentions ("Mention") who met a spec threshold: the best four by points, listed quarterbacks first,
    then other offence, defence and special teams. Nobody appears twice."""
    best = lambda pool, key: max(pool, key=lambda p: (key(p), p["short"]), default=None)  # noqa: E731
    off = best([p for p in players if p["pos"] in OFF_POS], points)
    dfn = best([p for p in players if p["pos"] in DEF_POS], lambda p: points(p) + rare_bonus(p))
    st = best([p for p in players if st_points(p) > 0], st_points)
    out, used = [], set()
    for label, p, floor, score in (("Offence", off, 0, points), ("Defence", dfn, 12, lambda q: points(q) + rare_bonus(q)), ("Special teams", st, 6, st_points)):
        if p and score(p) >= floor:
            out.append((label, _pline(p, games)))
            used.add(p["id"])
    group = lambda p: 0 if p["pos"] == "QB" else 1 if p["pos"] in OFF_POS else 2 if p["pos"] in DEF_POS else 3   # noqa: E731
    more = sorted(sorted([p for p in players if kinds_of(p) and p["id"] not in used], key=lambda p: -points(p))[:extras], key=group)   # the best four, shown quarterbacks first
    return out + [("Mention", standout_text(p, kinds_of(p), games)) for p in more]


def _plain(text):
    """A scoring play's description without the kick in brackets: 'Joe Burrow 9 Yd Rush'."""
    return re.sub(r"\s*\(.*?\)\s*$", "", text).strip()


def game_highlights(games, boxes, limit=5):
    """Game-level and team-level highlights of the given finished games, ranked by interest, at most five: [(interest, line)]. Comebacks,
    game-winning kicks, shutouts, blowouts, overtime, giveaways and the longest scoring play. Underdog wins are not listed here: they are
    marked on the scoreboard. Individual performances are in Top performances."""
    items, longest = [], None
    for g in games:
        w = winner(g)
        if g["status"] != "final" or w is None:
            continue
        win, lose = g[w], g["home" if w == "away" else "away"]
        hi, lo = win["score"], lose["score"]
        box = boxes.get(g["id"]) or {}
        plays = box.get("plays") or []
        if lo == 0:
            items.append((3.0, f"Shutout: {win['short']} blanked {lose['short']} {hi}-0."))
        if hi - lo >= BLOWOUT:
            items.append((2 + (hi - lo) / 100, f"Blowout: {win['short']} beat {lose['short']} {hi}-{lo}."))
        comeback = winning_kick = None
        if plays:
            other = "home" if w == "away" else "away"
            deficit = max(p[other] - p[w] for p in plays)
            if deficit >= COMEBACK:
                comeback = deficit
            last = plays[-1]
            m = re.match(r"(.+?) (\d+) Yd Field Goal", last["text"])
            if m and last["team"] == win["abbr"] and hi - lo <= 3:
                winning_kick = (m.group(1), m.group(2), "in overtime" if last["period"] > 4 else f"with {last['clock']} left")
            for pl in plays:
                y = re.search(r"(\d+) Yd", pl["text"])
                if y and "Touchdown" in pl["type"] and (longest is None or int(y.group(1)) > longest[0]):
                    longest = (int(y.group(1)), pl)
        ot = " in overtime" if g["ot"] else ""
        if comeback and winning_kick:  # one line, not two, for the same game
            items.append((5.5 + comeback / 100, f"Comeback: {win['short']} came back from {comeback} points down to beat {lose['short']} {hi}-{lo}{ot}, {winning_kick[0]} kicking the {winning_kick[1]}-yard winner."))
        elif comeback:
            items.append((5 + comeback / 100, f"Comeback: {win['short']} came back from {comeback} points down to beat {lose['short']} {hi}-{lo}{ot}."))
        elif winning_kick:
            items.append((4.5, f"Game-winner: {winning_kick[0]} ({win['abbr']}) kicked a {winning_kick[1]}-yard field goal {winning_kick[2]} to beat {lose['short']} {hi}-{lo}."))
        elif g["ot"]:
            items.append((2.0, f"Overtime: {win['short']} beat {lose['short']} {hi}-{lo}."))
        for side in (win, lose):
            t = (box.get("teamStats") or {}).get(side["id"]) or {}
            giveaways = int(num(t.get("turnovers", 0)))
            if giveaways >= TURNOVERS:
                opp = lose if side is win else win
                items.append((2.0 + giveaways / 100, f"Giveaways: {side['short']} turned the ball over {giveaways} times in the {hi}-{lo} {'win over' if side is win else 'loss to'} {opp['short']}."))
    if longest and longest[0] >= LONG_PLAY:
        items.append((3.5, f"Longest play: {_plain(longest[1]['text'])} for a touchdown ({longest[1]['team']})."))
    return sorted(items, key=lambda t: -t[0])[:limit]


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


def ranks_of(standings):
    """{"div": {team code: place in its division}, "seeds": {team code: playoff seed}}: what the +/- arrows are measured against next time."""
    div, seeds = {}, {}
    for conf in standings["children"]:
        for d in conf["children"]:
            for i, e in enumerate(d["standings"]["entries"], 1):
                div[e["team"]["abbreviation"]] = i
                if _stat(e, "playoffSeed"):
                    seeds[e["team"]["abbreviation"]] = int(_stat(e, "playoffSeed", "value") or 0)
    return {"div": div, "seeds": seeds}


def games_behind(entry, leader):
    """Games behind the division leader: '–' for the leader (or a tied team), else 0.5 steps (a tie counts as half a win and half a loss)."""
    val = lambda e, k: float(_stat(e, k, "value") or 0)  # noqa: E731
    d = ((val(leader, "wins") + val(leader, "ties") / 2 - val(entry, "wins") - val(entry, "ties") / 2) + (val(entry, "losses") + val(entry, "ties") / 2 - val(leader, "losses") - val(leader, "ties") / 2)) / 2
    return "–" if d <= 0 else f"{d:g}"


def division_html(standings, before=None):
    """Eight small tables, AFC then NFC, in ESPN's order inside each division (the leader first, with a blue bar). Columns: W-L, DIV (the record inside the
    division), GB (games behind the leader) and the streak; +/- is the places moved within the division since the last table shown (`before`, from
    ranks_of); empty the first time."""
    out = ""
    prev = (before or {}).get("div") or {}
    for conf in standings["children"]:
        for div in conf["children"]:
            ents = div["standings"]["entries"]
            rows = []
            for i, e in enumerate(ents, 1):
                abbr = e["team"]["abbreviation"]
                rows.append([abbr, record_of(e), _stat(e, "divisionRecord") or "-", games_behind(e, ents[0]), _stat(e, "streak") or "-", r.move(prev[abbr] - i) if abbr in prev else ""])
            out += r.compact(r.table(div["name"], [("Team", False), ("W-L", True), ("DIV", True), ("GB", True), ("Strk", True), ("+/-", True)], rows,
                                     zones=["blue" if i == 0 else None for i in range(len(rows))]), (18, 18, 16, 16, 16, 16), " nfl div")
    return out


def playoff_html(standings, seeds_shown=10, before=None):
    """Each conference's seeds 1 to 10 with a line after the seventh: seed 1 (gold, BYE) gets the first-round bye, 2 to 4 lead their divisions, 5 to 7 are wild cards."""
    out = ""
    for conf in standings["children"]:
        ents = sorted((e for d in conf["children"] for e in d["standings"]["entries"] if _stat(e, "playoffSeed")), key=lambda e: int(_stat(e, "playoffSeed", "value") or 99))[:seeds_shown]
        prev = (before or {}).get("seeds") or {}
        rows = [[_stat(e, "playoffSeed"), e["team"]["abbreviation"], record_of(e), r.move(prev[e["team"]["abbreviation"]] - int(_stat(e, "playoffSeed", "value"))) if e["team"]["abbreviation"] in prev else "", "BYE" if int(_stat(e, "playoffSeed", "value")) == 1 else ("DIV" if int(_stat(e, "playoffSeed", "value")) <= 4 else ("WC" if int(_stat(e, "playoffSeed", "value")) <= 7 else ""))] for e in ents]
        classes = [" ".join(x for x in ("bye" if i == 0 else "", "cut" if i == 6 else "") if x) for i, e in enumerate(ents)]
        out += r.compact(r.table(f"{''.join(w[0] for w in conf['name'].split())} Playoff Picture", [("Seed", True), ("Team", False), ("W-L", True), ("+/-", True), ("", False)], rows, row_classes=classes), (14, 26, 22, 18, 20), " nfl div po")
    return out


# ---- Page -----------------------------------------------------------------------------------------

LABELS = ("Offence", "Defence", "Special teams", "Also", "Shutout", "Blowout", "Overtime", "Comeback", "Game-winner", "Giveaways", "Longest play")


def gold_numbers(text):
    """The stat figures of a Players-of-the-Week line in gold: every number before the result ('in the 43-36 win over TEN') is wrapped."""
    stats, sep, result = text.rpartition(" in the ")
    if not sep:
        stats, result = text, ""
    marked = re.sub(r"(?<![\w-])(\d+(?:/\d+)?)(?![\w-])", r'<span class="n">\1</span>', r.esc(stats))
    return marked + (" in the " + r.esc(result) if sep else "")


def emphasise(text, teams):
    """A highlight line with something to catch the eye: the team names in bold and the key figures in gold (scores like 33-30, '14 points', '42-yard',
    '95 Yd', '4 times') and the runner of a longest play in bold. Long runs of plain white text get skipped on a phone, so every highlight carries both."""
    out = r.esc(text)
    out = re.sub(r"(?<![\w-])(\d+-\d+)(?![\w-])", r'<span class="n">\1</span>', out)
    out = re.sub(r"(?<![\w>-])(\d+)(?=-yard|\s+(?:points|Yd|yards|times)\b)", r'<span class="n">\1</span>', out)
    out = re.sub(r"(?<![\w>])([A-Z][\w.'-]+(?: [A-Z][\w.'-]+)+)(?= <span class=\"n\">\d+</span> Yd)", r"<strong>\1</strong>", out)   # the player of a longest play
    for name in sorted(teams, key=len, reverse=True):
        out = re.sub(rf"(?<![\w>]){re.escape(r.esc(name))}(?![\w<])", lambda m: f"<strong>{m.group(0)}</strong>", out)
    return out


def _list(items, numbers=False, cls="", teams=None):
    """Notes lines in the house style: a gold diamond bullet with a hanging indent; a leading label (Offence:, Comeback:) in bold; the stat
    figures in gold when `numbers` is set (Top performances); `teams` (a set of team names) switches on emphasise() for the highlights."""
    def one(text):
        head, sep, rest = text.partition(": ")
        fmt = (lambda t: emphasise(t, teams)) if teams else (lambda t: gold_numbers(t) if numbers else r.esc(t))
        return f"<strong>{r.esc(head)}:</strong> {fmt(rest)}" if sep and head in LABELS else fmt(text)
    return f'<div class="dlist{" " + cls if cls else ""}">' + "".join(f'<div class="pl"><span class="t">{one(i)}</span></div>' for i in items) + "</div>" if items else ""


def standings_ok(standings):
    return bool(standings and standings.get("children"))


# ---- The whole block ------------------------------------------------------------------------------

def run(now, day, st, source):
    """{"html", "state", "stats", "week"}. now: UTC; day: the edition's date in Singapore (its weekday decides the extras);
    st: {"reported": [game ids], "positions": {athlete id: position}, "leaders": {"week", "ids"}}. A failing source never raises:
    that part is left out and counted in stats["failed"]."""
    stats = {"week": None, "games": 0, "completed": 0, "new": 0, "shown": 0, "boxes": 0, "failed": 0, "unknown_positions": 0, "calls": 0}
    reported, positions, dogs = list(st.get("reported", [])), dict(st.get("positions", {})), dict(st.get("dogs", {}))
    keep = {"reported": reported, "positions": positions, "leaders": st.get("leaders"), "dogs": dogs, "ranks": st.get("ranks")}
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
    show_board = bool(new) or wed
    need_boxes = completed if day.weekday() in wrap_days else new + [g for g in completed if g["id"] not in dogs and g not in new]  # a scoreboard needs every finished game's underdog
    boxes = {}
    for g in need_boxes:
        try:
            boxes[g["id"]] = source.box(g["id"])
        except Exception:
            stats["failed"] += 1
    stats["boxes"] = len(boxes)
    for gid, b in boxes.items():  # the underdog of each game is kept in the state: it does not change, and it costs a box score to find
        dogs[gid] = dog_of(b) or ""
    for g in games:
        g["dog"] = dogs.get(g["id"]) or None
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
    html = scoreboard_html(games, week_name(week, season_type), len(completed), len(games), byes) if show_board else ""
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
    hl = game_highlights([g for g in new if g["id"] in boxes], boxes)
    if hl:
        html += "<h4>Highlights</h4>" + _list([t for _, t in hl], teams={g[side]["short"] for g in games for side in ("home", "away")})
    if wed and all_players:
        potw = players_of_the_week(all_players, by_id)
        html += ("<h4>Top performances</h4>" + _list([f"{label}: {line}" for label, line in potw if label != "Mention"], numbers=True)
                 + (('<p class="subhead">Honourable mentions</p>' + _list([line for label, line in potw if label == "Mention"], numbers=True, cls="indent")) if any(label == "Mention" for label, _ in potw) else ""))
    if wed and season_type == 2:
        try:
            standings = source.standings()
            if standings_ok(standings):
                html += "<h4>Division Standings</h4>" + division_html(standings, st.get("ranks"))
                if week >= PLAYOFF_PICTURE_FROM:
                    html += "<h4>Playoff Picture</h4>" + playoff_html(standings, before=st.get("ranks"))
                keep["ranks"] = ranks_of(standings)
        except Exception:
            stats["failed"] += 1
    stats["shown"] = len(completed) if show_board else 0
    if show_board:
        reported += [g["id"] for g in completed if g["id"] not in set(reported)]
    keep.update(reported=reported[-300:], leaders=leaders_shown or st.get("leaders"))
    stats["calls"] = getattr(source, "calls", 0)
    return {"html": html, "state": keep, "stats": stats, "week": week}
