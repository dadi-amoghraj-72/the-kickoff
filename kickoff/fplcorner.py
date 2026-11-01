"""The FPL corner: D's classic team and Draft league, deadline reminders, squad alerts and gameweek top scorers.
All built by code from FPL's public data. No Claude, no cost."""
from datetime import datetime, timedelta, timezone

from kickoff import render as r
from kickoff.focus import when_sgt

DEADLINE_WINDOW = timedelta(hours=72)
RECENT = timedelta(hours=36)
WATCH_OWNERSHIP = 15.0  # per cent of managers who own the player
FLAGGED = {"i": "Injured", "d": "Doubtful", "s": "Suspended", "u": "Unavailable"}


def parse_time(text):
    """FPL times, with or without fractions of a second: '2026-11-06T18:30:00Z' or '2026-10-24T17:00:09.115906Z'."""
    return datetime.fromisoformat(text.replace("Z", "+00:00")) if text else None


def current_event(bootstrap):
    return next((e for e in bootstrap["events"] if e["is_current"]), None) or next(e for e in bootstrap["events"] if e["is_next"])


def deadline(bootstrap, now):
    """The next gameweek deadline if it is within 72 hours, else None. {'gw', 'when'}."""
    nxt = next((e for e in bootstrap["events"] if e["is_next"]), None)
    when = parse_time(nxt["deadline_time"]) if nxt else None
    if not when or not (timedelta(0) <= when - now <= DEADLINE_WINDOW):
        return None
    return {"gw": nxt["id"], "when": when_sgt(when.strftime("%Y-%m-%dT%H:%MZ"))}


def number(n):
    return f"{n:,}"


def classic_line(entry, picks, history, live, by_id, event):
    """Your team's gameweek in one line: points, average, rank and its move, captain, bench, transfers."""
    eh, gw = picks["entry_history"], event["id"]
    cap = next((p for p in picks["picks"] if p["is_captain"]), None)
    ranks = {c["event"]: c["overall_rank"] for c in history.get("current", [])}
    move = ""
    if gw - 1 in ranks and gw in ranks and ranks[gw] != ranks[gw - 1]:
        diff = ranks[gw] - ranks[gw - 1]
        move = f", {'down' if diff > 0 else 'up'} {number(abs(diff))}"
    parts = [f"<strong>{r.esc(entry['name'])}</strong>",
             f"Gameweek {gw}{'' if event['finished'] else ' so far'}: {eh['points']} pts (average {event['average_entry_score']})",
             f"overall rank {number(eh['overall_rank'])}{move}"]
    if cap:
        parts.append(f"captain {r.esc(by_id[cap['element']]['web_name'])} {live.get(cap['element'], 0) * cap['multiplier']} pts")
    if eh.get("points_on_bench"):
        parts.append(f"{eh['points_on_bench']} on the bench")
    if eh.get("event_transfers_cost"):
        parts.append(f"{eh['event_transfers_cost']} pt transfer cost")
    if picks.get("active_chip"):
        parts.append(f"chip: {r.esc(picks['active_chip'])}")
    return "<p>" + " · ".join(parts) + "</p>"


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
    lis = "".join(f"<li><strong>{r.esc(i['name'])}</strong> ({r.esc(i['team'])}) <span class=\"muted\">{FLAGGED[i['status']]}</span>"
                  f"{(': ' + r.esc(i['news'])) if i['news'] else ''}"
                  f"{(' (' + str(i['chance']) + '% chance of playing)') if i['chance'] is not None and i['status'] == 'd' else ''}</li>"
                  for i in items)
    return f'<p><strong>Your squad:</strong></p><ul class="team-news">{lis}</ul>' if lis else ""


def draft_table(league, my_entry_id, gw):
    """Standings rows, the signature used to tell whether anything changed, and the HTML."""
    by = {e["id"]: e for e in league["league_entries"]}
    rows, mine, sig = [], [], []
    for s in sorted(league["standings"], key=lambda s: s["rank"]):
        e = by[s["league_entry"]]
        rows.append([s["rank"], e["entry_name"], s["event_total"], s["total"]])
        mine.append("mine" if e["entry_id"] == my_entry_id else "")
        sig.append([s["league_entry"], s["rank"], s["total"]])
    html = r.table(f"{league['league']['name']} After Gameweek {gw}",
                   [("#", True), ("Team", False), ("GW", True), ("Total", True)], rows, row_classes=mine)
    return sig, html


def top_scorers(live, by_id, n=5):
    best = sorted(live.items(), key=lambda kv: (-kv[1], by_id[kv[0]]["web_name"]))[:n]
    return [[i + 1, by_id[pid]["name"], by_id[pid]["team"], pts] for i, (pid, pts) in enumerate(best)]


def watch_items(players, seen, now):
    """Heavily owned players with new injury or suspension news, each shown once."""
    out = []
    for p in players:
        if p["owned"] >= WATCH_OWNERSHIP and p["status"] in ("i", "d", "s") and p["news_added"] and is_recent(p["news_added"], now) \
                and seen.get(str(p["id"])) != p["news_added"]:
            out.append({"name": p["name"], "team": p["team"], "status": p["status"], "news": p["news"], "chance": p["chance_next"],
                        "added": p["news_added"], "owned": p["owned"]})
    return out


def build(bootstrap, players, entry, picks, history, live, draft, my_draft_entry_id, state, now):
    """The FPL corner HTML and the new state. Pieces that have nothing to say are left out."""
    by_id = {p["id"]: p for p in players}
    event = current_event(bootstrap)
    new_state = dict(state)
    parts = []
    dl = deadline(bootstrap, now)
    if dl:
        parts.append(f"<p><strong>Deadline:</strong> Gameweek {dl['gw']} closes {dl['when']}.</p>")
    if entry and picks and live is not None:
        parts.append(classic_line(entry, picks, history or {}, live, by_id, event))
        alerts = squad_alerts(picks, by_id)
        shown = alerts if dl else [a for a in alerts if is_recent(a["added"], now)]
        if shown:
            parts.append(alerts_html(shown))
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
        if sig != state.get("draft"):
            parts.append(table)
            new_state["draft"] = sig
    if live and event["finished"] and state.get("topscorers_gw") != event["id"]:
        parts.append(r.table(f"Gameweek {event['id']} Top Scorers", [("#", True), ("Player", False), ("Team", False), ("Pts", True)],
                             top_scorers(live, by_id)))
        new_state["topscorers_gw"] = event["id"]
    return ("<h3>FPL Corner</h3>" + "".join(parts) if parts else ""), new_state
