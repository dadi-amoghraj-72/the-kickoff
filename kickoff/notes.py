"""Match notes: code gathers the facts, Claude phrases them, code checks the result.

Claude only ever sees a facts sheet and is told to use nothing else. Every note is then checked: a number
or a name that isn't in the facts means one retry, and then a plain scoreline written by code instead.
"""
import json
import re
import sys

from kickoff import settings
from kickoff.clubs import ARSENAL_ID, CLUBS, is_big6, is_listed

BIG_SIX_ORDER = ["382", "360", "364", "363", "367"]  # Arsenal has its own section
TIERS = {"short": ("one sentence, at most 25 words", 30), "standard": ("two to three sentences, at most 55 words", 65),
         "derby": ("three to four sentences, at most 80 words", 95)}

SYSTEM = """You write the match notes for The Kickoff, a personal daily sports digest read by one football fan in Singapore.

Voice: plain, warm and specific, in your own words. British spelling. No emojis, no exclamation marks, no clichés
such as "clinical", "masterclass" or "thriller".

Hard rules:
- Use ONLY the facts supplied for each match. Add nothing from memory: no form, history, records, injuries, opinions,
  predictions or comparisons. Do not guess at how a goal was scored.
- Use club and player names exactly as they appear in the facts. Every number you write must come from the facts.
- If the facts are thin, write less. A short accurate note beats a long invented one.
- Each match has a "length" instruction. Follow it.
- Mention a red card whenever there is one. State a team's table position and points as they are now. Say a team
  moved, climbed, dropped or stayed only if the facts include "position_before" for that team.

Return one note for every match id supplied."""

SCHEMA = {"type": "object", "properties": {"notes": {"type": "array", "items": {
    "type": "object", "properties": {"id": {"type": "string"}, "note": {"type": "string"}},
    "required": ["id", "note"], "additionalProperties": False}}},
    "required": ["notes"], "additionalProperties": False}

# Words that claim a table movement or continuity. They need a "position_before" in the facts to be true.
MOVEMENT = re.compile(r"\b(stay(?:s|ed)?|remain(?:s|ed)?|climb(?:s|ed|ing)?|ris(?:e|es|en|ing)|rose|jump(?:s|ed)?|"
                      r"drop(?:s|ped)?|fall(?:s|en)?|fell|slip(?:s|ped)?|leapfrog\w*|overtak\w*|overtook|"
                      r"(?:up|down) to|(?:up|down) from|unchanged)\b", re.I)

ALLOWED_WORDS = {"premier", "league", "champions", "europa", "conference", "cup", "monday", "tuesday", "wednesday",
                 "thursday", "friday", "saturday", "sunday", "british", "english", "spanish", "german", "french",
                 "italian", "turkish", "uefa", "fa", "var"}


# ---- Choosing the matches ------------------------------------------------------------------

def select(league, matches, premier_league="eng.1"):
    """[(match, tier)] in display order. Arsenal's match is left out: it belongs to the Arsenal section.
    Premier League: every game, big six first. Other leagues: only games involving a listed club."""
    out = []
    for m in matches:
        ids = {m["home"]["id"], m["away"]["id"]}
        if ARSENAL_ID in ids:
            continue
        both_listed = all(is_listed(i) for i in ids)
        if league == premier_league:
            out.append((m, "derby" if all(is_big6(i) for i in ids) else "standard"))
        elif any(is_listed(i) for i in ids):
            out.append((m, "derby" if both_listed else "short"))

    def order(item):
        m, _ = item
        ranks = [BIG_SIX_ORDER.index(i) for i in (m["home"]["id"], m["away"]["id"]) if i in BIG_SIX_ORDER]
        return (min(ranks) if ranks else 99, m["kickoff"])
    return sorted(out, key=order)


# ---- The facts sheet -----------------------------------------------------------------------

def match_facts(m, tier, rows=None, previous=None, competition="Premier League"):
    """Everything Claude may use for one match. rows: the league table now. previous: the last published
    snapshot, {team_id: rank}, used only to say whether a team moved."""
    names = {"home": m["home"]["name"], "away": m["away"]["name"]}
    kind = lambda g: "own goal" if g["own_goal"] else ("penalty" if g["penalty"] else "goal")  # noqa: E731
    facts = {
        "id": m["id"], "competition": competition, "length": TIERS[tier][0],
        "home": names["home"], "away": names["away"], "final_score": f"{m['home_score']}-{m['away_score']}",
        "goals": [{"minute": g["minute"], "scorer": g["player"], "for": names.get(g["side"], "?"), "type": kind(g)}
                  for g in m["goals"]],
        "red_cards": [{"minute": r["minute"], "player": r["player"], "team": names.get(r["side"], "?")} for r in m["reds"]],
    }
    if rows:
        by_id = {x["id"]: x for x in rows}
        table = {}
        for side in ("home", "away"):
            row = by_id.get(m[side]["id"])
            if row:
                entry = {"position_now": row["rank"], "points": row["points"], "played": row["played"]}
                if previous and m[side]["id"] in previous and previous[m[side]["id"]] != row["rank"]:
                    entry["position_before"] = previous[m[side]["id"]]
                table[names[side]] = entry
        if table:
            facts["table"] = table
    return facts


def plain_note(f):
    """The safe fallback: a scoreline and scorers, built by code with no AI."""
    line = f"{f['home']} {f['final_score']} {f['away']}."
    parts = []
    for g in f["goals"]:
        tag = {"penalty": " (pen)", "own goal": " (og)"}.get(g["type"], "")
        parts.append(f"{g['scorer']} {g['minute']}{tag}")
    if parts:
        line += " Goals: " + ", ".join(parts) + "."
    if f["red_cards"]:
        line += " Red card: " + ", ".join(f"{r['player']} {r['minute']}" for r in f["red_cards"]) + "."
    return line


# ---- Checking a note against its facts -------------------------------------------------------

def _vocab(value, words=None):
    words = words if words is not None else set()
    if isinstance(value, dict):
        for k, v in value.items():
            _vocab(v, words)
            _vocab(k, words)
    elif isinstance(value, list):
        for v in value:
            _vocab(v, words)
    else:
        text = str(value)
        for token in re.findall(r"[\w'’-]+", text):
            words.add(token.lower())
            words.update(part.lower() for part in token.split("-"))
        words.update(re.findall(r"\d+", text))  # "2-0" gives 2 and 0, "90'+11'" gives 90 and 11
    return words


def check_note(note, f):
    """Problems found in a note: any number or capitalised name that isn't in the facts. Empty list = OK."""
    vocab = _vocab(f)
    problems = []
    for n in re.findall(r"\d+", note):
        if n not in vocab and n.lstrip("0") not in vocab:
            problems.append(f"number {n} is not in the facts")
    for sentence in re.split(r"(?<=[.!?])\s+", note):
        words = re.findall(r"[\w'’-]+", sentence)
        for w in words[1:]:  # the first word of a sentence is capitalised anyway
            base = re.sub(r"['’]s$", "", w)  # "Villa's" is checked as "Villa"
            if base[0].isupper() and base.lower() not in vocab and base.lower() not in ALLOWED_WORDS \
                    and not all(p.lower() in vocab for p in base.split("-")):
                problems.append(f"name {base} is not in the facts")
    moved = any("position_before" in t for t in (f.get("table") or {}).values())
    for m in MOVEMENT.finditer(note):
        if not moved:
            problems.append(f'"{m.group(0)}" implies a table move, but no previous position was given')
    return sorted(set(problems))


# ---- Asking Claude ---------------------------------------------------------------------------

def cost(usage, model=None):
    price = settings.PRICES.get(model or settings.CLAUDE_MODEL)
    if not price or not usage:
        return 0.0
    return (usage["input"] * price[0] + usage["output"] * price[1]) / 1_000_000


def _ask(client, facts_list, extra=""):
    """One call. Returns ({id: note}, usage). Any failure returns ({}, usage so far) and a warning."""
    import anthropic
    body = {"model": settings.CLAUDE_MODEL, "max_tokens": 16000, "system": SYSTEM,
            "messages": [{"role": "user", "content": extra + "Matches:\n" + json.dumps(facts_list, ensure_ascii=False, indent=1)}],
            "output_config": {"effort": settings.CLAUDE_EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}}}
    try:
        try:
            resp = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **body)
        except anthropic.BadRequestError as e:
            print(f"WARN  fallbacks option rejected, retrying without it: {e.message[:120]}", file=sys.stderr)
            resp = client.messages.create(**body)
    except Exception as e:
        print(f"WARN  Claude call failed: {type(e).__name__}", file=sys.stderr)
        return {}, {"input": 0, "output": 0}
    usage = {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens}
    if resp.stop_reason != "end_turn":
        print(f"WARN  Claude stopped early ({resp.stop_reason}); using plain notes", file=sys.stderr)
        return {}, usage
    try:
        text = next(b.text for b in resp.content if b.type == "text")
        return {n["id"]: n["note"] for n in json.loads(text)["notes"]}, usage
    except Exception:
        print("WARN  Claude's reply could not be read; using plain notes", file=sys.stderr)
        return {}, usage


def write_notes(client, facts_list):
    """{match id: {"note", "source": "claude" | "plain", "problems"}} plus total usage.
    Nothing unchecked is ever returned as a Claude note."""
    result, total = {}, {"input": 0, "output": 0}
    pending = list(facts_list)
    for attempt in (1, 2):
        if not pending:
            break
        notes, usage = _ask(client, pending, "" if attempt == 1 else
                            "Some earlier notes added details that are not in the facts. Rewrite these using only the facts.\n")
        total = {k: total[k] + usage[k] for k in total}
        failed = []
        for f in pending:
            note = notes.get(f["id"])
            problems = check_note(note, f) if note else ["no note returned"]
            if note and not problems:
                result[f["id"]] = {"note": note.strip(), "source": "claude", "problems": []}
            else:
                result[f["id"]] = {"note": plain_note(f), "source": "plain", "problems": problems}
                failed.append(f)
        pending = failed if attempt == 1 else []
    return result, total
