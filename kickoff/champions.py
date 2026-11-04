"""Champions League: matchday scores, notes for the listed clubs, and the full league-phase table."""
from kickoff import render as r
from kickoff.clubs import is_listed
from kickoff.tables import movement
from kickoff.scoreboard import HIGHLIGHT as scoreboard_highlight  # noqa: F401
from kickoff.scoreboard import scorer_entries, scorers, scorers_html, scores_html  # noqa: F401  (the scoreboard moved; kept importable here)
from kickoff.sources import espn

COMPETITION = "UEFA Champions League"
TOP_EIGHT, CUT_LINE = 8, 24  # 1-8 go straight to the round of 16, 9-24 play off, 25-36 are out


KNOCKOUT_STAGES = {"knockout-round-playoffs": "Knockout Round Play-offs", "round-of-16": "Round of 16", "quarterfinals": "Quarter-finals",
                   "semifinals": "Semi-finals", "final": "Final"}


def is_knockout(m):
    return m.get("stage") in KNOCKOUT_STAGES


def aggregate(legs):
    """{team id: goals over the completed legs}, counted from the leg scores themselves (not ESPN's aggregate field)."""
    agg = {}
    for g in legs:
        if g["completed"]:
            agg[g["home"]["id"]] = agg.get(g["home"]["id"], 0) + g["home_score"]
            agg[g["away"]["id"]] = agg.get(g["away"]["id"], 0) + g["away_score"]
    return agg


def tie_html(stage, legs, goals_of=None, date_fmt=lambda d: f"{d.day} {d:%b}"):
    """One knockout tie as a series-style table (render.series_table): the two teams (the first leg's hosts on the left) with their aggregate
    either side of the word 'aggregate', a row for each leg (1st and 2nd leg made in advance, the date; the score once played; 'after extra
    time' or the shoot-out on the leg that had one) and the scorers under each played leg. A one-match tie (the final) shows its score and says
    'final' instead of 'aggregate'. goals_of(leg id) -> the leg's goals (as in a match record) or None."""
    first = legs[0]
    a_team, b_team = first["home"], first["away"]
    agg = aggregate(legs)
    one = len(legs) == 1 and stage == "final"
    rows = []
    for n in range(1, (1 if one else 2) + 1):
        g = legs[n - 1] if n <= len(legs) else None
        label = "Final" if one else f"{'1st' if n == 1 else '2nd'} leg"
        if g and g["completed"]:
            sc = {g["home"]["id"]: g["home_score"], g["away"]["id"]: g["away_score"]}
            pens, extra = g["pens"], g["status"].endswith("AET") or g["status"].endswith("PEN")
            when = parse_when(g["kickoff"], utc=True)   # a played leg shows the matchday as played in Europe
            tag = " · after extra time" if extra and not pens else ""
            win = "a" if sc[a_team["id"]] > sc[b_team["id"]] else "b" if sc[b_team["id"]] > sc[a_team["id"]] else None
            notes = []
            goals = (goals_of(g["id"]) if goals_of else None) or []
            fake = {"goals": goals}
            for side in ("home", "away"):
                line = scorers_html(fake, side)
                if line:
                    notes.append(r.esc(g[side]["name"]) + ": " + line)
            rows.append({"mid": f"{label} · {date_fmt(when)}{tag}", "a": sc[a_team["id"]], "b": sc[b_team["id"]], "win": win, "notes": notes})
            if pens:
                ph = {g["home"]["id"]: pens[0], g["away"]["id"]: pens[1]}
                rows.append({"mid": "Penalties", "a": ph[a_team["id"]], "b": ph[b_team["id"]], "win": "a" if ph[a_team["id"]] > ph[b_team["id"]] else "b", "notes": []})
        else:
            when = parse_when(g["kickoff"]) if g else None
            rows.append({"mid": f"{label} · " + (f"{date_fmt(when)}, {when:%-I:%M%p}".replace("AM", "am").replace("PM", "pm") + " SGT" if when else "to be scheduled"), "pre": True})
    title = KNOCKOUT_STAGES.get(stage, stage.replace("-", " ").title())
    return r.series_table(title, a_team["name"], b_team["name"], agg.get(a_team["id"], 0), agg.get(b_team["id"], 0), "final" if one else "aggregate", rows)


def parse_when(kickoff, utc=False):
    """A kick-off text like '2026-03-17T20:00Z' as a Singapore-time datetime (the edition is read in Singapore), or as UTC with utc=True."""
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    t = datetime.strptime(kickoff, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
    return t if utc else t.astimezone(ZoneInfo("Asia/Singapore"))


def results(day):
    """Finished Champions League matches since the last edition. Empty list on a non-matchday."""
    return espn.recent_results(espn.CHAMPIONS_LEAGUE, day)


def in_league_phase(matches):
    return any(m.get("stage") == "league-phase" for m in matches)


def zone(rank):
    return "blue" if rank <= TOP_EIGHT else ("lilac" if rank <= CUT_LINE else "rose")


def table_html(rows, before=None):
    """The full league-phase table. Zone bars show the three groups, a heavier line marks the cut after 8th and
    24th, and the listed clubs are in bold so they are easy to find. No legend."""
    if len(rows) < CUT_LINE:
        return ""
    body = [[x["rank"], x.get("short") or x["team"], x["played"], f"{x['gd']:+d}", x["points"], movement(x, before)] for x in rows]
    classes = [" ".join(c for c in ("cut" if x["rank"] in (TOP_EIGHT, CUT_LINE) else "", "mine" if is_listed(x["id"]) else "") if c)
               for x in rows]
    return r.table(f"League Phase After Matchday {max(x['played'] for x in rows)}",
                   [("#", True), ("Team", False), ("P", True), ("GD", True), ("Pts", True), ("+/-", True)],
                   body, zones=[zone(x["rank"]) for x in rows], row_classes=classes)


def section_html(matches, rows, overview_text=None, box="", before=None, legs_fn=None, goals_fn=None, performers=""):
    """The full Champions League block: the overview first, then the scoreboard, then the league-phase table.
    Returns '' when there were no matches, so the block is simply left out."""
    if not matches:
        return ""
    names = [n for m in matches for side in ("home", "away") for n in (m[side]["name"], m[side]["short"])]
    html = "<h3>Champions League</h3>" + box
    if overview_text:
        html += f"<p>{r.bold_names(overview_text, names)}</p>"
    league_matches = [m for m in matches if not (legs_fn and is_knockout(m))]
    html += scores_html(league_matches)
    done = set()
    for m in matches:                              # knockout ties: one series table per tie, the legs found from the team's schedule
        if not (legs_fn and is_knockout(m)) or frozenset((m["home"]["id"], m["away"]["id"])) in done:
            continue
        done.add(frozenset((m["home"]["id"], m["away"]["id"])))
        try:
            legs = legs_fn(m)
        except Exception:
            legs = None
        if not legs:
            html += scores_html([m])               # no schedule: the plain scoreboard line, nothing lost
            continue
        have = {x["id"]: x for x in matches}

        def goals_of(leg_id, have=have):
            if leg_id in have:
                return have[leg_id]["goals"]
            try:
                return goals_fn(leg_id)["goals"] if goals_fn else None
            except Exception:
                return None
        html += tie_html(m["stage"], legs, goals_of)
    html += performers                             # the best performers of the night, right under the scores
    if rows and in_league_phase(matches):
        html += table_html(rows, before)
    return html
