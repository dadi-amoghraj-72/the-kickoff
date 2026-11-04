"""The headlines for the Telegram ping and the archive: the stories of the morning picked from every match of every competition, by code, no AI.

Every finished match gets a score: the size of the win and the goals, a comeback, an upset against the odds, and a bonus when one of D's clubs
(kickoff/clubs.py) played. Arsenal's own result always comes first. The top three distinct matches follow, a competition named in front of each."""
from kickoff import clubs

LISTED_BONUS = 3
BIG_RESULT = 3          # a margin of this many goals or more is a story in itself


def score(row):
    """How much of a story one match is (see the module note). row: a matchday_facts row."""
    margin = row.get("margin", 0)
    s = 2 * margin + row["total_goals"] + (3 if row.get("comeback") else 0) + {"big_upset": 4, "upset": 3}.get(row.get("result_vs_expectation"), 0)
    if margin >= BIG_RESULT:
        s += 2
    if any(clubs.is_listed(t) for t in row.get("teams", []) if t):
        s += LISTED_BONUS
    return s


def pick(overviews, arsenal=None, limit=3):
    """overviews: {competition name: facts from overview.matchday_facts}; arsenal: Arsenal's result line ('Arsenal 2–1 Brentford') or None.
    Returns up to `limit` headline strings."""
    out = [f"Arsenal: {arsenal}"] if arsenal else []
    own = (arsenal or "").replace("–", "-")
    found = []
    for i, (comp, f) in enumerate(overviews.items()):
        for j, row in enumerate(f.get("matches", [])):
            if own and row["match"].replace("–", "-") == own:
                continue                                    # Arsenal's own match is already the first headline
            found.append((-score(row), i, j, f"{comp.replace('UEFA ', '')}: {row['match']}"))
    for *_, text in sorted(found):
        if len(out) >= limit:
            break
        out.append(text)
    return out[:limit]
