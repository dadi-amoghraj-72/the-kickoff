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
            out.append({"name": pl["name"], "team": pl["team"], "status": pl["status"], "news": pl["news"],
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
        mine.append("mine" if e["entry_id"] == my_entry_id else "")
        sig.append([s["league_entry"], s["rank"], s["total"]])
    html = r.table(f"{league['league']['name']} After Gameweek {gw}",
                   [("#", True), ("Team", False), ("Move", True), ("GW", True), ("Total", True)], rows, row_classes=mine)
    return sig, html


def top_scorers(live, by_id, n=5):
    best = sorted(live.items(), key=lambda kv: (-kv[1], by_id[kv[0]]["web_name"]))[:n]
    return [[i + 1, by_id[pid]["name"], by_id[pid]["team"], pts] for i, (pid, pts) in enumerate(best)]


HINT_LIMIT = 3
OUT_AVERAGE = 2.0  # points per appearance
SWAP_GAP = 4       # points a bench player must beat his position's worst starter by, over the window


def _totals(trend, pid):
    """(points, appearances) for a player across the gameweeks in trend. An appearance is any minutes played."""
    points = sum(trend[g].get(pid, {}).get("points", 0) for g in trend)
    apps = sum(1 for g in trend if trend[g].get(pid, {}).get("minutes", 0) > 0)
    return points, apps


def transfer_hints(picks, trend, by_id, limit=HINT_LIMIT):
    """A nudge from the last gameweeks in trend ({gw: {player id: {"points", "minutes"}}}), never advice.
    'out' (quiet): a starter who scored under 2 points in each of the last 3 gameweeks, which in practice means he is
        not playing or not doing anything. 'out' (low): a starter who played in at least two of them and averaged
        2 points an appearance or less. Players already flagged injured, suspended or unavailable are left to the
        squad alerts.
    'swap': a bench outfield player who beat the worst starter in his position by 4 or more points."""
    squad = picks["picks"]
    starters = [p for p in squad if p["position"] <= 11]
    bench = [p for p in squad if p["position"] > 11 and p["element_type"] != 1]
    outs, swaps = [], []
    for p in starters:
        pl = by_id[p["element"]]
        if pl["status"] in ("i", "s", "u"):
            continue
        pts, apps = _totals(trend, p["element"])
        weekly = [trend[g].get(p["element"], {}).get("points", 0) for g in sorted(trend)]
        if len(weekly) >= 3 and all(w < 2 for w in weekly):
            outs.append({"kind": "out", "reason": "quiet", "player": pl, "points": pts, "apps": apps, "weekly": weekly, "avg": pts / max(apps, 1)})
        elif apps >= 2 and pts / apps <= OUT_AVERAGE:
            outs.append({"kind": "out", "reason": "low", "player": pl, "points": pts, "apps": apps, "weekly": weekly, "avg": pts / apps})
    for b in bench:
        peers = [s for s in starters if s["element_type"] == b["element_type"]]
        if not peers:
            continue
        worst = min(peers, key=lambda s: _totals(trend, s["element"])[0])
        bpts, wpts = _totals(trend, b["element"])[0], _totals(trend, worst["element"])[0]
        if bpts - wpts >= SWAP_GAP:
            swaps.append({"kind": "swap", "player": by_id[b["element"]], "over": by_id[worst["element"]], "points": bpts,
                          "over_points": wpts, "gap": bpts - wpts})
    outs.sort(key=lambda x: (x["reason"] != "quiet", x["points"], x["player"]["name"]))
    swaps.sort(key=lambda x: (-x["gap"], x["player"]["name"]))
    return (outs + swaps)[:limit]


POSITION = {1: "goalkeeper", 2: "defender", 3: "midfielder", 4: "forward"}


def pickups(picks, trend, players, hints, limit=2):
    """Players you do not own who would be worth picking up in the position of an underperformer (a 'move out' hint): the best scorer over the trend's gameweeks
    among available (status 'a') players of that position who played, whose price fits (the outgoing player's price plus your bank), and who beat the player
    going out. At most one per underperformer, `limit` in all. [{"player", "points", "for", "cost"}]."""
    squad = {p["element"] for p in picks["picks"]}
    bank = (picks.get("entry_history") or {}).get("bank") or 0
    out, used = [], set()
    for h in (x for x in hints if x["kind"] == "out"):
        old = h["player"]
        if not old.get("type") or not old.get("cost"):
            continue
        best = None
        for c in players:
            if c.get("type") != old["type"] or c["id"] in squad or c["id"] in used or c["status"] != "a" or not c.get("cost") or c["cost"] > old["cost"] + bank:
                continue
            pts, apps = _totals(trend, c["id"])
            if apps >= 2 and pts > h["points"] and (best is None or (pts, c["minutes"]) > (best[0], best[1]["minutes"])):
                best = (pts, c)
        if best:
            used.add(best[1]["id"])
            out.append({"player": best[1], "points": best[0], "for": old, "cost": best[1]["cost"]})
        if len(out) == limit:
            break
    return out


def hints_html(hints, gws, picks_up=()):
    """'Transfer Suggestions': Underperformers (Move out?), bench players outscoring a starter, and Pick-up suggestions (from `pickups`)."""
    if not hints and not picks_up:
        return ""
    span = f"{len(gws)} gameweeks"
    outs, swaps = "", ""
    for h in hints:
        p = h["player"]
        if h["kind"] == "out" and h["reason"] == "quiet":
            outs += f"<li><strong>{r.esc(p['name'])}</strong> ({r.esc(p['team'])}) <span class=\"muted\">form</span> {', '.join(str(w) for w in h['weekly'])}</li>"
        elif h["kind"] == "out":
            outs += (f"<li><strong>{r.esc(p['name'])}</strong> ({r.esc(p['team'])}) <span class=\"muted\">form</span> "
                     f"{h['points']} points in {h['apps']} appearances over the last {span}</li>")
        else:
            o = h["over"]
            swaps += (f"<li><strong>{r.esc(p['name'])}</strong> ({r.esc(p['team'])}): {h['points']} points against {r.esc(o['name'])}'s {h['over_points']} "
                      f"over the last {span}</li>")
    html = "<p><strong>Transfer Suggestions</strong></p>"
    if outs:
        html += f'<p class="sub">Underperformers <span class="muted">(Move out?)</span> <span class="muted">· points in the last {span}</span></p><ul class="team-news">{outs}</ul>'
    if swaps:
        html += f'<p class="sub">Bench players outscoring a starter</p><ul class="team-news">{swaps}</ul>'
    if picks_up:
        lis = "".join(f"<li><strong>{r.esc(u['player']['name'])}</strong> ({r.esc(u['player']['team'])}) <span class=\"muted\">{POSITION.get(u['player']['type'], '')}</span>: "
                      f"{u['points']} points in the last {span} · £{u['cost'] / 10:.1f}m <span class=\"muted\">(for {r.esc(u['for']['name'])})</span></li>" for u in picks_up)
        html += f'<p class="sub">Pick-up suggestions?</p><ul class="team-news">{lis}</ul>'
    return html


def watch_items(players, seen, now):
    """Heavily owned players with new injury or suspension news, each shown once."""
    out = []
    for p in players:
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
            parts.append(alerts_html(alerts))
        if dl and trend_fn:  # only near the deadline, when a transfer decision is due
            trend = trend_fn()
            if trend:
                hints = transfer_hints(picks, trend, by_id)
                parts.append(hints_html(hints, list(trend), pickups(picks, trend, players, hints)))
    if dl:
        watch = watch_items(players, state.get("watch_seen", {}), now)
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
