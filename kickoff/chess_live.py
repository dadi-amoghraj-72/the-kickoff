"""Chess results from Lichess's free broadcast API (official, no key): the elite events (Lichess tier 5: the Candidates, Tata Steel, Norway Chess, the World Championship match ...) and
the Indian stars in the tier 4 and 5 events (checkpoint 12, second pass, 2026-11-05).

  - a round that finished in the last 36 hours in a tier 5 event: the decisive games (the three with the highest average rating) and how many were drawn;
  - the last round of a round-robin of twelve players or fewer: the winner and score, summed from every round's games;
  - a win by a listed Indian player in a tier 4 or 5 event (the spotlight rule), at most two lines.
Only the games' own tags are used (White, Black, Result, ratings), so every line is exact. Without Lichess nothing is shown. Built on the real API's shapes; no tier 5 event was running when it was built,
so the tier 5 paths are tested on made-up games with the real layout."""
import re
from datetime import timedelta, timezone, datetime

RECENT = timedelta(hours=36)
ELITE_TIER = 5
STAR_TIER = 4
MAX_ROUND_ROBIN = 12
INDIAN_STARS = re.compile(r"\b(gukesh|praggnanandhaa|pragg|arjun erigaisi|erigaisi|vidit|koneru|humpy|divya deshmukh|vaishali|harikrishna|nihal sarin|aravindh chithambaram|harika)\b", re.I)
POINTS = {"1-0": (1, 0), "0-1": (0, 1), "1/2-1/2": (0.5, 0.5)}


def parse_pgn(text):
    """[{"white", "black", "result", "elo": (white, black)}] for every game in a PGN with a known result; unfinished games ('*') are left out."""
    games = []
    for chunk in re.split(r"\n\s*\n(?=\[Event )", text.strip()):
        tags = dict(re.findall(r'\[(\w+) "([^"]*)"\]', chunk))
        if tags.get("Result") in POINTS and tags.get("White") and tags.get("Black"):
            elo = lambda k: int(tags[k]) if tags.get(k, "").isdigit() else 0  # noqa: E731
            games.append({"white": tags["White"], "black": tags["Black"], "result": tags["Result"], "elo": (elo("WhiteElo"), elo("BlackElo"))})
    return games


def surname(name):
    """'Gukesh, D' or 'D Gukesh' or 'Praggnanandhaa R' -> the part people say: the first word of a 'Surname, Initial' name, else the longest word."""
    if "," in name:
        return name.split(",")[0].strip()
    words = [w for w in name.split() if len(w) > 2 or not w.isupper()]
    return max(words or name.split(), key=len)


def decisive(games, limit=3):
    """The decisive games with the highest average rating, as 'Gukesh beat Firouzja'."""
    wins = [g for g in games if g["result"] != "1/2-1/2"]
    wins.sort(key=lambda g: -(g["elo"][0] + g["elo"][1]))
    out = []
    for g in wins[:limit]:
        w, l = (g["white"], g["black"]) if g["result"] == "1-0" else (g["black"], g["white"])
        out.append(f"{surname(w)} beat {surname(l)}")
    return out


def standings(rounds_games):
    """{player: points} summed over every round's games."""
    table = {}
    for games in rounds_games:
        for g in games:
            a, b = POINTS[g["result"]]
            table[g["white"]] = table.get(g["white"], 0) + a
            table[g["black"]] = table.get(g["black"], 0) + b
    return table


def _num(x):
    return f"{x:g}"


def _utc(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def run(source, now):
    """[(line, unique id, link)] from Lichess. source.top() -> {"active": [...], "past": [...]} as the API gives it; source.round_pgn(round id) -> text; source.tour(tour id) -> {"rounds": [...]}.
    Never raises: a failing call skips that event."""
    try:
        top = source.top()
    except Exception:
        return []
    items = list(top.get("active") or []) + list((top.get("past") or {}).get("currentPageResults") or top.get("past") or [])
    if isinstance(top.get("past"), list):
        items = list(top.get("active") or []) + list(top["past"])
    out, stars = [], 0
    for it in items:
        tour, rnd = it.get("tour") or {}, it.get("round") or {}
        tier = tour.get("tier") or 0
        done = rnd.get("finishedAt")
        if tier < STAR_TIER or not rnd.get("finished") or not done or not (timedelta(0) <= now - _utc(done) <= RECENT):
            continue
        try:
            games = parse_pgn(source.round_pgn(rnd["id"]))
        except Exception:
            continue
        link = rnd.get("url") or f"https://lichess.org/broadcast/{tour.get('slug', '')}"
        name = re.sub(r"\s*\|.*$", "", tour.get("name", "")).strip()
        if tier >= ELITE_TIER and games:
            wins = decisive(games)
            draws = sum(1 for g in games if g["result"] == "1/2-1/2")
            text = f"{name}, {rnd.get('name', 'round')}: " + (", ".join(wins) if wins else "all games drawn") + (f"; {draws} drawn" if wins and draws else "")
            out.append((text, f"chess:{rnd['id']}", link))
            last = (tour.get("dates") or [0, 0])[-1]
            if last and done >= last - 86400000:
                try:
                    rounds = [x for x in source.tour(tour["id"]).get("rounds", []) if x.get("finished")]
                    table = standings([parse_pgn(source.round_pgn(x["id"])) for x in rounds])
                except Exception:
                    table = {}
                if table and len(table) <= MAX_ROUND_ROBIN:
                    best = max(table.values())
                    leaders = sorted(p for p, s in table.items() if s == best)
                    out.append((f"{name}: " + (f"{surname(leaders[0])} wins on {_num(best)} point{'s' if best != 1 else ''}" if len(leaders) == 1 else f"{' and '.join(surname(p) for p in leaders)} share first on {_num(best)} point{'s' if best != 1 else ''}"),
                                f"chess:{tour['id']}:final", link))
        if stars < 2:
            for g in games:
                if g["result"] == "1/2-1/2":
                    continue
                w, l = (g["white"], g["black"]) if g["result"] == "1-0" else (g["black"], g["white"])
                if INDIAN_STARS.search(w) and not (tier >= ELITE_TIER and any(surname(w) in x for x in decisive(games))):
                    out.append((f"{surname(w)} beat {surname(l)} in {name}, {rnd.get('name', 'round')}", f"chess:{rnd['id']}:{surname(w)}", link))
                    stars += 1
                    if stars >= 2:
                        break
    return out
