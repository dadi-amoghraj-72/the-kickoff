"""The matchday overview: what the night meant. Code finds the insights, Claude only phrases them.

Code works out, for every match: the pre-match chances (from betting odds), whether the result went with or
against them, how dramatic it was, and which game was the game of the night. Claude is given those labels and
ESPN's own match-report headlines for context, and is not allowed to claim anything the labels don't support.
"""
import re

from kickoff import notes, settings
from kickoff.http import safe
from kickoff.sources import espn

SYSTEM = """You write the matchday overview for The Kickoff, a personal daily sports digest read by one football fan in Singapore.
The reader already sees every score and every scorer in a table right below your text, so do NOT list results.
Say what the night meant: how the favourites fared overall, the biggest surprise, the game of the night, and any
standout player or storyline.

Voice: warm, specific and with a point of view, in your own words. British spelling. No emojis, no exclamation marks,
no clichés such as "clinical", "masterclass" or "thriller".

Hard rules:
- Use ONLY the facts supplied. Add nothing from memory.
- Call a result an "upset" or "shock" ONLY if its result_vs_expectation is "upset" or "big_upset". A "close_match"
  had no clear favourite, so never describe it as a surprise. Mention favourites only as the labels show them.
- If "expectations" says "unavailable", say nothing about favourites or upsets.
- You may quote pre-match chances only as the whole percentages given.
- For context about managers, pressure or reputation, use ONLY what appears in a match's "recap". Paraphrase it:
  never copy a run of more than five words from a recap.
- Do not mention cities, stadiums or countries unless they appear in the facts (no "in Lisbon", no "at the Allianz").
- Say nothing about anyone's history, form or reputation unless the facts state it: no "former club", no "perfect start"
  (use it only when a team's "perfect_start" is true), no records or streaks. Describe goals only from each match's "goals"
  list; the "winning_goal" is the goal that decided the match, and a late goal that only reduced a deficit decided nothing.
- Use club and player names exactly as they appear in the facts. Every number must come from the facts.
- Write minutes in words ("the 88th minute"), never with symbols such as ' or +.
- Follow the "length" instruction: one short paragraph, no lists."""

SCHEMA = {"type": "object", "properties": {"overview": {"type": "string"}},
          "required": ["overview"], "additionalProperties": False}

DECIDING = re.compile(r"\b(decisive|decider|winner|winning|clinch\w*|sealed|settled)\b", re.I)
MINUTE = re.compile(r"\b(\d+)(?:st|nd|rd|th) minute\b", re.I)
UPSET_WORDS = re.compile(r"\b(upsets?|shocks?|shocked|stunn\w*|surpris\w*|sensation\w*)\b", re.I)
FAVOURITE_WORDS = re.compile(r"\b(favourites?|favoured|underdogs?|expected|expectations?)\b", re.I)


# ---- Expectations from betting odds ------------------------------------------------------------

def _prob(moneyline):
    """American odds to a raw probability: +140 -> 0.417, -275 -> 0.733."""
    ml = float(moneyline)
    return 100 / (ml + 100) if ml > 0 else -ml / (-ml + 100)


def chances(pickcenter):
    """{"home": %, "draw": %, "away": %} as whole percentages, with the bookmaker's margin removed. None if no odds."""
    for rec in pickcenter or []:
        try:
            raw = {"home": _prob(rec["homeTeamOdds"]["moneyLine"]), "draw": _prob(rec["drawOdds"]["moneyLine"]),
                   "away": _prob(rec["awayTeamOdds"]["moneyLine"])}
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue
        total = sum(raw.values())
        return {k: round(v / total * 100) for k, v in raw.items()}
    return None


def winner_side(m):
    return "home" if m["home_score"] > m["away_score"] else ("away" if m["away_score"] > m["home_score"] else "draw")


def verdict(m, pct):
    """How the result sat against the pre-match chances. A 'clear favourite' has at least a 50% chance."""
    if not pct:
        return None
    fav = max(("home", "away"), key=lambda s: pct[s])
    if pct[fav] < 50:
        return "close_match"
    won = winner_side(m)
    if won == fav:
        return "favourite_won"
    if won == "draw":
        return "favourite_held"
    return "big_upset" if pct[fav] >= 65 else "upset"


# ---- How dramatic was it? ---------------------------------------------------------------------

def minute_number(text):
    found = re.match(r"\d+", text or "")
    return int(found.group(0)) if found else 0


def drama(m):
    """Objective measures of a match: goals, lead changes, comebacks, late goals, red cards."""
    goals = sorted(enumerate(m["goals"]), key=lambda ig: (minute_number(ig[1]["minute"]), ig[0]))
    score, last_leader, changes = {"home": 0, "away": 0}, 0, 0
    for _, g in goals:
        if g["side"] in score:
            score[g["side"]] += 1
        lead = (score["home"] > score["away"]) - (score["home"] < score["away"])
        if lead:  # a lead change is a different team in front than the last time anyone was, even via a level score
            if last_leader and lead != last_leader:
                changes += 1
            last_leader = lead
    won = winner_side(m)
    late = max((minute_number(g["minute"]) for g in m["goals"]), default=0)
    return {"total_goals": m["home_score"] + m["away_score"], "margin": abs(m["home_score"] - m["away_score"]),
            "lead_changes": changes, "comeback": won != "draw" and _was_behind(goals, won),
            "late_goal_minute": late if late >= 85 else None, "red_cards": len(m["reds"])}


def _was_behind(goals, side):
    score = {"home": 0, "away": 0}
    for _, g in goals:
        if g["side"] in score:
            score[g["side"]] += 1
        other = "away" if side == "home" else "home"
        if score[other] > score[side]:
            return True
    return False


def excitement(d, result_vs_expectation=None):
    """Picks the game of the night. Drama (goals, lead changes, a close finish, a late goal, a comeback, red cards)
    plus significance (an upset against the pre-match odds). The weights are a judgement call, tested below."""
    return (2 * d["total_goals"] + 3 * d["lead_changes"] + (2 if d["margin"] <= 1 else 0)
            + (2 if d["late_goal_minute"] and d["margin"] <= 1 else 0) + (3 if d["comeback"] else 0) + d["red_cards"]
            + {"big_upset": 3, "upset": 2}.get(result_vs_expectation, 0))


def label(m):
    return f"{m['home']['name']} {m['home_score']}-{m['away_score']} {m['away']['name']}"


# ---- The facts sheet -------------------------------------------------------------------------

def collect_odds(league, matches):
    """{match id: chances or None}. A match whose odds can't be read just has no expectation label."""
    out = {}
    for m in matches:
        pickcenter = safe(f"odds {m['id']}", espn.get_odds, m["id"], league)
        out[m["id"]] = chances(pickcenter)
    return out


def goal_timeline(m):
    """Every goal in order, with who scored, for which team and the score right after it. Own goals count for the
    team that benefits. Built by code so a model can never misread who scored when."""
    score, out = {"home": 0, "away": 0}, []
    for _, g in sorted(enumerate(m["goals"]), key=lambda ig: (minute_number(ig[1]["minute"]), ig[0])):
        if g["side"] not in score:
            continue
        score[g["side"]] += 1
        out.append({"minute": minute_number(g["minute"]), "scored_by": g["player"],
                    "for": m[g["side"]]["name"], "score_after": f"{score['home']}-{score['away']}",
                    **({"stoppage_time": True} if "+" in g["minute"] else {}),
                    **({"penalty": True} if g["penalty"] else {}), **({"own_goal": True} if g["own_goal"] else {})})
    return out


def winning_goal(m, timeline):
    """The goal that decided the match: the winner's goal number (loser's total + 1). None for a draw."""
    side = winner_side(m)
    if side == "draw":
        return None
    need = (m["away_score"] if side == "home" else m["home_score"]) + 1
    mine = [g for g in timeline if g["for"] == m[side]["name"]]
    g = mine[need - 1] if len(mine) >= need else None
    return {k: g[k] for k in ("minute", "scored_by", "for")} if g else None


def league_records(m, rows):
    """Each team's league-phase record, from the table now. perfect_start is only present when it is true."""
    by_id = {x["id"]: x for x in rows or []}
    out = {}
    for side in ("home", "away"):
        x = by_id.get(m[side]["id"])
        if x:
            out[m[side]["name"]] = {"position": x["rank"], "points": x["points"], "played": x["played"], "won": x["won"],
                                    "drawn": x["drawn"], "lost": x["lost"],
                                    **({"perfect_start": True} if x["played"] >= 2 and x["won"] == x["played"] else {})}
    return out


def matchday_facts(competition, matches, odds_by_id, table_rows=None):
    rows, scored = [], []
    for m in matches:
        pct, d = odds_by_id.get(m["id"]), drama(m)
        v = verdict(m, pct)
        timeline = goal_timeline(m)
        row = {"match": label(m), "total_goals": d["total_goals"], "lead_changes": d["lead_changes"], "goals": timeline}
        win = winning_goal(m, timeline)
        if win:
            row["winning_goal"] = win
        records = league_records(m, table_rows)
        if records:
            row["league_table_now"] = records
        if pct:
            row["pre_match_chances_pct"] = {m["home"]["name"]: pct["home"], "draw": pct["draw"], m["away"]["name"]: pct["away"]}
            row["result_vs_expectation"] = v
        if d["comeback"]:
            row["comeback"] = True
        if d["red_cards"]:
            row["red_cards"] = d["red_cards"]
        if m.get("recap"):
            row["recap"] = m["recap"]
        rows.append(row)
        scored.append((excitement(d, v), d["total_goals"], -len(scored), row))
    facts = {"kind": "overview", "competition": competition, "length": notes.TIERS["overview"][0], "matches": rows}
    known = [r for r in rows if "result_vs_expectation" in r]
    if known:
        count = lambda *v: sum(1 for r in known if r["result_vs_expectation"] in v)  # noqa: E731
        facts["expectations"] = "from pre-match betting odds"
        draws = sum(1 for m in matches if winner_side(m) == "draw")
        facts["tally"] = {"matches": len(rows), "decided_matches": len(rows) - draws, "draws": draws,
                          "clear_favourites": count("favourite_won", "favourite_held", "upset", "big_upset"),
                          "favourite_won": count("favourite_won"), "favourite_held": count("favourite_held"),
                          "upsets": count("upset", "big_upset"), "close_matches_no_clear_favourite": count("close_match")}
    else:
        facts["expectations"] = "unavailable"
    if rows:
        facts["game_of_the_night"] = max(scored)[3]["match"]
    return facts


# ---- Writing it ------------------------------------------------------------------------------

def plain_overview(f):
    """The safe fallback, built by code with no AI."""
    parts = []
    t = f.get("tally")
    if t and t["matches"]:
        parts.append(f"The favourites won {t['favourite_won']} of {t['matches']} matches.")
        ups = [r["match"] for r in f["matches"] if r.get("result_vs_expectation") in ("upset", "big_upset")]
        if ups:
            parts.append("Upsets: " + "; ".join(ups) + ".")
    if f.get("game_of_the_night"):
        g = next(r for r in f["matches"] if r["match"] == f["game_of_the_night"])
        parts.append(f"Game of the night: {g['match']}, with {g['total_goals']} goals.")
    return " ".join(parts)


def _words(text):
    return re.findall(r"[a-z0-9']+", text.lower())


def check_overview(note, f):
    """Everything the match-note checker looks for, plus: no 'upset' language without an upset label,
    no favourite language when expectations are unavailable, and no copied run of ESPN report text."""
    problems = notes.check_note(note, f)
    labels = {r.get("result_vs_expectation") for r in f["matches"]}
    if UPSET_WORDS.search(note) and not labels & {"upset", "big_upset"}:
        problems.append(f'"{UPSET_WORDS.search(note).group(0)}" is not supported: no result was labelled an upset')
    if f.get("expectations") == "unavailable" and FAVOURITE_WORDS.search(note):
        problems.append("mentions favourites or expectations, but no odds were available")
    real_winners = {r["winning_goal"]["minute"] for r in f["matches"] if r.get("winning_goal")}
    for sentence in re.split(r"(?<=[.!?])\s+", note):
        if DECIDING.search(sentence):
            for minute in MINUTE.findall(sentence):
                if int(minute) not in real_winners:
                    problems.append(f"calls a goal in the {minute}th minute decisive, but no winning goal was scored then")
    note_words = _words(note)
    for r in f["matches"]:
        for source in (r.get("recap") or {}).values():
            theirs = _words(source)
            grams = {tuple(theirs[i:i + 6]) for i in range(len(theirs) - 5)}
            if any(tuple(note_words[i:i + 6]) in grams for i in range(len(note_words) - 5)):
                problems.append("copies a run of six or more words from an ESPN report")
    return sorted(set(problems))


def write_overview(client, f):
    """{"note", "source": "claude" | "plain", "problems"} and usage. One retry that names the problems; then the
    plain overview. Nothing unchecked is ever returned as Claude's."""
    import json
    total, problems, sent, rejected = {"input": 0, "output": 0}, [], f, []
    for attempt in (1, 2, 3):
        extra = "" if attempt == 1 else ("Your earlier overview broke these rules: " + "; ".join(problems) +
                                         ". Rewrite it so that it fixes them, using only the facts.\n")
        obj, usage = notes.call_json(client, SYSTEM, SCHEMA, extra + "Facts:\n" + json.dumps(sent, ensure_ascii=False, indent=1),
                                     model=settings.OVERVIEW_MODEL)
        total = {k: total[k] + usage[k] for k in total}
        note = (obj or {}).get("overview", "").strip() if isinstance(obj, dict) else ""
        problems = check_overview(note, f) if note else ["no overview returned"]
        if note and not problems:
            return {"note": note, "source": "claude", "problems": [], "rejected": rejected}, total
        rejected.append({"attempt": attempt, "note": note, "problems": problems})
    return {"note": plain_overview(f), "source": "plain", "problems": problems, "rejected": rejected}, total
