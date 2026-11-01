"""Champions League: matchday scores, notes for the listed clubs, and the league-phase table."""
from kickoff import notes
from kickoff import render as r
from kickoff.clubs import code, is_listed
from kickoff.sources import espn
from kickoff.tables import ordinal

COMPETITION = "UEFA Champions League"
TOP_EIGHT, CUT_LINE = 8, 24  # 1-8 go straight to the round of 16, 9-24 play off, 25-36 are out


def results(day):
    """Finished Champions League matches since the last edition. Empty list on a non-matchday."""
    return espn.recent_results(espn.CHAMPIONS_LEAGUE, day)


def in_league_phase(matches):
    return any(m.get("stage") == "league-phase" for m in matches)


def scores_html(matches):
    """One line per match: home team (right-aligned), score, away team (left-aligned)."""
    if not matches:
        return ""
    items = "".join(f'<li><span class="h">{r.esc(m["home"]["short"])}</span>'
                    f'<span class="s">{m["home_score"]}–{m["away_score"]}</span>'
                    f'<span>{r.esc(m["away"]["short"])}</span></li>' for m in matches)
    return f'<ul class="scores">{items}</ul>'


def zone(rank):
    return "blue" if rank <= TOP_EIGHT else ("lilac" if rank <= CUT_LINE else "rose")


def table_html(rows):
    """Top 8, the 24th-place cut line, and a line for the listed clubs the table doesn't already show."""
    if len(rows) < CUT_LINE:
        return ""
    shown = rows[:TOP_EIGHT] + [None] + [rows[CUT_LINE - 1]]
    body = [None if x is None else [x["rank"], x["team"], x["played"], f"{x['gd']:+d}", x["points"]] for x in shown]
    zones = [None if x is None else zone(x["rank"]) for x in shown]
    md = max(x["played"] for x in rows)
    html = r.table(f"League Phase After Matchday {md}", [("#", True), ("Team", False), ("P", True), ("GD", True), ("Pts", True)],
                   body, zones=zones)
    cut = rows[CUT_LINE - 1]
    html += (f'<p class="muted">Top 8 go straight to the round of 16, 9th to 24th play off. '
             f'The cut line is {r.esc(cut["team"])} in 24th on {cut["points"]} points.</p>')
    visible = {x["id"] for x in rows[:TOP_EIGHT]} | {cut["id"]}
    yours = [x for x in rows if is_listed(x["id"]) and x["id"] not in visible]
    if yours:
        line = ", ".join(f"{code(x['id'], x['abbr'])} {ordinal(x['rank'])} ({x['points']} pts)" for x in yours)
        html += f"<p>Your clubs elsewhere in the table: {r.esc(line)}.</p>"
    return html


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
            html += f"<p>{r.esc(written[m['id']]['note'])}</p>"
    if rows and in_league_phase(matches):
        html += table_html(rows)
    return html
