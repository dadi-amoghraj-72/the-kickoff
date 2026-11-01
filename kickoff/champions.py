"""Champions League: matchday scores, notes for the listed clubs, and the full league-phase table."""
from kickoff import notes
from kickoff import render as r
from kickoff.clubs import ARSENAL_ID, is_listed
from kickoff.leaders import surname
from kickoff.sources import espn

COMPETITION = "UEFA Champions League"
TOP_EIGHT, CUT_LINE = 8, 24  # 1-8 go straight to the round of 16, 9-24 play off, 25-36 are out


def results(day):
    """Finished Champions League matches since the last edition. Empty list on a non-matchday."""
    return espn.recent_results(espn.CHAMPIONS_LEAGUE, day)


def in_league_phase(matches):
    return any(m.get("stage") == "league-phase" for m in matches)


def scorers(m, side):
    """'Eze 25', Rice 82'' for one side. An own goal is listed under the team it counted for."""
    parts = []
    for g in m["goals"]:
        if g["side"] == side:
            tag = " (og)" if g["own_goal"] else (" (pen)" if g["penalty"] else "")
            parts.append(f"{surname(g['player'])} {g['minute']}{tag}")
    return ", ".join(parts)


def scores_html(matches, scorecard_for=(ARSENAL_ID,)):
    """One line per match: home team (right-aligned), score, away team (left-aligned).
    A match involving a club in scorecard_for also gets its scorers underneath, each under its own team."""
    if not matches:
        return ""
    items = []
    for m in matches:
        card = bool({m["home"]["id"], m["away"]["id"]} & set(scorecard_for))
        name = lambda side: (f'<span class="mine">{r.esc(m[side]["short"])}</span>'  # noqa: E731
                             if card and m[side]["id"] in scorecard_for else r.esc(m[side]["short"]))
        row = (f'<span class="h">{name("home")}</span><span class="s">{m["home_score"]}–{m["away_score"]}</span>'
               f'<span>{name("away")}</span>')
        if card:
            home, away = scorers(m, "home"), scorers(m, "away")
            row += (f'<span class="gh">{r.esc(home)}</span>' if home else "") + (f'<span class="ga">{r.esc(away)}</span>' if away else "")
        items.append(f"<li>{row}</li>")
    return f'<ul class="scores">{"".join(items)}</ul>'


def zone(rank):
    return "blue" if rank <= TOP_EIGHT else ("lilac" if rank <= CUT_LINE else "rose")


def table_html(rows):
    """The full league-phase table. Zone bars show the three groups, a heavier line marks the cut after 8th and
    24th, and the listed clubs are in bold so they are easy to find. No legend."""
    if len(rows) < CUT_LINE:
        return ""
    body = [[x["rank"], x["team"], x["played"], f"{x['gd']:+d}", x["points"]] for x in rows]
    classes = [" ".join(c for c in ("cut" if x["rank"] in (TOP_EIGHT, CUT_LINE) else "", "mine" if is_listed(x["id"]) else "") if c)
               for x in rows]
    return r.table(f"League Phase After Matchday {max(x['played'] for x in rows)}",
                   [("#", True), ("Team", False), ("P", True), ("GD", True), ("Pts", True)],
                   body, zones=[zone(x["rank"]) for x in rows], row_classes=classes)


def note_facts(matches, rows, previous=None):
    """[(match, facts)] for the matches that get a written note: those with a listed club, Arsenal's excluded."""
    return [(m, notes.match_facts(m, tier, rows, previous, COMPETITION))
            for m, tier in notes.select(espn.CHAMPIONS_LEAGUE, matches)]


def section_html(matches, rows, written):
    """The full Champions League block. written: {match id: {"note": ...}} from notes.write_notes.
    Returns '' when there were no matches, so the block is simply left out."""
    if not matches:
        return ""
    html = "<h3>Champions League</h3>" + scores_html(matches)
    for m in matches:
        if m["id"] in written:
            html += f"<p>{r.bold_names(written[m['id']]['note'], (m['home']['name'], m['away']['name']))}</p>"
    if rows and in_league_phase(matches):
        html += table_html(rows)
    return html
