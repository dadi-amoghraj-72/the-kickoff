"""Champions League: matchday scores, notes for the listed clubs, and the full league-phase table."""
from kickoff import render as r
from kickoff.clubs import is_listed
from kickoff.tables import movement
from kickoff.scoreboard import HIGHLIGHT as scoreboard_highlight  # noqa: F401
from kickoff.scoreboard import scorer_entries, scorers, scorers_html, scores_html  # noqa: F401  (the scoreboard moved; kept importable here)
from kickoff.sources import espn

COMPETITION = "UEFA Champions League"
TOP_EIGHT, CUT_LINE = 8, 24  # 1-8 go straight to the round of 16, 9-24 play off, 25-36 are out


def results(day):
    """Finished Champions League matches since the last edition. Empty list on a non-matchday."""
    return espn.recent_results(espn.CHAMPIONS_LEAGUE, day)


def in_league_phase(matches):
    return any(m.get("stage") == "league-phase" for m in matches)


def zone(rank):
    return "blue" if rank <= TOP_EIGHT else ("lilac" if rank <= CUT_LINE else "rose")


def table_html(rows, before=None, colours=None):
    """The full league-phase table. Zone bars show the three groups, a heavier line marks the cut after 8th and
    24th, and the listed clubs are in bold so they are easy to find. No legend."""
    if len(rows) < CUT_LINE:
        return ""
    body = [[x["rank"], x.get("short") or x["team"], x["played"], f"{x['gd']:+d}", x["points"], movement(x, before)] for x in rows]
    classes = [" ".join(c for c in ("cut" if x["rank"] in (TOP_EIGHT, CUT_LINE) else "", "mine" if is_listed(x["id"]) else "") if c)
               for x in rows]
    html = r.table(f"League Phase After Matchday {max(x['played'] for x in rows)}",
                   [("#", True), ("Team", False), ("P", True), ("GD", True), ("Pts", True), ("+/-", True)],
                   body, zones=[zone(x["rank"]) for x in rows], row_classes=classes)
    return r.paint(html, {(x.get("short") or x["team"]): colours[x["id"]] for x in rows if x["id"] in (colours or {})}) if colours else html


def section_html(matches, rows, overview_text=None, box="", before=None, colours=None):
    """The full Champions League block: the overview first, then the scoreboard, then the league-phase table.
    Returns '' when there were no matches, so the block is simply left out."""
    if not matches:
        return ""
    names = [n for m in matches for side in ("home", "away") for n in (m[side]["name"], m[side]["short"])]
    html = "<h3>Champions League</h3>" + box
    if overview_text:
        html += f"<p>{r.bold_names(overview_text, names)}</p>"
    html += scores_html(matches)
    if rows and in_league_phase(matches):
        html += table_html(rows, before, colours)
    return html
