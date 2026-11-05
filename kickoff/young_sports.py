"""Young Guns candidates (full names everywhere: D does not know the young players, as with golfers; 2026-11-05), one function per sport: the notable performances of a sport's finished games, checked for youth (kickoff/youngguns.py).

Each takes the players the sport has already read, the saved state ({"watch", "ages"}; `ages` is filled in with new lookups) and the edition's date, and returns candidates.
A threshold is the usual one, 70% of it for a player on the watchlist; the lookup happens only for a player who already clears the lowest threshold, so a busy night costs a
handful of requests. `get` is the age lookup (injectable for tests). Cricket and the sports without a free data feed are not covered yet."""
from datetime import date

from kickoff import nba as nba_mod
from kickoff import nfl as nfl_mod
from kickoff import tennis as tennis_mod
from kickoff import youngguns as yg


def _scaled(state, sport, pid):
    return yg.WATCH_FACTOR if yg.watched(state, sport, pid) else 1.0


def nba(players, state, day, get=None):
    out = []
    for p in players:
        if p["dnp"]:
            continue
        low = yg.WATCH_FACTOR
        if not (p["PTS"] >= 20 * low or p["REB"] >= 12 * low or p["AST"] >= 10 * low or p["STL"] >= 4 or p["BLK"] >= 4):
            continue
        age, rookie = yg.lookup("nba", p["id"], day, state.setdefault("ages", {}), get)
        if not yg.is_young(age, rookie):
            continue
        f = _scaled(state, "nba", p["id"])
        if p["PTS"] >= 20 * f or p["REB"] >= 12 * f or p["AST"] >= 10 * f or p["STL"] >= 4 or p["BLK"] >= 4:
            out.append(yg.make("nba", p["id"], p["name"], p["team"], f"{nba_mod.line(p)} against {p['opp']['name']}", nba_mod.weight(p), age, rookie, day))
    return out


def nfl(players, state, day, get=None):
    out = []
    for p in players:
        if not p.get("pos"):
            continue
        py, ptd = nfl_mod.n(p, "passing", "YDS"), nfl_mod.n(p, "passing", "TD")
        ry, rtd = nfl_mod.n(p, "rushing", "YDS"), nfl_mod.n(p, "rushing", "TD")
        cy, ctd = nfl_mod.n(p, "receiving", "YDS"), nfl_mod.n(p, "receiving", "TD")
        sacks, ints = nfl_mod.n(p, "defensive", "SACKS"), nfl_mod.n(p, "interceptions", "INT")
        low = yg.WATCH_FACTOR
        bits = []                                               # (threshold met at the usual level, text, score)
        if py >= 250 * low or ptd >= 2:
            bits.append((py >= 250 or ptd >= 3, f"{int(py)} passing yards, {int(ptd)} TD", py / 10 + ptd * 6))
        if ry >= 100 * low or rtd >= 2:
            bits.append((ry >= 100 or rtd >= 2, f"{int(ry)} rushing yards" + (f", {int(rtd)} TD" if rtd else ""), ry / 8 + rtd * 6))
        if cy >= 100 * low or ctd >= 2:
            bits.append((cy >= 100 or ctd >= 2, f"{int(cy)} receiving yards" + (f", {int(ctd)} TD" if ctd else ""), cy / 8 + ctd * 6))
        if sacks >= 2 * low or ints >= 1:
            bits.append((sacks >= 2 or ints >= 1, (f"{sacks:g} sacks" if sacks >= 1 else "") + (", " if sacks >= 1 and ints else "") + (f"{int(ints)} interception" + ("s" if ints > 1 else "") if ints else ""), sacks * 8 + ints * 8))
        if not bits:
            continue
        age, rookie = yg.lookup("nfl", p["id"], day, state.setdefault("ages", {}), get)
        if not yg.is_young(age, rookie):
            continue
        watched = yg.watched(state, "nfl", p["id"])
        best = [b for b in bits if b[0] or watched]
        if best:
            out.append(yg.make("nfl", p["id"], p["name"], p["team"], "; ".join(b[1] for b in best), sum(b[2] for b in best), age, rookie, day))
    return out


def f1(rows, race_name, day):
    """rows: the race result rows (each Driver carries a date of birth). Under 21 on race day with a podium, a points finish, pole or the fastest lap."""
    out = []
    for x in rows:
        d = x["Driver"]
        age = yg.age_on(d.get("dateOfBirth", ""), day)
        if age is None or age >= yg.AGE_LIMIT:
            continue
        pos, bits = int(x["position"]) if str(x["position"]).isdigit() else 99, []
        if pos <= 3:
            bits.append(f"finished {pos}{'st' if pos == 1 else 'nd' if pos == 2 else 'rd'}")
        elif pos <= 10:
            bits.append(f"finished {pos}th, in the points")
        if x.get("grid") == "1":
            bits.append("started from pole")
        if (x.get("FastestLap") or {}).get("rank") == "1":
            bits.append("set the fastest lap")
        if bits:
            out.append(yg.make("f1", d["driverId"], f"{d['givenName'].split()[-1]} {d['familyName']}", x["Constructor"]["name"], f"{', '.join(bits)} in the {race_name}",
                               40 - pos + (10 if pos <= 3 else 0), age, False, day))
    return out


def soccer(players, state, day, get=None):
    """players: espn.get_player_stats rows for the finished matches of the day. A goal or an assist (or a clean-sheet-sized night in goal) by an under-21."""
    out = []
    for p in players:
        if not (p["goals"] or p["assists"]):
            continue
        age, rookie = yg.lookup("soccer", p["id"], day, state.setdefault("ages", {}), get)
        if not yg.is_young(age, rookie):
            continue
        bits = ([f"{p['goals']} goal" + ("s" if p["goals"] > 1 else "")] if p["goals"] else []) + ([f"{p['assists']} assist" + ("s" if p["assists"] > 1 else "")] if p["assists"] else [])
        out.append(yg.make("soccer", p["id"], p["name"], p["team_abbr"], ", ".join(bits) + (f" ({p['match']})" if p.get("match") else ""), p["goals"] * 5 + p["assists"] * 3, age, False, day))
    return out


def tennis(matches, state, day, get=None):
    """matches: tennis.parse_match dicts shown this morning. An under-21 who won in the last 16 or later, or beat a seeded player."""
    out = []
    for m in matches:
        w, l = m["winner"], m["loser"]
        late = tennis_mod.ORDER.index(m["stage"]) >= tennis_mod.ORDER.index("R4")
        if not (late or l.get("seed")):
            continue
        age, rookie = yg.lookup("tennis", w["id"], day, state.setdefault("ages", {}), get)
        if not yg.is_young(age, rookie):
            continue
        why = f"beat ({l['seed']}) {l['short']}" if l.get("seed") else f"beat {l['short']}"
        out.append(yg.make("tennis", w["id"], w["name"], m.get("draw", ""), f"{why} {tennis_mod.score(m, tb=False)}", 10 + tennis_mod.ORDER.index(m["stage"]) * 3 + (5 if l.get("seed") else 0), age, False, day))
    return out
