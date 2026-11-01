"""Champions League: matchday scores, notes for the listed clubs, and the full league-phase table."""
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


def scorer_entries(m, side):
    """['Paz 2', 57'', 'Douvikas 49''] for one side: surname, then all that player's minutes. A penalty is tagged
    (pen) and an own goal (OG); an own goal is listed under the team it counted for."""
    order, minutes = [], {}
    for g in m["goals"]:
        if g["side"] == side:
            if g["player"] not in minutes:
                order.append(g["player"])
            tag = " (OG)" if g["own_goal"] else (" (pen)" if g["penalty"] else "")
            minutes.setdefault(g["player"], []).append(f"{g['minute']}{tag}")
    return [f"{surname(p)} {', '.join(minutes[p])}" for p in order]


def scorers(m, side):
    return ", ".join(scorer_entries(m, side))


def scorers_html(m, side):
    """Each scorer kept together on one line, so a long list wraps between players, never inside one."""
    return ", ".join(f'<span class="p">{r.esc(e)}</span>' for e in scorer_entries(m, side))


def scores_html(matches, highlight=(ARSENAL_ID,)):
    """One line per match: home team (right-aligned), score, away team (left-aligned), with the scorers
    underneath, each under their own team. Clubs in `highlight` (Arsenal) have their name in bold."""
    if not matches:
        return ""
    items = []
    for m in matches:
        name = lambda side: (f'<span class="mine">{r.esc(m[side]["short"])}</span>'  # noqa: E731
                             if m[side]["id"] in highlight else r.esc(m[side]["short"]))
        row = (f'<span class="h">{name("home")}</span><span class="s">{m["home_score"]}–{m["away_score"]}</span>'
               f'<span>{name("away")}</span>')
        home, away = scorers_html(m, "home"), scorers_html(m, "away")
        row += (f'<span class="gh">{home}</span>' if home else "") + (f'<span class="ga">{away}</span>' if away else "")
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


def section_html(matches, rows, overview_text=None, box=""):
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
        html += table_html(rows)
    return html
