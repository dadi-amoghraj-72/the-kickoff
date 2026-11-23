"""Chess results from Lichess's free broadcast API (official, no key): the elite events (Lichess tier 5: the Candidates, Tata Steel, Norway Chess, the World Championship match ...) and
the Indian stars in the tier 4 and 5 events (checkpoint 12, second pass, 2026-11-05).

  - a round that finished in the last three days in a tier 5 event: the decisive games (the three with the highest average rating) and how many were drawn;
  - the last round of a round-robin of twelve players or fewer: the winner and score, summed from every round's games;
  - a win by a listed Indian player in a tier 4 or 5 event (the spotlight rule), at most two lines.
Only the games' own tags are used (White, Black, Result, ratings), so every line is exact. Without Lichess nothing is shown. Built on the real API's shapes; no tier 5 event was running when it was built,
so the tier 5 paths are tested on made-up games with the real layout."""
import re
from datetime import timedelta, timezone, datetime
from zoneinfo import ZoneInfo

from kickoff.render import esc

RECENT = timedelta(days=3)
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

SHOWN = {"1-0": "1\u20130", "0-1": "0\u20131", "1/2-1/2": "\u00bd\u2013\u00bd"}
CLASSICAL = re.compile(r"^game\s*(\d+)", re.I)
MATCH_GAMES = 14          # a World Championship match: 14 classical games, first to 7.5 (FIDE regulations, 2026)
WIN_POINTS = 7.5


def short(name):
    """The name people say: 'Gukesh, D' -> Gukesh, 'Gukesh Dommaraju' -> Gukesh (a listed Indian star by his well-known name), 'Javokhir Sindarov' -> Sindarov (the last word)."""
    if "," in name:
        return name.split(",")[0].strip()
    m = INDIAN_STARS.search(name)
    if m:
        return m.group(1).title()
    return name.split()[-1] if name.split() else name


def is_match(tour):
    """A two-player match (the World Championship), not a tournament: Lichess's info says 'Match' or names the pair as 'A vs B'."""
    info = tour.get("info") or {}
    return info.get("format") == "Match" or " vs " in (info.get("players") or "")


def _points(x):
    return f"{x:g}".replace(".5", "\u00bd") if x % 1 else f"{x:g}"


def match_table(title, games, tiebreak_day=""):
    """The match as one table, built like the NBA League Leaders table: the title, a gold score row, then # · White · result · Black, a grey note at the foot.
    games: [(game number, parse_pgn game)] of the finished classical games in order."""
    first = games[0][1]
    a, b = short(first["white"]), short(first["black"])
    pts = {a: 0.0, b: 0.0}
    rows = ""
    for n, g in games:
        w, k = short(g["white"]), short(g["black"])
        x, y = POINTS[g["result"]]
        pts[w] = pts.get(w, 0.0) + x
        pts[k] = pts.get(k, 0.0) + y
        rows += f'<tr><td class="n">{n}</td><td>{esc(w)}</td><td>{SHOWN[g["result"]]}</td><td>{esc(k)}</td></tr>'
    left = max(MATCH_GAMES - len(games), 0)
    top, low = max(pts.values()), min(pts.values())
    if top >= WIN_POINTS:
        who = max(pts, key=pts.get)
        note = f"{esc(who)} wins the match"
    elif left == 0:
        note = "Level after 14 games: tiebreaks" + (f" on {esc(tiebreak_day)}" if tiebreak_day else "")
    else:
        note = f"First to 7\u00bd \u00b7 {left} game{'s' if left != 1 else ''} to play"
    score = f"{esc(a)} {_points(pts[a])} \u2013 {_points(pts[b])} {esc(b)}"
    return (f'<div class="pts f1 nba lead chm"><div class="table-wrap"><table><colgroup><col style="width:12%"><col style="width:34%"><col style="width:20%"><col style="width:34%"></colgroup>'
            f'<thead><tr><th class="tt" colspan="4">{esc(title)}</th></tr></thead><tbody><tr class="grp"><td colspan="4">{score}</td></tr>{rows}'
            f'<tr><td class="note" colspan="4">{note}</td></tr></tbody></table></div></div>')


def match_blocks(source, now):
    """[(html, unique id, link)]: the table for each two-player match (tier 5, active or just finished) whose latest classical game finished in the last three days. Lichess's list
    shows a tournament's CURRENT round (ongoing or next), never the one just played, so the games come from the tournament's own round list, where a finished round carries
    finished and finishedAt. The id carries the number of games played: one table per new game, nothing on a rest day. Never raises."""
    try:
        top = source.top()
    except Exception:
        return []
    past = top.get("past")
    items = list(top.get("active") or []) + list((past.get("currentPageResults") if isinstance(past, dict) else past) or [])
    out, seen_tours = [], set()
    for it in items:
        tour = it.get("tour") or {}
        if (tour.get("tier") or 0) < ELITE_TIER or tour.get("id") in seen_tours:
            continue
        seen_tours.add(tour.get("id"))
        try:
            full = source.tour(tour["id"])
            if not is_match(full.get("tour") or tour):
                continue
            classical = [(int(CLASSICAL.match(x["name"]).group(1)), x) for x in full.get("rounds", []) if CLASSICAL.match(x.get("name", ""))]
            done = [(n, x) for n, x in classical if x.get("finished") and x.get("finishedAt")]
            if not done or not (timedelta(0) <= now - _utc(max(x["finishedAt"] for _, x in done)) <= RECENT):
                continue
            games = []
            for n, x in sorted(done, key=lambda t: t[0]):
                got = parse_pgn(source.round_pgn(x["id"]))
                if got:
                    games.append((n, got[0]))
            if not games:
                continue
            games = games[:MATCH_GAMES]
            day = ""
            if classical:
                last = max(classical, key=lambda t: t[0])[1]
                if last.get("startsAt"):
                    day = (_utc(last["startsAt"]).astimezone(ZoneInfo("Europe/Zurich")) + timedelta(days=1)).strftime("%-d %b")
            name = re.sub(r"\s*\|.*$", "", tour.get("name", "")).strip()
            title = re.sub(r"^FIDE\s+|\s+20\d\d$", "", name).replace("Chess Championship", "Championship") or name
            link = (full.get("tour") or tour).get("url") or f"https://lichess.org/broadcast/{tour.get('slug', '')}"
            out.append((match_table(title, games, day), f"chess:{tour['id']}:table:{len(games)}", link))
        except Exception:
            continue
    return out


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
        if tier >= ELITE_TIER and (is_match(tour) or re.search(r"world (chess )?championship", tour.get("name", ""), re.I)):
            continue                       # a world championship match has its own table (match_table): no second line saying the same
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
