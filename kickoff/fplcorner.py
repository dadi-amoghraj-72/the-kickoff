"""The FPL corner: D's classic team and Draft league, the deadline reminder, squad alerts, transfer hints and gameweek top scorers.
All built by code from FPL's public data. No Claude, no cost.

It appears on two mornings only (D, 2026-11-04): the one edition that falls within 24 hours before a gameweek's deadline, and once after a gameweek's last match
when FPL has added the bonus points and marked the data checked (usually the day after the last Premier League game of the week). Every other morning it is left out."""
from datetime import datetime, timedelta, timezone

from kickoff import render as r
from kickoff.focus import when_sgt

DEADLINE_WINDOW = timedelta(hours=24)
RECENT = timedelta(hours=36)
WATCH_OWNERSHIP = 15.0  # per cent of managers who own the player
FLAGGED = {"i": "Injured", "d": "Doubtful", "s": "Suspended", "u": "Unavailable"}


def parse_time(text):
    """FPL times, with or without fractions of a second: '2026-11-06T18:30:00Z' or '2026-10-24T17:00:09.115906Z'."""
    return datetime.fromisoformat(text.replace("Z", "+00:00")) if text else None


def current_event(bootstrap):
    return next((e for e in bootstrap["events"] if e["is_current"]), None) or next(e for e in bootstrap["events"] if e["is_next"])


def deadline(bootstrap, now, window=DEADLINE_WINDOW):
    """The next gameweek deadline if it is within the window (24 hours), else None. {'gw', 'when'}."""
    nxt = next((e for e in bootstrap["events"] if e["is_next"]), None)
    when = parse_time(nxt["deadline_time"]) if nxt else None
    if not when or not (timedelta(0) <= when - now <= window):
        return None
    return {"gw": nxt["id"], "when": when_sgt(when.strftime("%Y-%m-%dT%H:%MZ"))}


def number(n):
    return f"{n:,}"


def classic_box(entry, picks, history, live, by_id, event):
    """Your team's gameweek as a small summary box (the same box as the other sports): the team, the gameweek's points with the average, the overall rank with its move
    (▼ down, ▲ up), the captain and his points, the points left on the bench, and a transfer cost or chip when there is one."""
    eh, gw = picks["entry_history"], event["id"]
    cap = next((p for p in picks["picks"] if p["is_captain"]), None)
    ranks = {c["event"]: c["overall_rank"] for c in history.get("current", [])}
    move = ""
    if gw - 1 in ranks and gw in ranks and ranks[gw] != ranks[gw - 1]:
        diff = ranks[gw] - ranks[gw - 1]
        move = f"{'▼' if diff > 0 else '▲'}{number(abs(diff))}"
    items = [("Team", "", entry["name"], ""),
             (f"Gameweek {gw}{'' if event['finished'] else ' so far'}", f"{eh['points']} pts", f"(AVG: {event['average_entry_score']})", ""),
             ("Overall rank", "", number(eh["overall_rank"]), move)]
    if cap:
        items.append(("Captain", f"{live.get(cap['element'], 0) * cap['multiplier']} pts", by_id[cap["element"]]["web_name"], ""))
    items.append(("Bench", f"{eh.get('points_on_bench') or 0} pts", "", ""))
    if eh.get("event_transfers_cost"):
        items.append(("Transfer cost", f"-{eh['event_transfers_cost']} pts", "", ""))
    if picks.get("active_chip"):
        items.append(("Chip", "", str(picks["active_chip"]), ""))
    return r.summary_box(items)


def squad_alerts(picks, by_id):
    """Your players who are not fully fit, with FPL's note and chance of playing."""
    out = []
    for p in picks["picks"]:
        pl = by_id[p["element"]]
        if pl["status"] in FLAGGED:
            out.append({"name": pl.get("web_name") or pl["name"], "team": pl["team"], "status": pl["status"], "news": pl["news"],
                        "chance": pl["chance_next"], "added": pl["news_added"]})
    return out


def is_recent(added, now):
    when = parse_time(added) if added else None
    return bool(when and now - when <= RECENT)


def alerts_html(items):
    """'Injuries': the players of your squad who are not fully fit, numbered, with FPL's note and chance of playing."""
    lis = "".join(f"<li><strong>{r.esc(i['name'])}</strong> ({r.esc(i['team'])}) <span class=\"muted\">{FLAGGED[i['status']]}</span>"
                  f"{(': ' + r.esc(i['news'])) if i['news'] else ''}"
                  f"{(' (' + str(i['chance']) + '% chance of playing)') if i['chance'] is not None and i['status'] == 'd' and 'chance of playing' not in i['news'] else ''}</li>"
                  for i in items)
    return f'<p><strong>Injuries</strong></p><ol class="inj">{lis}</ol>' if lis else ""


def draft_table(league, my_entry_id, gw):
    """Standings rows, the signature used to tell whether anything changed, and the HTML."""
    by = {e["id"]: e for e in league["league_entries"]}
    rows, mine, sig = [], [], []
    for s in sorted(league["standings"], key=lambda s: s["rank"]):
        e = by[s["league_entry"]]
        moved = (s.get("last_rank") or s["rank"]) - s["rank"]
        rows.append([s["rank"], e["entry_name"], f"▲{moved}" if moved > 0 else (f"▼{-moved}" if moved < 0 else "–"), s["event_total"], s["total"]])
        mine.append("mine hl" if e["entry_id"] == my_entry_id else "")       # bold and gold, like Arsenal and Sunrisers (D)
        sig.append([s["league_entry"], s["rank"], s["total"]])
    html = r.table(f"{league['league']['name']} After Gameweek {gw}",
                   [("#", True), ("Team", False), ("Move", True), ("GW", True), ("Total", True)], rows, row_classes=mine)
    return sig, html


def top_scorers(live, by_id, n=5):
    best = sorted(live.items(), key=lambda kv: (-kv[1], by_id[kv[0]]["web_name"]))[:n]
    return [[i + 1, by_id[pid]["name"], by_id[pid]["team"], pts] for i, (pid, pts) in enumerate(best)]


WINDOW = 3         # gameweeks the averages cover
LOW_AVG = 2.5      # a starter at or below this many points a gameweek is underperforming
SWAP_GAP = 2.0     # points a gameweek a bench player must beat his position's worst starter by
PICKUPS_PER_POSITION = 2
POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
NOT_FIT = ("i", "s", "u")   # injured, suspended, unavailable: left to the Injuries list


def _avg(trend, gws, pid):
    """Points a gameweek over gws; a gameweek without a game counts as 0."""
    return sum(trend[g].get(pid, {}).get("points", 0) for g in gws) / len(gws)


def _played(trend, gws, pid):
    return sum(1 for g in gws if trend[g].get(pid, {}).get("minutes", 0) > 0)


def transfer_review(picks, trend, by_id, players):
    """The three FPL lists, all in average points a gameweek over the last 3 gameweeks of trend ({gw: {player id: {"points", "minutes"}}}):
    'swaps' (highest priority, it costs nothing): a fit bench player who beat his position's worst starter by 2.0 or more a gameweek;
    'outs': fit starters at 2.5 or less; 'pickups': per position (GKP, DEF, MID, FWD) the best two players outside your squad, available (status 'a') and
    playing in at least 2 of the 3 gameweeks, who beat your squad's average for that position (all 15 players). Nothing if fewer than 3 gameweeks are known."""
    gws = sorted(trend)[-WINDOW:]
    if len(gws) < WINDOW:
        return {"gws": gws, "swaps": [], "outs": [], "pickups": []}
    squad = picks["picks"]
    starters = [p for p in squad if p["position"] <= 11]
    fit = lambda p: by_id[p["element"]]["status"] not in NOT_FIT  # noqa: E731
    avg = lambda p: _avg(trend, gws, p["element"])  # noqa: E731
    outs = [{"player": by_id[p["element"]], "avg": avg(p)} for p in starters if fit(p) and avg(p) <= LOW_AVG]
    swaps = []
    for b in (p for p in squad if p["position"] > 11 and fit(p)):
        peers = [s for s in starters if s["element_type"] == b["element_type"]]
        if peers:
            worst = min(peers, key=lambda s: (avg(s), by_id[s["element"]]["name"]))
            if avg(b) - avg(worst) >= SWAP_GAP:
                swaps.append({"player": by_id[b["element"]], "over": by_id[worst["element"]], "avg": avg(b), "over_avg": avg(worst), "gap": avg(b) - avg(worst)})
    outs.sort(key=lambda x: (x["avg"], x["player"]["name"]))
    swaps.sort(key=lambda x: (-x["gap"], x["player"]["name"]))
    mine = {p["element"] for p in squad}
    pickups = []
    for typ in sorted(POS):
        group = [avg(p) for p in squad if p["element_type"] == typ]
        if not group:
            continue
        pos_avg = sum(group) / len(group)
        cands = [(_avg(trend, gws, c["id"]), c) for c in players
                 if c.get("type") == typ and c["id"] not in mine and c["status"] == "a" and _played(trend, gws, c["id"]) >= 2]
        best = sorted((x for x in cands if x[0] > pos_avg), key=lambda x: (-x[0], -x[1]["minutes"], x[1]["name"]))[:PICKUPS_PER_POSITION]
        pickups += [{"player": c, "pos": POS[typ], "avg": a, "pos_avg": pos_avg} for a, c in best]
    return {"gws": gws, "swaps": swaps, "outs": outs, "pickups": pickups}


GROUPS = {"GKP": "Goalkeepers", "DEF": "Defenders", "MID": "Midfielders", "FWD": "Forwards"}      # FPL's own names for the four positions
LEGEND = "Avg. points per Gameweek, last 3 GWs"


def review_html(review):
    """The FPL lists, each with only its heading and, under it, one legend line saying what the figures are (D, 2026-11-04: not repeated on every row): Bench Swaps and
    Underperforming Players (numbered lists), and Potential Pick Ups grouped by position (Goalkeepers, Defenders, Midfielders, Forwards: two numbered entries each, the squad's
    average for that position once in the group's heading). Each entry is the player's FPL short name (web_name), his club's code and the figure in square brackets: 'Szoboszlai (LIV) [0.7]' (gold; red for the underperformers; the squad average in a group heading is bold pastel red).
    Everything in the block is one font size (the wrapper's css). A list with nothing in it is left out."""
    n = lambda v: f"{v:.1f}"  # noqa: E731
    who = lambda p: f"<strong>{r.esc(p.get('web_name') or p['name'])}</strong>" + (f" ({r.esc(p['team'])})" if p.get("team") else "")  # noqa: E731
    fig = lambda v, cls="n": f'<span class="{cls}">[{n(v)}]</span>'  # noqa: E731  (in square brackets so the number is never bare)
    ol = lambda items: '<ol class="inj tight">' + "".join(f"<li>{x}</li>" for x in items) + "</ol>"  # noqa: E731
    head = lambda t, legend: f'<p><strong>{t}</strong></p><p class="muted">{legend}</p>'  # noqa: E731
    out = ""
    if review["swaps"]:
        out += head("Bench Swaps", f"{LEGEND} (bench player | starter)") + ol(f"{who(s['player'])} over {who(s['over'])} {fig(s['avg'])} | {fig(s['over_avg'])}" for s in review["swaps"])
    if review["outs"]:
        out += head("Underperforming Players", LEGEND) + ol(f"{who(o['player'])} {fig(o['avg'], 'n bad')}" for o in review["outs"])
    if review["pickups"]:
        out += head("Potential Pick Ups", LEGEND)
        for pos, title in GROUPS.items():
            group = [u for u in review["pickups"] if u["pos"] == pos]
            if group:
                out += f'<p class="gp"><strong>{title}</strong> <span class="muted">(my squad avg.: <span class="sq">{n(group[0]["pos_avg"])}</span>)</span></p>' + ol(f"{who(u['player'])} {fig(u['avg'])}" for u in group)
    return out


def watch_items(players, seen, now, exclude=()):
    """Heavily owned players with new injury or suspension news, each shown once. `exclude`: player ids already in D's own squad (their news is in the Injuries list above;
    D, 2026-11-05: Konsa and Calvert-Lewin were there twice)."""
    out = []
    for p in players:
        if p["id"] in exclude:
            continue
        if p["owned"] >= WATCH_OWNERSHIP and p["status"] in ("i", "d", "s") and p["news_added"] and is_recent(p["news_added"], now) \
                and seen.get(str(p["id"])) != p["news_added"]:
            out.append({"name": p["name"], "team": p["team"], "status": p["status"], "news": p["news"], "chance": p["chance_next"],
                        "added": p["news_added"], "owned": p["owned"]})
    return out


def build(bootstrap, players, entry, picks, history, live, draft, my_draft_entry_id, state, now, trend_fn=None, demo=False):
    """The FPL corner HTML and the new state: '' on every morning except the one within 24 hours before a deadline and the one after a gameweek's bonus points are
    final. Before the deadline: the deadline, your summary box, squad alerts, transfer hints, FPL Watch and the Draft table. After the gameweek: your summary box,
    the Draft table and the gameweek's top scorers (once per gameweek: state["recap_gw"]). demo=True shows everything the corner can do whatever the date."""
    by_id = {p["id"]: p for p in players}
    event = current_event(bootstrap)
    new_state = dict(state)
    dl = deadline(bootstrap, now) or (deadline(bootstrap, now, window=timedelta(days=400)) if demo else None)
    recap = bool(event.get("data_checked")) and event["finished"] and state.get("recap_gw") != event["id"]
    if demo:
        recap = bool(live) and state.get("recap_gw") != event["id"]
    if not (dl or recap):
        return "", new_state
    parts = []
    if dl:
        parts.append(f"<p><strong>Deadline:</strong> Gameweek {dl['gw']} closes {dl['when']}.</p>")
    if entry and picks and live is not None:
        parts.append(classic_box(entry, picks, history or {}, live, by_id, event))
        alerts = squad_alerts(picks, by_id)
        if dl and alerts:
            parts.append(f'<div class="fplrev">{alerts_html(alerts)}</div>')
        if dl and trend_fn:  # only near the deadline, when a transfer decision is due
            trend = trend_fn()
            if trend:
                parts.append(f'<div class="fplrev">{review_html(transfer_review(picks, trend, by_id, players))}</div>')
    if dl:
        watch = watch_items(players, state.get("watch_seen", {}), now, {x["element"] for x in (picks or {}).get("picks", [])})
        if watch:
            lis = "".join(f"<li><strong>{r.esc(w['name'])}</strong> ({r.esc(w['team'])}) <span class=\"muted\">{FLAGGED[w['status']]}</span>"
                          f"{(': ' + r.esc(w['news'])) if w['news'] else ''} <span class=\"muted\">· owned by {w['owned']:.0f}%</span></li>" for w in watch)
            parts.append(f'<p><strong>FPL Watch:</strong></p><ul class="team-news">{lis}</ul>')
            seen = dict(state.get("watch_seen", {}))
            seen.update({str(p["id"]): p["news_added"] for p in players if p["owned"] >= WATCH_OWNERSHIP and p["news_added"]})
            new_state["watch_seen"] = seen
    if draft:
        sig, table = draft_table(draft, my_draft_entry_id, event["id"])
        parts.append(table)
        new_state["draft"] = sig
    if recap and live:
        parts.append(r.table(f"Gameweek {event['id']} Top Scorers", [("#", True), ("Player", False), ("Team", False), ("Pts", True)], top_scorers(live, by_id)))
        new_state["recap_gw"] = event["id"]
    return "<h3>FPL Corner</h3>" + "".join(parts), new_state
