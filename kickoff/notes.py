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
         "derby": ("three to four sentences, at most 80 words", 95),
         "arsenal": ("four to six sentences, at most 110 words; cover the result, the scorers and assists, the table or recent form", 125),
         "women": ("two sentences, at most 45 words", 55),
         "overview": ("four to six sentences, at most 110 words", 125)}

SYSTEM = """You write the match notes for The Kickoff, a personal daily sports digest read by one football fan in Singapore.

Voice: plain, warm and specific, in your own words. British spelling. No emojis, no exclamation marks, no clichés
such as "clinical", "masterclass" or "thriller".

Hard rules:
- Use ONLY the facts supplied for each match. Add nothing from memory: no form, history, records, injuries, opinions,
  predictions or comparisons. Do not guess at how a goal was scored.
- Use club and player names exactly as they appear in the facts. Every number you write must come from the facts.
- Where a goal has an "assist", you may credit it. If the facts include "form", you may describe recent form and
  the unbeaten run exactly as given there.
- If the facts are thin, write less. A short accurate note beats a long invented one.
- Each match has a "length" instruction. Follow it strictly: a short note is ONE sentence.
- Write minutes in plain words ("the 38th minute", "stoppage time"). Never copy symbols such as ' or +.
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
                      r"(?:up|down) to|(?:up|down) from|unchanged|still|again)\b", re.I)

# Hype the voice rules ban, and the word limit for each length instruction.
HYPE = re.compile(r"thrash|hammer|demolish|humiliat|masterclass|clinical|thriller|stunning|sensational|annihilat", re.I)
LIMITS = {desc: limit for desc, limit in TIERS.values()}

# Words a sentence may start with. A first word outside this list, outside the facts and without an ordinary
# word ending is treated as a possible invented name.
STARTERS = set("""the a an this that these those it its they their there here in on at by for from with without after before
during while when where as but and or so yet if though although despite both each every all most some many few several one
two three four five six seven eight nine ten eleven twelve first second third last next another other others nobody
everyone someone nothing everything something only just even still also then now today tonight yesterday overall meanwhile
elsewhere otherwise instead however nevertheless together between among across against behind beyond within under over
through throughout into onto out up down off about around along early late earlier later finally ultimately perhaps maybe
indeed clearly simply more less much no not neither either whatever whoever what which who whose how why he she we you i
his her our your half full goal goals win wins defeat result results victory draw draws""".split())
ORDINARY_ENDINGS = ("ing", "ed", "ly", "ness", "tion", "sion", "ment", "ous", "ful", "ity", "ive", "able")

# Well-known club nicknames: not invented names, so they are allowed even when the facts say "Tottenham Hotspur".
NICKNAMES = {"spurs", "gunners", "citizens", "blues", "reds", "toffees", "magpies", "hammers", "villans", "seagulls",
             "cherries", "eagles", "foxes", "bees", "wolves", "saints", "blades", "canaries", "lions", "red", "devils"}

ALLOWED_WORDS = NICKNAMES | {"premier", "league", "champions", "europa", "conference", "cup", "monday", "tuesday", "wednesday",
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
        "goals": [dict({"minute": g["minute"], "scorer": g["player"], "for": names.get(g["side"], "?"), "type": kind(g)},
                       **({"assist": g["assist"]} if g.get("assist") else {})) for g in m["goals"]],
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
        tag = {"penalty": " (pen)", "own goal": " (OG)"}.get(g["type"], "")
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
        first = re.sub(r"['’]s$", "", words[0]) if words else ""
        if (first.isalpha() and len(first) > 2 and first.lower() not in vocab and first.lower() not in STARTERS
                and first.lower() not in ALLOWED_WORDS and not first.lower().endswith(ORDINARY_ENDINGS)):
            problems.append(f"name {first} is not in the facts")
        for w in words[1:]:  # later capitalised words are names; the first word was handled above
            base = re.sub(r"['’]s$", "", w)  # "Villa's" is checked as "Villa"
            if base[0].isupper() and base.lower() not in vocab and base.lower() not in ALLOWED_WORDS \
                    and not all(p.lower() in vocab for p in base.split("-")):
                problems.append(f"name {base} is not in the facts")
    limit = LIMITS.get(f.get("length"))
    if limit and len(note.split()) > limit:
        problems.append(f"{len(note.split())} words, over the limit of {limit}")
    if re.search(r"\d['’]|\d\+\d", note):
        problems.append("minute symbols such as 36' or 90+4: write 'the 36th minute' or 'stoppage time'")
    if HYPE.search(note):
        problems.append(f'hype word "{HYPE.search(note).group(0)}"')
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


def call_json(client, system, schema, content):
    """One Claude call that must return JSON matching the schema. Returns (parsed object or None, usage).
    Any failure (API error, refusal, cut-off, unreadable reply) returns None and a warning, never an exception."""
    import anthropic
    body = {"model": settings.CLAUDE_MODEL, "max_tokens": 16000, "system": system,
            "messages": [{"role": "user", "content": content}],
            "output_config": {"effort": settings.CLAUDE_EFFORT, "format": {"type": "json_schema", "schema": schema}}}
    try:
        try:
            resp = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **body)
        except anthropic.BadRequestError as e:
            print(f"WARN  fallbacks option rejected, retrying without it: {e.message[:120]}", file=sys.stderr)
            resp = client.messages.create(**body)
    except Exception as e:
        print(f"WARN  Claude call failed: {type(e).__name__}", file=sys.stderr)
        return None, {"input": 0, "output": 0}
    usage = {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens}
    if resp.stop_reason != "end_turn":
        print(f"WARN  Claude stopped early ({resp.stop_reason}); using the fallback", file=sys.stderr)
        return None, usage
    try:
        return json.loads(next(b.text for b in resp.content if b.type == "text")), usage
    except Exception:
        print("WARN  Claude's reply could not be read; using the fallback", file=sys.stderr)
        return None, usage


def _ask(client, facts_list, extra=""):
    """Match notes: ({id: note}, usage). Any failure gives an empty dict."""
    obj, usage = call_json(client, SYSTEM, SCHEMA,
                           extra + "Matches:\n" + json.dumps(facts_list, ensure_ascii=False, indent=1))
    try:
        return {n["id"]: n["note"] for n in obj["notes"]}, usage
    except Exception:
        return {}, usage


def write_notes(client, facts_list):
    """{match id: {"note", "source": "claude" | "plain", "problems"}} plus total usage.
    Nothing unchecked is ever returned as a Claude note."""
    result, total = {}, {"input": 0, "output": 0}
    pending, problems_by_id = list(facts_list), {}
    for attempt in (1, 2):
        if not pending:
            break
        if attempt == 1:
            sent, extra = pending, ""
        else:  # the retry names the exact problems; the check below still uses the original facts
            sent = [{**f, "problems_with_your_last_note": problems_by_id[f["id"]]} for f in pending]
            extra = ("Your earlier note for each match below broke a rule. Rewrite it so that it fixes the listed problems, "
                     "using only the facts.\n")
        notes, usage = _ask(client, sent, extra)
        total = {k: total[k] + usage[k] for k in total}
        failed = []
        for f in pending:
            note = notes.get(f["id"])
            problems = check_note(note, f) if note else ["no note returned"]
            if note and not problems:
                result[f["id"]] = {"note": note.strip(), "source": "claude", "problems": []}
            else:
                result[f["id"]] = {"note": plain_note(f), "source": "plain", "problems": problems}
                problems_by_id[f["id"]] = problems
                failed.append(f)
        pending = failed if attempt == 1 else []
    return result, total
