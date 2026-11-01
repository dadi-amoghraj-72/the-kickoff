"""Injuries, suspensions and returns for key Premier League players, from the league's official FPL status.

Each news item is reported once, when it is new, so an injury is not repeated every morning. State lives in
data/state/injuries.json: what each key player's status was the last time we looked."""
import re
from datetime import date, datetime, timedelta

from kickoff import render as r

LISTED_PL = {"ARS", "MCI", "MUN", "LIV", "CHE", "TOT"}  # the big six, by FPL short code
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
RETURN_DATE = re.compile(r"(?:expected back|until|back)\s+(\d{1,2})\s+([A-Za-z]{3,9})", re.I)
LONG_DAYS = 14
FIRST_RUN_DAYS = 7


def is_key(p, top_six_cutoff=6):
    """Averages 70+ minutes per team game, or has started three quarters of them. Top six side or big six only."""
    if not p["team_played"]:
        return False
    on_top_side = (p["team_position"] or 99) <= top_six_cutoff or p["team"] in LISTED_PL
    regular = p["minutes"] / p["team_played"] >= 70 or p["starts"] / p["team_played"] >= 0.75
    return on_top_side and regular


def added_date(p):
    return datetime.strptime(p["news_added"][:10], "%Y-%m-%d").date() if p["news_added"] else None


def return_date(p):
    """The date in a news line like 'Expected back 15 Nov' or 'Suspended until 29 Nov', or None."""
    m = RETURN_DATE.search(p["news"])
    month = MONTHS.get(m.group(2)[:3].lower()) if m else None
    added = added_date(p)
    if not (m and month and added):
        return None
    d = date(added.year, month, int(m.group(1)))
    return d if d >= added - timedelta(days=30) else date(added.year + 1, month, int(m.group(1)))


def reportable_out(p, today):
    """Injured: report when no return date is given or it is 14+ days away. Suspended: always."""
    if p["status"] == "s":
        return True
    if p["status"] != "i":
        return False
    back = return_date(p)
    return back is None or (back - today).days >= LONG_DAYS


def reportable_doubt(p):
    return p["status"] == "d" and p["chance_next"] is not None and p["chance_next"] <= 50


def detect(all_players, saved, today):
    """Returns (items, new_saved): the news worth showing today, and the memory for tomorrow.
    saved: {player id (str): {"status", "news_added", "reported"}}, empty on the very first run.
    'reported' means we have shown this player's current out or doubt event, so his return is worth showing."""
    first_run = not saved
    items, new_saved = [], {}
    for p in all_players:
        if not is_key(p):
            continue
        pid = str(p["id"])
        before = saved.get(pid, {})
        is_new_event = before.get("news_added") != p["news_added"] or before.get("status") != p["status"]
        kind = None
        if p["status"] in ("i", "s", "d") and is_new_event:
            # On the very first run only news from the last week is shown; older news is just remembered.
            added = added_date(p)
            eligible = not first_run or added is None or (today - added).days <= FIRST_RUN_DAYS
            if eligible and reportable_out(p, today):
                kind = "suspended" if p["status"] == "s" else "out"
            elif eligible and reportable_doubt(p):
                kind = "doubt"
        elif p["status"] == "a" and before.get("reported"):
            kind = "returning"
        if kind in ("out", "suspended", "doubt"):
            reported = True
        elif kind == "returning":
            reported = False
        else:
            reported = before.get("reported", False) and not is_new_event  # same event as last time: carry on
        if kind:
            items.append({"kind": kind, "name": p["name"], "team": p["team"], "team_name": p["team_name"],
                          "detail": p["news"], "back": return_date(p), "chance": p["chance_next"], "minutes": p["minutes"]})
        new_saved[pid] = {"status": p["status"], "news_added": p["news_added"], "reported": reported}
    return items, new_saved


LABEL = {"out": "Out", "suspended": "Suspended", "doubt": "Doubt", "returning": "Back"}
ORDER = ["out", "suspended", "doubt", "returning"]


def line(item):
    detail = item["detail"] or ("Back in contention" if item["kind"] == "returning" else "")
    chance = f" ({item['chance']}% chance of playing)" if item["kind"] == "doubt" and item["chance"] is not None else ""
    return (f"<li><strong>{r.esc(item['name'])}</strong> ({r.esc(item['team'])}) <span class=\"muted\">{LABEL[item['kind']]}</span>"
            f"{(': ' + r.esc(detail)) if detail else ''}{chance}</li>")


def html(items, exclude_team=None):
    """The 'Injuries And Returns' block. Empty string when there is nothing, so the block is left out."""
    shown = sorted((i for i in items if i["team"] != exclude_team), key=lambda i: (ORDER.index(i["kind"]), i["team"], i["name"]))
    if not shown:
        return ""
    return ("<h3>Injuries And Returns</h3><ul class=\"team-news\">" + "".join(line(i) for i in shown) + "</ul>"
            '<p class="muted">From the Premier League\'s official player status updates.</p>')
