"""Arsenal men's match board (D, 2026-11-22), directly under the big score line: the stats in two columns (goals first, with the assist in grey under each), the line-ups drawn on a
pitch with names only, and the bench in a table with who each substitute came on for. Home on the left and on top, away on the right and at the bottom, as the score line reads.
Name colours (no emojis, they widen the rows): a scorer in the champions' pearl shimmer ('(2)' for two goals), an assist maker in soft blue, yellow-carded in yellow, red-carded in red,
everyone else plain. A scorer or assister who was also carded keeps the goal or assist colour and gets a thin underline in the card's colour. Everything comes from ESPN's match summary;
nothing here is written by Claude."""
from collections import Counter

from kickoff import render as r

STAT_ROWS = (("Shots", "totalShots", "n"), ("On target", "shotsOnTarget", "n"), ("Possession", "possessionPct", "pct"), ("Fouls", "foulsCommitted", "n"),
             ("Offsides", "offsides", "n"), ("Yellows", "yellowCards", "n"), ("Reds", "redCards", "n"))
DEF, MID, AMID, FWD = 1, 2, 3, 4          # the rows of a formation, from the back


def surname(name):
    """'Gabriel Magalães' -> 'Magalães': the last word of the name (the one a fan says)."""
    return (name or "").split()[-1] if name else ""


def short_names(names):
    """{full name: the name shown}: the surname, with an initial when two players of one team share it."""
    count = Counter(surname(n) for n in names)
    return {n: (surname(n) if count[surname(n)] == 1 else f"{n.split()[0][0]}. {surname(n)}") for n in names}


def role(pos):
    """The formation row a position code belongs to: 1 defence, 2 midfield, 3 attacking midfield, 4 forwards (-1 for the goalkeeper)."""
    p = (pos or "").upper()
    if p == "G":
        return -1
    if p.startswith(("AM", "SS")) or p in ("LF", "RF"):
        return AMID
    if p.startswith(("CD", "SW")) or p in ("LB", "RB", "CB"):
        return DEF
    if p.startswith(("F", "ST", "CF", "LW", "RW")) or p in ("W",):
        return FWD
    return MID                                   # DM, CM, LM, RM, LWB, RWB and anything else in the middle


def across(pos):
    """0 to 4 from the left of the pitch to the right, from the team's own point of view: LB/LM/LW/LWB 0, -L 1, centre 2, -R 3, RB/RM/RW/RWB 4."""
    p = (pos or "").upper()
    if p.endswith("-L"):
        return 1
    if p.endswith("-R"):
        return 3
    if p.startswith("L"):
        return 0
    if p.startswith("R"):
        return 4
    return 2


def rows_of(formation, starters):
    """[[player, ...] ...] from the goalkeeper's row to the forwards': the formation's own numbers (4-2-3-1) cut the outfield players, sorted by position row, then left to right. A formation
    that does not add up to the ten outfield players is drawn by position rows instead."""
    keeper = [p for p in starters if role(p["pos"]) == -1]
    field = sorted((p for p in starters if role(p["pos"]) != -1), key=lambda p: (role(p["pos"]), across(p["pos"]), p["place"]))
    try:
        sizes = [int(x) for x in (formation or "").split("-")]
    except ValueError:
        sizes = []
    if sum(sizes) != len(field) or not sizes:
        rows = {}
        for p in field:
            rows.setdefault(role(p["pos"]), []).append(p)
        sizes_rows = [rows[k] for k in sorted(rows)]
    else:
        sizes_rows, i = [], 0
        for n in sizes:
            sizes_rows.append(field[i:i + n])
            i += n
    return ([keeper] if keeper else []) + [sorted(row, key=lambda p: (across(p["pos"]), p["place"])) for row in sizes_rows]


def marks(game):
    """{side: {"goals": Counter, "assists": set, "yellow": set, "red": set}} from the match's goals and timeline."""
    out = {s: {"goals": Counter(), "assists": set(), "yellow": set(), "red": set()} for s in ("home", "away")}
    for g in game.get("goals") or []:
        if g.get("side") in out and not g.get("own_goal"):
            out[g["side"]]["goals"][g["player"]] += 1
            if g.get("assist"):
                out[g["side"]]["assists"].add(g["assist"])
    for e in game.get("timeline") or []:
        if e.get("side") in out and e["kind"] in ("yellow", "red") and e.get("player"):
            out[e["side"]][e["kind"]].add(e["player"])
    for x in game.get("reds") or []:
        if x.get("side") in out:
            out[x["side"]]["red"].add(x["player"])
    return out


def name_html(full, shown, m, off=False):
    """One player's name as a coloured span; '(2)' after a scorer of two or more."""
    n = m["goals"].get(full, 0)
    cls = ["pl"]
    if n:
        cls.append("g")
    elif full in m["assists"]:
        cls.append("a")
    card = "r" if full in m["red"] else "y" if full in m["yellow"] else ""
    if card:
        cls.append(card)
    text = f'<span class="{" ".join(cls)}">{r.esc(shown)}</span>'
    return text + (f'<span class="x2">({n})</span>' if n > 1 else "") + ('<span class="off">↓</span>' if off else "")


def _num(v, kind):
    return "-" if v is None else (f"{round(v)}%" if kind == "pct" else str(int(v)))


def goals_cell(game, side, m):
    """The side's goals: 'Barnes 49'' with the assist in grey under it."""
    mine = [x for x in game.get("goals") or [] if x.get("side") == side]
    names = short_names(list(dict.fromkeys([x["player"] for x in mine] + [x["assist"] for x in mine if x.get("assist")])))
    out = ""
    for g in game.get("goals") or []:
        if g.get("side") != side:
            continue
        who = names.get(g["player"], surname(g["player"])) + (" (og)" if g.get("own_goal") else "")
        mark = f'<span class="pl g">{r.esc(who)}</span>' if not g.get("own_goal") else r.esc(who)
        assist = f'<span class="as">({r.esc(names.get(g["assist"], surname(g["assist"])))})</span>' if g.get("assist") else ""
        out += f'<span class="gl">{mark} <span class="mn">{r.esc(g["minute"])}</span>{assist}</span>'
    return out or "-"


def stats_html(game):
    s = game.get("stats") or {}
    ab = game.get("abbr") or {}
    head = f'<tr class="hd"><th>{r.esc(ab.get("home") or "")}</th><th></th><th>{r.esc(ab.get("away") or "")}</th></tr>'
    m = marks(game)
    rows = f'<tr class="goals"><td>{goals_cell(game, "home", m["home"])}</td><th>Goals</th><td>{goals_cell(game, "away", m["away"])}</td></tr>'
    for label, key, kind in STAT_ROWS:
        a, b = (s.get("home") or {}).get(key), (s.get("away") or {}).get(key)
        if a is None and b is None:
            continue
        rows += f"<tr><td>{_num(a, kind)}</td><th>{label}</th><td>{_num(b, kind)}</td></tr>"
    return f'<table class="mbstats"><colgroup><col style="width:36%"><col style="width:28%"><col style="width:36%"></colgroup>{head}{rows}</table>'


def pitch_html(game):
    """The two line-ups on one pitch with no fill: the home side on top (goalkeeper at the top), the away side at the bottom (goalkeeper at the bottom)."""
    lu = game.get("lineups") or {}
    if not (lu.get("home") and lu.get("away") and lu["home"]["starters"] and lu["away"]["starters"]):
        return ""
    m = marks(game)
    names = {}
    out = ""
    team_names = {"home": (game.get("home") or {}).get("name") or "", "away": (game.get("away") or {}).get("name") or ""}
    for side in ("home", "away"):
        names[side] = short_names([p["name"] for p in lu[side]["starters"]])
        rows = rows_of(lu[side]["formation"], lu[side]["starters"])
        html_rows = []
        for row in (rows if side == "home" else list(reversed(rows))):
            ordered = list(reversed(row)) if side == "home" else row              # the top team faces down: its right is on the viewer's left
            html_rows.append('<div class="pr">' + "".join(f'<span class="pn">{name_html(p["name"], names[side][p["name"]], m[side], p["off"])}</span>' for p in ordered) + "</div>")
        label = f'<div class="pt"><span>{r.esc(team_names[side])}</span><span class="fm">{r.esc(lu[side]["formation"])}</span></div>'
        out += f'<div class="half {side}">' + (label + "".join(html_rows) if side == "home" else "".join(html_rows) + label) + "</div>"
    return f'<div class="pitch"><i class="ph"></i><i class="pc"></i><i class="bx top"></i><i class="bx bot"></i>{out}</div>'


def bench_html(game):
    lu = game.get("lineups") or {}
    if not (lu.get("home") and lu.get("away")):
        return ""
    m = marks(game)
    minute = {(e["side"], e["player"]): e["minute"] for e in game.get("timeline") or [] if e["kind"] == "sub"}
    cols = {}
    for side in ("home", "away"):
        bench = lu[side]["bench"]
        sub_names = short_names([p["name"] for p in lu[side]["starters"] + bench])
        cells = []
        for p in sorted(bench, key=lambda p: (not p["on"], minute.get((side, p["name"]), ""), p["name"])):
            note = ""
            if p["on"]:
                bits = [f"for {sub_names.get(p['for'], surname(p['for']))}"] if p["for"] else []
                bits.append(minute.get((side, p["name"]), ""))
                hurt = any(e["kind"] == "sub" and e["side"] == side and e["player"] == p["name"] and e["injury"] for e in game.get("timeline") or [])
                note = f' <span class="as">({r.esc(", ".join(b for b in bits if b))}{", injury" if hurt else ""})</span>'
            cells.append(name_html(p["name"], sub_names[p["name"]], m[side]) + note)
        cols[side] = cells
    n = max(len(cols["home"]), len(cols["away"]))
    ab = game.get("abbr") or {}
    rows = "".join(f'<tr><td>{(cols["home"] + [""] * n)[i]}</td><td>{(cols["away"] + [""] * n)[i]}</td></tr>' for i in range(n))
    return (f'<table class="mbbench"><tr class="ttl"><th colspan="2">Bench</th></tr><tr class="hd"><th>{r.esc(ab.get("home") or "")}</th><th>{r.esc(ab.get("away") or "")}</th></tr>{rows}</table>')


def html(game):
    """The whole board for one finished game, '' when ESPN gave neither stats nor line-ups."""
    if not (game.get("stats") or game.get("lineups")):
        return ""
    return f'<div class="mb">{stats_html(game) if game.get("stats") else ""}{pitch_html(game)}{bench_html(game)}</div>'
