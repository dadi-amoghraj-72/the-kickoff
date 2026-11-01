"""International football: appears only around an international break, and only for competitive games.

The Nations League gets group tables and stake lines. Qualifiers and finals involving a top-30 side, Singapore or India
get a scoreboard. Friendlies are excluded."""
from datetime import timedelta

from kickoff import natleague, rankings, scoreboard
from kickoff import render as r
from kickoff.http import safe
from kickoff.sources import espn
from kickoff.sources import natleague as src

AHEAD = timedelta(hours=30)   # a matchday that starts within this long is "today's" matchday
ALWAYS = {"singapore", "india"}
# Competitive international competitions (never friendlies). Slugs are ESPN's.
COMPETITIONS = {"fifa.worldq.uefa": "World Cup qualifiers (Europe)", "fifa.worldq.afc": "World Cup qualifiers (Asia)",
                "fifa.worldq.conmebol": "World Cup qualifiers (South America)", "fifa.worldq.caf": "World Cup qualifiers (Africa)",
                "fifa.worldq.concacaf": "World Cup qualifiers (CONCACAF)", "uefa.euroq": "European Championship qualifiers",
                "afc.asian.cup": "AFC Asian Cup", "concacaf.nations.league": "CONCACAF Nations League", "caf.nations": "Africa Cup of Nations",
                "uefa.euro": "European Championship", "fifa.world": "World Cup"}


def wanted(match, top30):
    """True if either side is a top-30 team, Singapore or India."""
    names = [match["home"]["name"], match["away"]["name"]]
    return rankings.in_top(names, top30) or any(rankings.normalise(n) in ALWAYS for n in names)


def other_results(day, top30):
    """[(competition name, [matches])]: finished competitive matches since the last edition, other than the Nations League."""
    out = []
    for slug, name in COMPETITIONS.items():
        found = safe(f"{name} results", espn.recent_results, slug, day)
        mine = [m for m in found or [] if wanted(m, top30)]
        if mine:
            out.append((name, mine))
    return out


def active(day, now, nl_window):
    """True if the Nations League has results in this edition's window or a match kicking off within 30 hours."""
    if nl_window:
        return True
    soon = []
    for offset in (0, 1):
        soon += safe("Nations League today", espn.get_matches_on, src.LEAGUE, (now + timedelta(days=offset)).date()) or []
    return any(not m["completed"] and now <= espn.parse_time(m["kickoff"]) <= now + AHEAD for m in soon) if soon else False


def run(day, now, client=None, saved_top30=None):
    """{"html", "usage", "top30": new record or None, "problems"}. Empty html outside an international break."""
    problems, usage = [], {"input": 0, "output": 0}
    nl_window = safe("Nations League results", espn.recent_results, src.LEAGUE, day) or []
    top30, new_top30 = None, None
    try:
        top30, new_top30 = rankings.load(day, saved_top30)
    except Exception as e:  # the ranking is a helper: without it only League A and the always-teams are shown
        problems.append(f"top-30 ranking: {type(e).__name__}")
    parts = ""
    if active(day, now, nl_window):
        groups = safe("Nations League groups", src.get_groups)
        if groups:
            remaining = src.remaining_fixtures(natleague.groups_to_show(groups, top30))
            html, usage, _ = natleague.build(groups, top30, nl_window, remaining, client)
            if html:
                parts += "<h3>UEFA Nations League</h3>" + html
        else:
            problems.append("Nations League groups")
    for name, matches in other_results(day, top30):
        parts += f"<h3>{r.esc(name)}</h3>" + scoreboard.scores_html(matches)
    html = f"<h3>International Football</h3>{parts}" if parts else ""
    return {"html": html, "usage": usage, "top30": new_top30, "problems": problems}
