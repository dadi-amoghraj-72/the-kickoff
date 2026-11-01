"""Top Scorer, Top Assists and Top Clean Sheets for a league, and the running clean-sheet count."""
import copy
import sys

from kickoff import render as r
from kickoff.clubs import code

PARTICLES = {"de", "da", "di", "del", "della", "dos", "das", "do", "van", "von", "der", "den", "ter", "ten",
             "le", "la", "el", "al", "bin", "ben", "mac", "st."}
SUFFIXES = {"jr", "jr.", "júnior", "junior", "sr", "sr."}


def surname(full_name):
    """Surname only: 'Erling Haaland' -> 'Haaland', 'Kevin De Bruyne' -> 'De Bruyne', 'Vinícius Júnior' stays whole."""
    parts = full_name.split()
    if len(parts) < 2:
        return full_name
    i = len(parts) - 1
    if parts[i].lower() in SUFFIXES and i > 0:
        i -= 1
    while i > 1 and parts[i - 1].lower() in PARTICLES:
        i -= 1
    return " ".join(parts[i:]) if i > 0 else full_name


def count_clean_sheets(cs_state, league, matches, keepers_fn):
    """Add new clean sheets to the running count and return the updated state (the input is untouched).
    A clean sheet goes to the starting goalkeeper of a team that conceded nothing. Each match is counted
    once, however many times it is seen. If a match's lineup can't be fetched, it is left for the next run."""
    state = copy.deepcopy(cs_state)
    lg = state.setdefault(league, {"matches": [], "keepers": {}})
    done = set(lg["matches"])
    for m in matches:
        if m["id"] in done or not m["completed"]:
            continue
        shut_out = [m[side]["id"] for side, other in (("home", "away_score"), ("away", "home_score")) if m[other] == 0]
        if shut_out:
            try:
                keepers = keepers_fn(m)
            except Exception as e:
                print(f"WARN  lineup unavailable for match {m['id']}: {e}", file=sys.stderr)
                continue
            for team_id in shut_out:
                if team_id not in keepers:
                    print(f"WARN  no starting keeper found for team {team_id} in match {m['id']}", file=sys.stderr)
                    continue
                athlete_id, name = keepers[team_id]
                k = lg["keepers"].setdefault(athlete_id, {"name": name, "team": team_id, "cs": 0})
                k["cs"] += 1
                k["team"] = team_id  # follows the keeper if he moves club
        lg["matches"].append(m["id"])
    return state


def top_clean_sheets(cs_state, league):
    keepers = list(cs_state.get(league, {}).get("keepers", {}).values())
    if not keepers:
        return []
    best = max(k["cs"] for k in keepers)
    return sorted((k for k in keepers if k["cs"] == best), key=lambda k: k["name"])


def leaders_html(scorers, assists, sheets):
    """Each argument is a list of {"name", "club", "value"}, where club is a short code.
    One leader reads 'Haaland (MCI) 9'. A tie reads '4 Tied: Gross (BHA), Evanilson (BOU), Rice (ARS)'."""
    def line(label, entries):
        if not entries:
            return ""
        who = ", ".join(f"{r.esc(surname(e['name']))} ({r.esc(e['club'])})" for e in entries)
        value = entries[0]["value"]
        body = f'<span class="n">{value} Tied</span>: {who}' if len(entries) > 1 else f'{who} <span class="n">{value}</span>'
        return f'<li><span class="lbl">{label}</span><span>{body}</span></li>'
    rows = line("Top Scorer", scorers) + line("Top Assists", assists) + line("Top Clean Sheets", sheets)
    return f'<ul class="leaders">{rows}</ul>' if rows else ""


def league_block(league, year, rows, cs_state):
    """The Top Scorer / Assists / Clean Sheets lines for one league, as HTML."""
    from kickoff.sources import espn  # imported here so the pure logic above has no network dependency
    abbr = {x["id"]: x["abbr"] for x in rows}
    club = lambda team_id: code(team_id, abbr.get(team_id, "?"))  # noqa: E731
    found = espn.get_leaders(league, year)

    def entries(key):
        return [{"name": espn.get_athlete_name(league, year, x["athlete_id"]),
                 "club": club(x["team_id"]), "value": x["value"]} for x in found[key]]

    sheets = [{"name": k["name"], "club": club(k["team"]), "value": k["cs"]}
              for k in top_clean_sheets(cs_state, league)]
    return leaders_html(entries("goals"), entries("assists"), sheets)
