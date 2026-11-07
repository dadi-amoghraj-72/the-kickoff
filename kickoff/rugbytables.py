"""Rugby tables (D, 2026-11-08): the Six Nations, The Rugby Championship and the Nations Championship, shown under their results on a morning one of their games was played.

From ESPN's free standings feed (the same family as the other sports). The Nations Championship (the July and November windows from 2026) is two pools of six: ESPN lists all
twelve sides in one list, so they are split here, the Six Nations sides as the Northern pool and the others as the Southern. Columns fit a 360px phone: # Team P W L PD Pts,
the same table style as the football tables. A table that cannot be read is left out, never guessed."""
from kickoff import render as r

TABLES = {"180659": "Six Nations", "244293": "The Rugby Championship", "17567": "Nations Championship"}
NORTH = {"England", "France", "Ireland", "Italy", "Scotland", "Wales"}
COLUMNS = [("#", True), ("Team", False), ("P", True), ("W", True), ("L", True), ("PD", True), ("Pts", True)]


def rows_of(data):
    """[{"team", "p", "w", "l", "pd", "pts", "rank"}] for every side in the feed's groups, in the feed's order. [] when it has none."""
    out = []
    for group in (data or {}).get("children") or []:
        for e in (group.get("standings") or {}).get("entries") or []:
            v = {x.get("name"): x.get("displayValue") for x in e.get("stats") or []}
            try:
                out.append({"team": e["team"]["displayName"], "p": int(v["gamesPlayed"]), "w": int(v["gamesWon"]), "l": int(v["gamesLost"]),
                            "pd": int(float(v["pointsDifference"])), "pts": int(v["points"]), "bp": int(v.get("bonusPoints") or 0)})
            except (KeyError, TypeError, ValueError):
                return []                                  # one side we cannot read: no table rather than a wrong one
    return out


def ranked(rows):
    """By points, then points difference, then name: the order a table is read in (ESPN's own rank is per pool)."""
    return sorted(rows, key=lambda x: (-x["pts"], -x["pd"], x["team"]))


def table_html(league, data):
    """The table(s) of one competition, or '' when there is none yet (a season not started) or it cannot be read."""
    rows = [x for x in rows_of(data) if x["p"] > 0]
    if not rows:
        return ""
    name = TABLES.get(league, "Table")
    pools = [(f"{name}: Northern pool", [x for x in rows if x["team"] in NORTH]), (f"{name}: Southern pool", [x for x in rows if x["team"] not in NORTH])] \
        if league == "17567" else [(name, rows)]
    out = ""
    for caption, pool in pools:
        if not pool:
            continue
        body = [[i, x["team"], x["p"], x["w"], x["l"], f"{x['pd']:+d}", x["pts"]] for i, x in enumerate(ranked(pool), 1)]
        out += r.table(caption, COLUMNS, body)
    return f'<div class="rugbyt">{out}</div>'
