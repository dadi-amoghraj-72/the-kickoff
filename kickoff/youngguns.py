"""Young Guns: rookies and under-21s who did something notable (D, 2026-11-05: all sports, rookies in the NBA, NFL and MLB, under 21 everywhere; women's sports included;
only on a day someone did something notable; a watchlist that keeps following a young player once he has been notable three times).

Code finds them: each sport hands over the players of its finished games with the facts of their performance; this module looks up who is young (ESPN, once per player,
remembered), checks the performance against its threshold (lower for a player on the watchlist), ranks and caps them. The line is written by code; Claude can also
phrase it (`phrase`), checked like every other note: each name and number must come from the facts. `why` explains each pick for the dev log.

A candidate: {"sport", "id", "name", "team", "age", "rookie", "facts" (text), "score", "day"}."""
import re
from datetime import date

from kickoff import render as r
from kickoff.sources import espn_people

AGE_LIMIT = 21             # under 21 on the day
WATCH_AFTER = 3            # notable days before a young player joins the watchlist
WATCH_FACTOR = 0.7         # a watched player needs 70% of the usual threshold
CAP = 5
ROOKIE_SPORTS = {"nba", "nfl", "mlb"}       # their leagues have a rookie year (ESPN: 0 years of experience)


def age_on(dob, day):
    """Whole years on `day` (a date) for a birth date 'YYYY-MM-DD'; None when unreadable."""
    try:
        b = date.fromisoformat(dob[:10])
    except (ValueError, TypeError):
        return None
    return day.year - b.year - ((day.month, day.day) < (b.month, b.day))


def lookup(sport, athlete_id, day, ages, get=None):
    """(age, rookie) for an athlete, or (None, False) when unknown. ages: the state's remembered lookups {"sport:id": {"dob", "years"}}; a new one is added to it."""
    key = f"{sport}:{athlete_id}"
    info = ages.get(key)
    if info is None:
        try:
            got = (get or espn_people.athlete)(sport, athlete_id)
        except Exception:                                    # a failed lookup leaves that one player out, never the section
            got = None
        if not got:
            return None, False
        info = ages[key] = {"dob": got.get("dob"), "years": got.get("years"), "age": got.get("age")}
    age = age_on(info["dob"], day) if info.get("dob") else info.get("age")
    rookie = sport in ROOKIE_SPORTS and info.get("years") == 0
    return age, rookie


def is_young(age, rookie):
    return rookie or (age is not None and age < AGE_LIMIT)


def watch_key(c):
    return f"{c['sport']}:{c['id']}"


def make(sport, pid, name, team, facts, score, age, rookie, day):
    return {"sport": sport, "id": str(pid), "name": name, "team": team, "age": age, "rookie": rookie, "facts": facts, "score": round(score, 1), "day": day.isoformat()}


def update_watch(state, found, day):
    """Count each young player's notable day (once per day); at WATCH_AFTER days he is on the watchlist for good. Returns the new state (the old one is not changed)."""
    watch = {k: dict(v) for k, v in (state.get("watch") or {}).items()}
    for c in found:
        w = watch.setdefault(watch_key(c), {"name": c["name"], "sport": c["sport"], "team": c["team"], "days": []})
        w["team"] = c["team"]
        if c["day"] not in w["days"]:
            w["days"].append(c["day"])
        w["days"] = w["days"][-10:]
    return {**state, "watch": watch}


def watched(state, sport, pid):
    w = (state.get("watch") or {}).get(f"{sport}:{pid}")
    return bool(w and len(w["days"]) >= WATCH_AFTER)


def select(found, cap=CAP):
    """Best first, at most `cap`, one line per player."""
    seen, out = set(), []
    for c in sorted(found, key=lambda c: (-c["score"], c["name"])):
        if watch_key(c) in seen:
            continue
        seen.add(watch_key(c))
        out.append(c)
    return out[:cap]


def tag(c):
    return ("rookie" if c["rookie"] else "") + (", " if c["rookie"] and c["age"] is not None else "") + (f"{c['age']}" if c["age"] is not None else "")


def plain_line(c, watched_flag=False):
    return f"{c['name']} ({c['team']}, {tag(c)}): {c['facts']}"


def why(c, watched_flag):
    return f"{c['sport']} {'rookie' if c['rookie'] else 'under 21'}, score {c['score']}" + (", watchlist" if watched_flag else "")


def html(lines):
    """Gold figures like the other standouts lists; '' when nobody was notable (the section is then simply not there)."""
    if not lines:
        return ""
    gold = lambda t: re.sub(r"(?<![\w-])(\d+)(?=\s)", r'<span class="n">\1</span>', r.esc(t))  # noqa: E731
    return '<ul class="standouts">' + "".join(f"<li>{gold(t)}</li>" for t in lines) + "</ul>"


# ---- Claude phrasing (optional) -----------------------------------------------------------------

SYSTEM = ("You write one short line for each young player in a sports digest (a rookie or under 21). Use ONLY the facts given for that player; add nothing from memory. "
          "Plain, warm, specific, no hype, at most 25 words, British spelling, no emojis. Keep the player's name, team code and age as given.")
SCHEMA = {"type": "object", "properties": {"lines": {"type": "array", "items": {"type": "object", "properties": {"n": {"type": "integer"}, "text": {"type": "string"}},
          "required": ["n", "text"], "additionalProperties": False}}}, "required": ["lines"], "additionalProperties": False}


def supported(text, c):
    """Every number and every capitalised word in a written line must be in that player's facts, name, team or age."""
    hay = f"{c['name']} {c['team']} {c['age'] or ''} {c['facts']} rookie".lower()
    words = re.findall(r"\b[A-Z][\w'’.-]{2,}\b", re.sub(r"^\W*\w+", "", text))
    return all(w.lower().strip(".'’-") in hay for w in words) and all(n in hay for n in re.findall(r"\d+", text)) and len(text.split()) <= 30


def phrase(client, found, call_json=None):
    """({player key: written line}, usage). Lines that fail the check are left out (the caller falls back to the plain line). Never raises."""
    if not client or not found:
        return {}, {"input": 0, "output": 0}
    from kickoff import notes
    listing = "\n".join(f"{i + 1}. {c['name']} ({c['team']}, {tag(c)}): {c['facts']}" for i, c in enumerate(found))
    try:
        got, usage = (call_json or notes.call_json)(client, SYSTEM, SCHEMA, f"Players:\n{listing}")
    except Exception:
        return {}, {"input": 0, "output": 0}
    out = {}
    for x in (got or {}).get("lines", []):
        if 1 <= x["n"] <= len(found) and supported(x["text"], found[x["n"] - 1]):
            out[watch_key(found[x["n"] - 1])] = x["text"].strip()
    return out, usage


def build(found, state, day, client=None):
    """Everything for the morning: {"html", "state", "lines", "why", "cost_usage"}. found: candidates from every sport (already checked for youth and notability).
    The watchlist counts today's picks; Claude phrases the lines when a client is given (the plain line is the fallback for any line that fails the check)."""
    picked = select(found)
    new_state = update_watch(state, found, day)
    written, usage = phrase(client, picked)
    lines = [written.get(watch_key(c)) or plain_line(c) for c in picked]
    return {"html": html(lines), "state": new_state, "lines": lines, "plain": [plain_line(c) for c in picked], "why": [why(c, watched(state, c["sport"], c["id"])) for c in picked], "usage": usage}
