"""Golf (checkpoint 12, D's rules of 2026-11-05), from ESPN's free PGA Tour and LPGA scoreboards.

Men's majors and THE PLAYERS Championship (the Masters, PGA Championship, U.S. Open, The Open, PLAYERS): a note in the week before ("starts Thursday ..."), then after every completed round a table of
the first 25 with the round's score, the total to par and the strokes behind the lead, the leader's row in gold; D's players are added below the table with their real position whenever they are in the
field ("MC" for a missed cut, "WD" for a withdrawal); after the last round the same table is the final, with the winner in gold. The winner gets a line in The Big Stuff.
Women's majors (Chevron, U.S. Women's Open, Women's PGA, Evian, AIG Women's Open): only the weekend, the first 10 after Saturday's round and the final first 10 after Sunday's, the same table.

How the standings are worked out: ESPN gives each player's rounds (strokes, the score against par and how many holes were played). A round counts as finished when nobody is part-way through it (or
the next round has begun, which clears away anyone who withdrew); the table is the standing after the latest finished round, worked out here so it does not move while the next round is under way.
The LPGA boards have no hole-by-hole detail, so a round of 55 strokes or more counts as a whole round (a player on the 17th hole can be counted a hole early). Players who missed the cut have no third round and drop out of the tables. The final uses ESPN's own order (a playoff is already decided in it)."""
import re
from datetime import datetime, timedelta, timezone

from kickoff import render as r

MEN = re.compile(r"masters tournament|pga championship|u\.?s\.? open|the open championship|the players championship", re.I)
WOMEN = re.compile(r"chevron championship|u\.?s\.? women'?s open|women'?s pga championship|evian championship|women'?s open", re.I)
MEN_ROWS, WOMEN_ROWS = 25, 10
WATCH = ["Rory McIlroy", "Tiger Woods", "Bryson DeChambeau", "Scottie Scheffler", "Jon Rahm", "Brooks Koepka", "Xander Schauffele", "Collin Morikawa", "Rickie Fowler", "Phil Mickelson",
         "Jordan Spieth", "Akshay Bhatia"]          # D's players (2026-11-05): shown whenever they are in a men's field
START_WINDOW = timedelta(days=7)
FINAL_WINDOW = timedelta(days=3)


def _utc(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def par(text):
    """'-6' -> -6, 'E' -> 0, '+1' -> 1; None for '-' (no score) or anything unreadable."""
    t = (text or "").strip()
    if t == "E":
        return 0
    return int(t) if re.fullmatch(r"[+-]?\d+", t) and t not in ("-", "+") else None


def show(n):
    """A score against par as golfers write it: 'E', '-6', '+2'."""
    return "E" if n == 0 else f"{n:+d}"


def people(event):
    """[{"id", "name", "short", "order", "total", "rounds": {n: {"par", "strokes", "holes"}}, "playoff"}] for the competitors of a scoreboard event."""
    out = []
    for c in event["competitions"][0]["competitors"]:
        rounds, playoff = {}, False
        for l in c.get("linescores", []):
            holes = l.get("holes") if "holes" in l else len(l.get("linescores", []))
            if not holes and (l.get("value") or 0) > 0:      # the LPGA boards give no hole-by-hole detail: a round of 55 strokes or more is a whole round (nobody has played 18 holes in fewer), less is part of one
                holes = 18 if l["value"] >= 55 else max(1, round(l["value"] / 4.2))
            if l["period"] > 4:
                playoff = playoff or (holes or 0) > 0 or (l.get("value") or 0) > 0
                continue
            rounds[l["period"]] = {"par": par(l.get("displayValue")), "strokes": int(l.get("value") or 0), "holes": holes or 0}
        a = c["athlete"]
        out.append({"id": str(c.get("id")), "name": a["displayName"], "short": a.get("shortName") or a["displayName"], "order": c.get("order", 999), "total": par(c.get("score")),
                    "rounds": rounds, "playoff": playoff})
    return sorted(out, key=lambda p: p["order"])


def finished_rounds(ps):
    """The number of the latest finished round (0 when none): somebody finished it and nobody is part-way through it, unless a later round has begun (a part-way player has withdrawn)."""
    done = 0
    for n in (1, 2, 3, 4):
        finished = sum(1 for p in ps if p["rounds"].get(n, {}).get("holes") == 18)
        partial = sum(1 for p in ps if 0 < p["rounds"].get(n, {}).get("holes", 0) < 18)
        later = any(p["rounds"].get(n + 1, {}).get("holes", 0) > 0 for p in ps)
        if finished and (not partial or later):
            done = n
        else:
            break
    return done


def standing(ps, n):
    """The standing after round n: [{"p": player, "cum": total against par, "rd": round n's score, "rank": 1-based with ties}] for the players still in (finished all n rounds), best first."""
    live = []
    for p in ps:
        rs = [p["rounds"].get(k) for k in range(1, n + 1)]
        if all(x and x["holes"] == 18 and x["par"] is not None for x in rs):
            live.append({"p": p, "cum": sum(x["par"] for x in rs), "rd": rs[-1]["par"]})
    live.sort(key=lambda x: (x["cum"], x["p"]["order"]))
    for x in live:
        x["rank"] = 1 + sum(1 for y in live if y["cum"] < x["cum"])
    return live


def pos(rank, ties):
    return f"T{rank}" if ties > 1 else str(rank)


def watched(name):
    return any(w.lower() == name.lower() for w in WATCH)


def status_label(p, n):
    """'MC' for a player without a round past the cut, 'WD' for one who stopped part-way through a round, else None."""
    played = [k for k in (1, 2, 3, 4) if p["rounds"].get(k, {}).get("holes") == 18]
    partial = [k for k in (1, 2, 3, 4) if 0 < p["rounds"].get(k, {}).get("holes", 0) < 18]
    if partial and max(played or [0]) < n:
        return "WD"
    if len(played) < n and not partial and n >= 3 and len(played) >= 2:
        return "MC"
    return None


def table(title, rows, extras, final, behind_label="Behind"):
    """The standing as one table: Pos, Player, Rd, Total, Behind. rows: [{"p", "cum", "rd", "rank"}]; extras: D's players below it. The leader's row is gold."""
    lead = rows[0]["cum"] if rows else 0
    ties = {}
    for x in rows:
        ties[x["rank"]] = ties.get(x["rank"], 0) + 1
    body, classes = [], []
    for x in rows:
        body.append([pos(x["rank"], ties[x["rank"]]), x["p"]["name"], show(x["rd"]), show(x["cum"]), "–" if x["cum"] == lead else str(x["cum"] - lead)])
        classes.append("p1" if x["rank"] == 1 and x is rows[0] else "")
    for e in extras:
        body.append([e["pos"], e["name"], e.get("rd", ""), e.get("total", ""), e.get("behind", "")])
        classes.append("also")
    cols = [("Pos", False), ("Player", False), ("Rd", True), ("Total", True), (behind_label, True)]
    return render_table(title, cols, body, classes)


def render_table(title, cols, body, classes):
    """The standing in the compact fixed-width style: full player names (D does not know golfers' names), which wrap onto a second line when a name is long, narrow numbers."""
    return r.compact(r.table(title, cols, body, row_classes=classes), [11, 43, 14, 15, 17], " golf")


def extras_for(ps, rows, n, limit_names=None):
    """D's players who are in the field but not in `rows`: their position (ties counted over everyone still in), 'MC' or 'WD'."""
    shown = {x["p"]["id"] for x in rows}
    everyone = standing(ps, n)
    lead = everyone[0]["cum"] if everyone else 0
    ties = {}
    for x in everyone:
        ties[x["rank"]] = ties.get(x["rank"], 0) + 1
    out = []
    for name in (limit_names or WATCH):
        p = next((q for q in ps if q["name"].lower() == name.lower()), None)
        if not p or p["id"] in shown:
            continue
        x = next((y for y in everyone if y["p"]["id"] == p["id"]), None)
        if x:
            out.append({"name": p["name"], "rank": x["rank"], "pos": pos(x["rank"], ties[x["rank"]]), "rd": show(x["rd"]), "total": show(x["cum"]), "behind": "–" if x["cum"] == lead else str(x["cum"] - lead)})
        else:
            lab = status_label(p, n) or "MC"
            out.append({"name": p["name"], "rank": 10**6, "pos": lab, "rd": "", "total": show(p["total"]) if p["total"] is not None else "", "behind": ""})
    out.sort(key=lambda e: e["rank"])                      # D: always in order of position (T40, then T67, then MC/WD last); players on the same position keep his list's order
    return out


def final_rows(ps, size):
    """The final standing from ESPN's own order (a playoff is decided in it): [{"p", "cum", "rd", "rank"}] for the first `size` players, ties sharing a position except the winner."""
    done = [p for p in ps if p["total"] is not None and all(p["rounds"].get(k, {}).get("holes") == 18 for k in (1, 2, 3, 4))]
    done.sort(key=lambda p: p["order"])
    rows = []
    for p in done:
        rank = 1 + sum(1 for q in done if q["total"] < p["total"])
        rows.append({"p": p, "cum": p["total"], "rd": p["rounds"][4]["par"] if p["rounds"][4]["par"] is not None else 0, "rank": rank})
    if len(rows) > 1 and rows[1]["rank"] == 1:        # a tie on the lead is a playoff: the winner (ESPN's first) leads alone, the others tied with him share second
        for x in rows[1:]:
            if x["rank"] == 1:
                x["rank"] = 2
    return rows[:size]


def winner_of(ps):
    done = [p for p in ps if all(p["rounds"].get(k, {}).get("holes") == 18 for k in (1, 2, 3, 4)) and p["total"] is not None]
    return min(done, key=lambda p: p["order"]) if done else None


def start_notes(board, now, seen):
    """[(uid, text)] for each men's major or PLAYERS in the tour's calendar that starts within the next seven days and has not been noted."""
    out = []
    for c in ((board.get("leagues") or [{}])[0].get("calendar") or []):
        if not MEN.search(c.get("label", "")) or c["id"] in seen:
            continue
        start = datetime.fromisoformat(c["startDate"].replace("Z", "+00:00"))
        if timedelta(0) < start - now <= START_WINDOW:
            out.append((c["id"], f"{c['label']} starts on {start:%A} {start.day} {start:%B} (US time)"))
    return out


def run(boards, now, state):
    """boards: {"pga": scoreboard json, "lpga": scoreboard json} (missing tours are simply absent). state: {"events": {event id: {"round": last round shown, "final": bool}}, "notes": [calendar ids]}.
    Returns {"lines": [(text, uid)], "blocks": [html], "winners": [(text)], "state": new state}. Never raises for one odd event."""
    ev = {k: dict(v) for k, v in (state.get("events") or {}).items()}
    notes_seen = list(state.get("notes") or [])
    lines, blocks, winners = [], [], []
    for tour, board in boards.items():
        pattern, size = (MEN, MEN_ROWS) if tour == "pga" else (WOMEN, WOMEN_ROWS)
        if tour == "pga":
            for uid, text in start_notes(board, now, set(notes_seen)):
                lines.append((text, f"golf:start:{uid}"))
                notes_seen.append(uid)
        for e in board.get("events", []):
            try:
                if not pattern.search(e["name"]):
                    continue
                ps = people(e)
                if not ps:
                    continue
                name = re.sub(r"\s+pres\. by.*$", "", re.sub(r"^The\s+(Amundi\s+)?", "", e["name"])) if tour == "lpga" else e["name"]
                name = {"THE PLAYERS Championship": "The Players Championship"}.get(name, name)
                mine = ev.setdefault(e["id"], {"round": 0, "final": False})
                done = e["status"]["type"].get("state") == "post" and e["status"]["type"].get("completed")
                ended = datetime.fromisoformat(e["endDate"].replace("Z", "+00:00")) if e.get("endDate") else now
                if done and not mine["final"] and now - ended > FINAL_WINDOW:
                    mine["final"] = True                          # an event that finished long ago is not news (the first run ever, or a missed week)
                elif done and not mine["final"]:
                    rows = final_rows(ps, size)
                    if rows:
                        extras = extras_for(ps, rows, 4) if tour == "pga" else []
                        blocks.append(table(f"{name} · Final", rows, extras, True))
                        w = winner_of(ps)
                        if w:
                            winners.append(f"Golf: {w['name']} wins the {name} ({show(w['total'])})")
                        mine["final"], mine["round"] = True, 4
                elif not done:
                    n = finished_rounds(ps)
                    wanted = n > mine["round"] and (tour == "pga" or n == 3)
                    if wanted:
                        rows = standing(ps, n)[:size]
                        extras = extras_for(ps, rows, n) if tour == "pga" else []
                        under_way = any(0 < p["rounds"].get(n + 1, {}).get("holes", 0) < 18 for p in ps)
                        title = f"{name} · After round {n}" + (" (next round under way)" if under_way else "")
                        blocks.append(table(title, rows, extras, False))
                        mine["round"] = n
                    elif n > mine["round"]:
                        mine["round"] = n                          # a round the women do not show: remembered so it is not shown late
            except Exception:
                continue
    return {"lines": lines, "blocks": blocks, "winners": winners, "state": {"events": dict(list(ev.items())[-30:]), "notes": notes_seen[-30:]}}
