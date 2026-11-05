"""The round-up box above each table: the same four lines for every league and the Champions League.
Built entirely by code from results and pre-match odds, so it is exact, free and always the same shape."""
from kickoff import render as r


def _favourite(row):
    """(team, chance %) of the pre-match favourite in a match row from overview.matchday_facts."""
    chances = {k: v for k, v in row["pre_match_chances_pct"].items() if k != "draw"}
    team = max(chances, key=chances.get)
    return team, chances[team]


def round_info(table_rows, label="Game week", total=None):
    """Where we are in the season, worked out from the table. The current round is the most games any team has
    played; the games finished in it so far are the teams on that number, halved. total: rounds in the season
    (a double round-robin has 2 x (teams - 1)). None if there is no table."""
    if not table_rows:
        return None
    teams = len(table_rows)
    current = max(x["played"] for x in table_rows)
    so_far = sum(1 for x in table_rows if x["played"] == current) // 2
    return {"label": label, "number": current, "total": total or 2 * (teams - 1), "so_far": so_far, "size": teams // 2}


def lines(facts, round_size, period="day", info=None):
    """[(label, figure, text, sub)] for the box. figure is the highlighted part (may be empty); sub is a small second line under the row (may be empty).
    Rows: the round (Matchday 4/8), Games played, Underdogs won, Biggest upset (only when there was one), Best game (team codes and score, nothing underneath: D's choice)."""
    rows = facts["matches"]
    known = "tally" in facts
    out = []
    if info and info["number"]:
        out.append((info["label"], f"{info['number']}/{info['total']}", "", ""))
    sub = ""
    if info and info["so_far"] < info["size"]:
        sub = "Rest on day 2" if info["label"] == "Matchday" else "Rest still to play"
    elif info and len(rows) < round_size:
        sub = f"{info['label']} complete"
    out.append(("Games played", f"{len(rows)}/{round_size}", "", sub))
    if known and facts["tally"]["clear_favourites"]:
        out.append(("Underdogs won", f"{facts['tally']['upsets']}/{facts['tally']['clear_favourites']}", "", ""))
    elif known:
        out.append(("Underdogs won", "", "No clear favourites", ""))
    else:
        out.append(("Underdogs won", "", "No odds available", ""))
    if known:
        upsets = [x for x in rows if x.get("result_vs_expectation") in ("upset", "big_upset")]
        if upsets:
            top = max(upsets, key=lambda x: _favourite(x)[1])
            team, pct = _favourite(top)
            out.append(("Biggest upset", "", r.dash(top.get("codes") or top["match"]), f"{team} had a {pct}% chance"))
    game = next((x for x in rows if x["match"] == facts.get("game_of_the_night")), None)
    if game:
        out.append(("Best game", "", r.dash(game.get("codes") or game["match"]), ""))
    return out


def html(facts, round_size, period="day", info=None):
    """The box. Empty when there were no matches, so a league with nothing to report has no box."""
    if not facts or not facts["matches"]:
        return ""
    return r.summary_box(lines(facts, round_size, period, info))
