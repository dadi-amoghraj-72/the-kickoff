"""The Nations League block: group tables with zone bars, and 'what's at stake' worked out from every possible result.

Code decides every fact: the zone rules (read from ESPN's own notes), which groups are shown, and what each team can
still finish. Claude may only phrase what that calculation proves."""
import itertools
import re

from kickoff import render as r

PHRASES = {  # ESPN's zone text -> how we say it, and the table bar colour
    "qualifies for qfs": ("the quarter-finals", "blue"), "promotion": ("promotion", "blue"),
    "promotion playoffs": ("the promotion play-offs", "lilac"), "relegation playoffs": ("the relegation play-offs", "lilac"),
    "relegation": ("relegation", "rose"), "relegation or playoffs": ("relegation or the relegation play-offs", "rose"),
}
LEGEND = {"A": {"blue": "Quarter-finals", "lilac": "Relegation play-off", "rose": "Relegated"},
          "other": {"blue": "Promoted", "lilac": "Play-offs", "rose": "Relegated"}}


def parse_rules(groups):
    """{(league letter, rank): ESPN zone text}, read from the League A rows' notes. A note looks like
    'A: Qualifies for QFs; B-D: Promotion playoffs' or 'A, B: Relegation; C: Relegation or playoffs'."""
    rules = {}
    for g in groups:
        if g["league"] != "A":
            continue
        for row in g["rows"]:
            for part in (row["note"] or "").split(";"):
                if ":" not in part:
                    continue
                letters, text = part.split(":", 1)
                for token in letters.split(","):
                    token = token.strip()
                    m = re.fullmatch(r"([A-D])-([A-D])", token)
                    span = [chr(c) for c in range(ord(m.group(1)), ord(m.group(2)) + 1)] if m else [token]
                    for letter in span:
                        rules.setdefault((letter, row["rank"]), text.strip())
        break
    return rules


def zone(rules, letter, rank):
    """(phrase, colour) for a finishing position, or (None, None) when it leads nowhere."""
    return PHRASES.get((rules.get((letter, rank)) or "").lower(), (None, None))


# ---- Every possible finish ------------------------------------------------------------------

def finishes(rows, remaining):
    """{team id: (best, worst, tie_spans)}: the best and worst place each team can finish in, over every win, draw and
    loss for the remaining matches [(home id, away id)]. Teams level on points are treated as able to take any of the
    places between them, because goal difference and head-to-head decide those and are not guessed. tie_spans is the
    set of (first, last) place ranges in which the team was level on points."""
    base = {x["id"]: x["points"] for x in rows}
    best, worst, spans = {i: len(rows) for i in base}, {i: 1 for i in base}, {i: set() for i in base}
    for outcome in itertools.product("HDA", repeat=len(remaining)):
        pts = dict(base)
        for (h, a), o in zip(remaining, outcome):
            pts[h] += 3 if o == "H" else (1 if o == "D" else 0)
            pts[a] += 3 if o == "A" else (1 if o == "D" else 0)
        for i, p in pts.items():
            ahead = sum(1 for q in pts.values() if q > p)
            level = sum(1 for q in pts.values() if q == p)
            best[i] = min(best[i], ahead + 1)
            worst[i] = max(worst[i], ahead + level)
            if level > 1:
                spans[i].add((ahead + 1, ahead + level))
    return {i: (best[i], worst[i], spans[i]) for i in base}


def analyse(group, remaining_matches, rules):
    """Facts for one group. remaining_matches: parsed matches not yet played (home/away dicts with ids and names)."""
    rows, letter = group["rows"], group["league"]
    n = len(rows)
    expected = n * (n - 1) - sum(x["played"] for x in rows) // 2   # matches that must still be played in a home-and-away group
    if len(remaining_matches) != expected:
        # We have not found every remaining fixture, so any finishing position we calculated could be wrong. Say so.
        return {"group": group["name"], "league": letter, "fixtures_confirmed": False, "matchdays_left": None, "remaining": [],
                "expected_remaining_matches": expected, "found_remaining_matches": len(remaining_matches), "teams": [
                    {"team": x["team"], "points": x["points"], "played": x["played"], "position_now": x["rank"], "best_finish": None,
                     "worst_finish": None, "settled": None, "nothing_at_stake": False, "tiebreak_decides_zone": False} for x in rows]}
    pairs = [(m["home"]["id"], m["away"]["id"]) for m in remaining_matches]
    fin = finishes(rows, pairs)
    teams = []
    for x in rows:
        best, worst, spans = fin[x["id"]]
        zones = {zone(rules, letter, p)[0] for p in range(best, worst + 1)}
        boundary = any(len({zone(rules, letter, p)[0] for p in range(a, b + 1)}) > 1 for a, b in spans)
        only = next(iter(zones)) if len(zones) == 1 else None
        teams.append({"team": x["team"], "points": x["points"], "played": x["played"], "position_now": x["rank"],
                      "best_finish": best, "worst_finish": worst,
                      "settled": only,                       # a zone this team is certain to land in (None if not certain)
                      "nothing_at_stake": zones == {None},   # every place it can finish in leads nowhere
                      "tiebreak_decides_zone": boundary})
    left = max((len([1 for p in pairs if x["id"] in p]) for x in rows), default=0)
    return {"group": group["name"], "league": letter, "fixtures_confirmed": True, "matchdays_left": left,
            "remaining": [f"{m['home']['name']} v {m['away']['name']}" for m in remaining_matches], "teams": teams}


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def stake_lines(facts):
    """The plain, code-written 'what's at stake' lines (two or three). Used as the facts Claude phrases and as the fallback."""
    if not facts.get("fixtures_confirmed", True):
        return ["Remaining fixtures could not be confirmed, so no finishing positions are given."]
    teams, out = facts["teams"], []
    left = facts["matchdays_left"]
    header = "The group is finished." if left == 0 else f"{left} matchday{'s' if left != 1 else ''} left."
    secured = {}
    for t in teams:
        if t["settled"]:
            secured.setdefault(t["settled"], []).append(t["team"])
    if secured:
        out.append("; ".join(f"{' and '.join(ts)} {'have' if len(ts) > 1 else 'has'} secured {phrase}" for phrase, ts in secured.items()) + ".")
    open_teams = [t for t in teams if not t["settled"] and not t["nothing_at_stake"]]
    if open_teams:
        span = lambda t: ordinal(t["best_finish"]) if t["best_finish"] == t["worst_finish"] else f"{ordinal(t['best_finish'])} to {ordinal(t['worst_finish'])}"  # noqa: E731
        out.append("Still open: " + "; ".join(f"{t['team']} ({span(t)})" for t in open_teams) + ".")
    if any(t["tiebreak_decides_zone"] for t in teams):
        out.append("Some places could be decided by goal difference or head-to-head, not by points alone.")
    if not out:
        return [header]
    out[0] = f"{header} {out[0]}"  # the header joins the first line, so a group never has more than three lines
    return out


# ---- Display --------------------------------------------------------------------------------

COLUMNS = [("#", True), ("Team", False), ("P", True), ("W", True), ("D", True), ("L", True), ("GD", True), ("Pts", True)]


def table_html(group, rules):
    rows = group["rows"]
    zones = [zone(rules, group["league"], x["rank"])[1] for x in rows]
    body = [[x["rank"], x["team"], x["played"], x["won"], x["drawn"], x["lost"], f"{x['gd']:+d}", x["points"]] for x in rows]
    legend_for = LEGEND["A" if group["league"] == "A" else "other"]
    legend = [(z, legend_for[z]) for z in ("blue", "lilac", "rose") if z in zones]
    return r.table(f"{group['name']} · League {group['league']}", COLUMNS, body, zones=zones, legend=legend)


def group_html(group, rules, lines):
    text = "".join(f"<p>{r.bold_names(line, [x['team'] for x in group['rows']] + [x['short'] for x in group['rows']])}</p>" for line in lines)
    return table_html(group, rules) + text


# ---- Which groups to show ----------------------------------------------------------------------

def groups_to_show(groups, top30):
    """All four League A groups, plus any League B or C group containing a top-30 side. Without a ranking, League A only."""
    from kickoff import rankings
    out = []
    for g in groups:
        if g["league"] == "A":
            out.append(g)
        elif g["league"] in ("B", "C") and top30 and rankings.in_top([x["team"] for x in g["rows"]], top30):
            out.append(g)
    return out


# ---- Claude phrases the stakes; code checks every line -----------------------------------------

import json  # noqa: E402

from kickoff import notes, scoreboard, settings  # noqa: E402
from kickoff.sources.natleague import group_of  # noqa: E402

SYSTEM = """You write the "what's at stake" lines under each UEFA Nations League group table for The Kickoff, a daily
digest read by one football fan in Singapore. You are given, for each group, exact facts worked out by code from every
possible result of the remaining matches, plus "code_lines": the same facts in plain words.

Write TWO or THREE short lines per group (one is enough if there is little to say) in your own words, using only those facts:
- Each line is one sentence of at most 30 words. Use team names exactly as given. Every number must come from the facts.
- Only say a team has "secured", is "through", "safe" or "guaranteed" something if its "settled" field names that zone.
  Otherwise say what it can still finish, using best_finish and worst_finish.
- If any team has "tiebreak_decides_zone" true, one line must say plainly that some places could be decided by goal
  difference or head-to-head, not by points alone. Never guess how a tie would fall.
- Add nothing from memory: no form, history, predictions or opinions. No hype, no emojis.
Return the lines for every group, using the group's name as its id."""
SCHEMA = {"type": "object", "properties": {"groups": {"type": "array", "items": {
    "type": "object", "properties": {"group": {"type": "string"}, "lines": {"type": "array", "items": {"type": "string"}}},
    "required": ["group", "lines"], "additionalProperties": False}}}, "required": ["groups"], "additionalProperties": False}
CERTAIN = re.compile(r"\b(secured?|through|clinched?|guaranteed|certain|safe|confirmed)\b", re.I)


def check_lines(lines, facts, code_lines):
    """Problems with Claude's lines for one group. Empty means they can be shown."""
    problems = []
    if not 1 <= len(lines) <= 3:
        problems.append(f"{len(lines)} lines instead of one to three")
    f = {"facts": facts, "code_lines": code_lines, "length": notes.TIERS["news"][0]}
    for line in lines:
        problems += notes.check_note(line, f)
        if CERTAIN.search(line):
            for t in facts["teams"]:
                if t["team"] in line and not t["settled"]:
                    problems.append(f"says {t['team']} is certain of something, but the calculation leaves it open")
    if any(t["tiebreak_decides_zone"] for t in facts["teams"]) and not re.search(r"goal difference|head-to-head", " ".join(lines), re.I):
        problems.append("does not mention that a tie-break could decide places")
    return sorted(set(problems))


def phrase(client, facts_by_group, code_lines):
    """({group name: lines}, usage). Every group falls back to its code-written lines if Claude's fail the checks twice."""
    out, total, pending = {}, {"input": 0, "output": 0}, list(facts_by_group)
    problems = {}
    for attempt in (1, 2):
        if not pending:
            break
        payload = [{"group": n, "facts": facts_by_group[n], "code_lines": code_lines[n],
                    **({"problems_with_your_last_lines": problems[n]} if n in problems else {})} for n in pending]
        extra = "" if attempt == 1 else "Some of your earlier lines broke a rule (see problems). Rewrite those groups.\n"
        obj, usage = notes.call_json(client, SYSTEM, SCHEMA, extra + "Groups:\n" + json.dumps(payload, ensure_ascii=False, indent=1),
                                     model=settings.NEWS_MODEL)
        total = {k: total[k] + usage[k] for k in total}
        got = {x["group"]: x["lines"] for x in (obj or {}).get("groups", [])} if isinstance(obj, dict) else {}
        redo = []
        for n in pending:
            lines = got.get(n)
            bad = check_lines(lines, facts_by_group[n], code_lines[n]) if lines else ["no lines returned"]
            if bad:
                problems[n] = bad
                redo.append(n)
            else:
                out[n] = lines
        pending = redo
    for n in pending:
        out[n] = code_lines[n]  # the plain, code-written lines: safe by construction
    return out, total


def build(groups, top30, window_matches, all_matches, client=None):
    """The Nations League block: scoreboard of the window's results, then each shown group's table and stake lines.
    window_matches: finished matches since the last edition. all_matches: every match known (to find the remaining ones).
    Returns (html, usage, facts_by_group). Empty html if no group is shown."""
    rules = parse_rules(groups)
    shown = groups_to_show(groups, top30)
    if not shown:
        return "", {"input": 0, "output": 0}, {}
    owner = group_of(groups)
    facts, code = {}, {}
    for g in shown:
        remaining = [m for m in all_matches if not m["completed"] and owner.get(m["home"]["id"]) is g]
        facts[g["name"]] = analyse(g, remaining, rules)
        code[g["name"]] = stake_lines(facts[g["name"]])
    usage = {"input": 0, "output": 0}
    lines = code
    sure = {n: f for n, f in facts.items() if f.get("fixtures_confirmed", True)}  # Claude only phrases what is proven
    if client and sure:
        said, usage = phrase(client, sure, {n: code[n] for n in sure})
        lines = {**code, **said}
    shown_ids = {x["id"] for g in shown for x in g["rows"]}
    results = [m for m in window_matches if m["home"]["id"] in shown_ids and m["completed"]]
    played = max((x["played"] for g in shown for x in g["rows"]), default=0)
    head = f'<p class="muted">Matchday {played} of 6 played</p>'
    if top30:
        head += f'<p class="muted">League B and C groups are shown when they contain a top-30 side (ranking: {r.esc(top30["source"])}).</p>'
    html = head + scoreboard.scores_html(results) + "".join(group_html(g, rules, lines[g["name"]]) for g in shown)
    return html, usage, facts
