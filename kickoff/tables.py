"""League tables: what to show today (full, changed, or unchanged) and what to remember for tomorrow."""
from datetime import date

from kickoff import render as r
from kickoff.clubs import code, is_listed

COLUMNS = [("#", True), ("Team", False), ("P", True), ("GD", True), ("Pts", True)]
LEGEND = {"blue": "Champions League places", "lilac": "Europa and Conference League places, play-offs",
          "rose": "Relegation"}


def zone_for(note):
    n = (note or "").lower()
    if "relegat" in n:
        return "lilac" if "play" in n else "rose"
    if "champions" in n:
        return "blue"
    if "europa" in n or "conference" in n:
        return "lilac"
    return None


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def signature(rows):
    return [[x["id"], x["rank"], x["points"], x["played"]] for x in rows]


def decide(rows, saved, edition_date, tuesday_only=False):
    """Returns {"mode": "full" | "changed" | "unchanged" | "skip", "since": day name (unchanged only)}."""
    is_tuesday = edition_date.weekday() == 1
    if tuesday_only:
        return {"mode": "full" if is_tuesday else "skip"}
    if is_tuesday or not saved:
        return {"mode": "full"}
    if signature(rows) == saved["rows"]:
        return {"mode": "unchanged", "since": date.fromisoformat(saved["published"]).strftime("%A")}
    return {"mode": "changed"}


def _table_html(name, rows):
    zones = [zone_for(x["zone"]) for x in rows]
    legend = [(z, LEGEND[z]) for z in ("blue", "lilac", "rose") if z in zones]
    body = [[x["rank"], x["team"], x["played"], f"{x['gd']:+d}", x["points"]] for x in rows]
    return r.table(name, COLUMNS, body, zones=zones, legend=legend)


def block(name, rows, decision):
    """The HTML for one league's table, following the decision."""
    mode = decision["mode"]
    if mode == "skip":
        return ""
    if mode == "unchanged":
        return f'<p class="muted"><strong>{r.esc(name)}:</strong> No change since {decision["since"]}.</p>'
    if mode == "full":
        return _table_html(name, rows)
    top, rest = rows[:6], rows[6:]
    html = _table_html(f"{name}: top 6", top)
    yours = [x for x in rest if is_listed(x["id"])]
    if yours:
        line = ", ".join(f"{code(x['id'], x['abbr'])} {ordinal(x['rank'])} ({x['points']} pts)" for x in yours)
        html += f"<p>Your clubs outside the top 6: {r.esc(line)}.</p>"
    return html


def tables_html(tables, state, edition_date, leagues, tuesday_only=()):
    """tables: {league_id: rows or None if the source failed}. leagues: {league_id: display name}.
    Returns (html, new_state). State changes only for tables that were actually shown."""
    new_state, parts = dict(state), []
    for league, name in leagues.items():
        rows = tables.get(league)
        if rows is None:
            parts.append(r.no_data(f"{name} table"))
            continue
        decision = decide(rows, state.get(league), edition_date, tuesday_only=league in tuesday_only)
        parts.append(block(name, rows, decision))
        if decision["mode"] in ("full", "changed"):
            new_state[league] = {"published": edition_date.isoformat(), "rows": signature(rows)}
    return "".join(parts), new_state
