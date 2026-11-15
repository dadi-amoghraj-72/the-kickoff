"""Young Guns: rookies and under-21s who did something notable (D, 2026-11-05: all sports, rookies in the NBA, NFL and MLB, under 21 everywhere; women's sports included;
only on a day someone did something notable; a watchlist that keeps following a young player once he has been notable three times).

Code finds them: each sport hands over the players of its finished games with the facts of their performance; this module looks up who is young (ESPN, once per player,
remembered), checks the performance against its threshold (lower for a player on the watchlist), ranks and caps them. The line is written by code, one form for
everyone: 'Name (team, rookie, age): figures against opponent' (D, 2026-11-15). `why` explains each pick for the dev log.

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


SPORT_LABEL = {"nba": "NBA", "nfl": "NFL", "mlb": "MLB", "soccer": "Football", "tennis": "Tennis", "f1": "F1"}


def html(lines, sports=None):
    """Gold figures like the other standouts lists, each sport under its own small label (sports: the sport of each line, in the same order; D, 2026-11-15);
    '' when nobody was notable (the section is then simply not there)."""
    if not lines:
        return ""
    sports = sports or [None] * len(lines)
    out = ""
    for sport in dict.fromkeys(sports):
        label = f'<p class="subhead">{r.esc(SPORT_LABEL.get(sport, (sport or "").title()))}</p>' if sport else ""
        out += label + '<ul class="standouts yg">' + "".join(f"<li>{highlight(r.esc(t))}</li>" for t, sp in zip(lines, sports) if sp == sport) + "</ul>"
    return out


def grouped(picked):
    """The picks with each sport together (sports in the order of their best player, players keep their order inside a sport)."""
    order = list(dict.fromkeys(c["sport"] for c in picked))
    return sorted(picked, key=lambda c: order.index(c["sport"]))


NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "once": 1, "twice": 2}
STAT = {"goal": "goal", "goals": "goal", "assist": "assist", "assists": "assist", "ast": "assist", "point": "pts", "points": "pts", "pts": "pts", "rebound": "reb", "rebounds": "reb",
        "reb": "reb", "block": "blk", "blocks": "blk", "blk": "blk", "steal": "stl", "steals": "stl", "stl": "stl", "save": "save", "saves": "save"}
_NUM = r"(\d+|" + "|".join(k for k in NUMBER_WORDS if k not in ("once", "twice")) + r")"
HIGHLIGHT = re.compile(rf"\b(?:{_NUM}\s+(?:{'|'.join(STAT)})|(?:scored|netted|found the net|struck|converted)\s+(?:once|twice)|(?:an?\s+)?(?:hat-trick|hat trick|brace))\b", re.I)


def highlight(text):
    """The figures that are the news in gold, the whole phrase: '1 goal', '2 assists', '22 pts', 'scored twice', 'a hat-trick'. Scores (9-1) and ages are never part of a phrase (D, 2026-11-05)."""
    return HIGHLIGHT.sub(lambda m: f'<span class="n">{m.group(0)}</span>', text)


def build(found, state, day, client=None):
    """Everything for the morning: {"html", "state", "lines", "why", "usage"}. found: candidates from every sport (already checked for youth and notability).
    The watchlist counts today's picks. Every line is written by code in one form (D, 2026-11-15: Claude's free wording read differently on every line); `client` is not used."""
    picked = grouped(select(found))
    new_state = update_watch(state, found, day)
    lines = [plain_line(c) for c in picked]
    return {"html": html(lines, [c["sport"] for c in picked]), "state": new_state, "lines": lines, "plain": lines, "why": [why(c, watched(state, c["sport"], c["id"])) for c in picked],
            "usage": {"input": 0, "output": 0}}
