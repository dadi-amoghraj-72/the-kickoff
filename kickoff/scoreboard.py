"""The scoreboard used by every league and the Champions League: one aligned line per match, scorers underneath.

Home team on the right-aligned left, gold score in the middle, away team on the left-aligned right. Each scorer sits
under his own team, a repeat scorer is listed once with all his minutes, penalties are tagged (pen) and own goals
(OG). Clubs in `highlight` have their names in bold."""
from kickoff import render as r
from kickoff.clubs import CLUBS
from kickoff.leaders import surname


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


# The clubs in bold: our 17 listed clubs and Arsenal Women (ESPN id 19973).
HIGHLIGHT = frozenset(CLUBS) | {"19973"}


DOG = '<span class="dog" title="Underdog win">*</span>'      # the same asterisk as the NFL and NBA tables


def scores_html(matches, highlight=HIGHLIGHT):
    """One line per match: home team (right-aligned), score, away team (left-aligned), with the scorers
    underneath, each under their own team. Clubs in `highlight` have their name in bold."""
    if not matches:
        return ""
    items = []
    for m in matches:
        star = lambda side: DOG if m.get("dog") == side else ""  # noqa: E731
        name = lambda side: ((f'<span class="mine">{r.esc(m[side]["short"])}</span>'  # noqa: E731
                              if m[side]["id"] in highlight else r.esc(m[side]["short"])) + star(side))
        row = (f'<span class="h">{name("home")}</span><span class="s">{m["home_score"]}–{m["away_score"]}</span>'
               f'<span>{name("away")}</span>')
        home, away = scorers_html(m, "home"), scorers_html(m, "away")
        row += (f'<span class="gh">{home}</span>' if home else "") + (f'<span class="ga">{away}</span>' if away else "")
        items.append(f"<li>{row}</li>")
    key = '<p class="key"><span class="dog">*</span> Underdog won</p>' if any(m.get("dog") for m in matches) else ""
    return f'<ul class="scores">{"".join(items)}</ul>{key}'
