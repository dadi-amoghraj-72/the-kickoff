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

SGT = ZoneInfo("Asia/Singapore")

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
    """2.5 -> '2½', 0.5 -> '½', 3.0 -> '3'."""
    whole = int(x)
    return (f"{whole}" if whole else "") + "\u00bd" if x % 1 else f"{whole}"


def pairing(text):
    """(white, black, result or None) of a round's first game, also before it is played: Lichess lists the pairing (and so the colours) in advance with result '*'."""
    chunk = re.split(r"\n\s*\n(?=\[Event )", text.strip())[0] if text.strip() else ""
    tags = dict(re.findall(r'\[(\w+) "([^"]*)"\]', chunk))
    if not (tags.get("White") and tags.get("Black")):
        return None
    return tags["White"], tags["Black"], tags.get("Result") if tags.get("Result") in POINTS else None


def _sgt(ms):
    return _utc(ms).astimezone(SGT)


def _clock(t):
    h = t.hour % 12 or 12
    return f"{h}:{t.minute:02d}{'am' if t.hour < 12 else 'pm'}" if t.minute else f"{h}{'am' if t.hour < 12 else 'pm'}"


def match_table(title, sub, games, now):
    """The whole match as one table (D, 2026-11-24): the title with a grey line under it (venue and dates), the gold running score, then EVERY game, played or not:
    # · date (grey) · Gukesh (W/B) · score · Sindarov (W/B). The two players keep their columns (the Indian star on the left), the colour is a small grey (W) or (B) from
    Lichess's own pairing, the score is read from the left player's side, a decisive game's winner is gold, the next game within 24 hours shows its time in gold, a game
    still to come shows a grey dash. A grey foot: first to 7½ and the games to play, the winner, or the tiebreaks. games: [{"n", "starts" (ms), "white", "black", "result"}]."""
    names = [short(x) for g in games for x in (g["white"], g["black"])]
    pair = list(dict.fromkeys(names))[:2]
    if len(pair) < 2:
        return ""
    left, right = sorted(pair, key=lambda x: (not INDIAN_STARS.search(x), pair.index(x)))
    pts = {left: 0.0, right: 0.0}
    tb = {left: 0.0, right: 0.0}
    rows, nxt = "", None
    for g in games:
        w, b = short(g["white"]), short(g["black"])
        res = g["result"]
        mark = {w: "W", b: "B"}
        cls = {left: "", right: ""}
        if res:
            x, y = POINTS[res]
            got = {w: x, b: y}
            (tb if g["tb"] else pts)[w] += x
            (tb if g["tb"] else pts)[b] += y
            score = f'<td class="s">{_points(got[left])}\u2013{_points(got[right])}</td>'
            if got[left] != got[right]:
                cls[left if got[left] > got[right] else right] = " w"
        elif nxt is None and g.get("starts") and timedelta(0) <= _utc(g["starts"]) - now <= timedelta(hours=24):
            nxt = g
            score = f'<td class="s next">{_clock(_sgt(g["starts"]))}</td>'
        else:
            score = '<td class="s up">\u2013</td>'
        if g.get("starts") and _utc(g["starts"]) > now:
            nxt = nxt or g
        date_ = _sgt(g["starts"]).strftime("%-d %b") if g.get("starts") else ""
        rows += (f'<tr><td class="n">{esc(g["label"])}</td><td class="d">{date_}</td>'
                 f'<td class="pl l{cls[left]}">{esc(left)}<span class="c">({mark[left]})</span></td>{score}'
                 f'<td class="pl r{cls[right]}">{esc(right)}<span class="c">({mark[right]})</span></td></tr>')
    played = sum(1 for g in games if g["result"] and not g["tb"])
    left_n = max(MATCH_GAMES - played, 0)
    if max(pts.values()) >= WIN_POINTS:
        note = f"{esc(max(pts, key=pts.get))} wins the match"
    elif any(g["tb"] and g["result"] for g in games):
        note = f"Tiebreaks: {esc(left)} {_points(tb[left])} \u2013 {_points(tb[right])} {esc(right)}"
    elif left_n == 0:
        note = "Level after 14 games: tiebreaks next"
    else:
        note = f"First to 7\u00bd \u00b7 {left_n} game{'s' if left_n != 1 else ''} to play"
    score_row = f"{esc(left)} {_points(pts[left])} \u2013 {_points(pts[right])} {esc(right)}"
    return (f'<div class="pts f1 chm"><div class="table-wrap"><table><colgroup><col style="width:7%"><col style="width:15%"><col style="width:30%"><col style="width:16%"><col style="width:32%"></colgroup>'
            f'<thead><tr><th class="tt" colspan="5">{esc(title)}{f"<span class=prog>{esc(sub)}</span>" if sub else ""}</th></tr></thead>'
            f'<tbody><tr class="grp"><td colspan="5">{score_row}</td></tr>{rows}<tr><td class="note" colspan="5">{note}</td></tr></tbody></table></div></div>')


def match_blocks(source, now):
    """[(html, unique id, link)]: the table of each two-player match (tier 5), in EVERY edition from the day before the first game until the morning after the last game
    played (D, 2026-11-24). Lichess's list shows a tournament's current round, so the games come from the tournament's own round list; each round's PGN gives the pairing
    (colours) even before it is played. Never raises."""
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
            info_tour = full.get("tour") or tour
            if not is_match(info_tour):
                continue
            rounds = [x for x in full.get("rounds", []) if x.get("startsAt")]
            if not rounds:
                continue
            first = min(x["startsAt"] for x in rounds)
            finished = [x["finishedAt"] for x in rounds if x.get("finished") and x.get("finishedAt")]
            to_come = [x for x in rounds if not x.get("finished") and _utc(x["startsAt"]) > now]
            if now < _utc(first) - timedelta(hours=36):
                continue
            games = []
            for x in rounds:
                m = CLASSICAL.match(x.get("name", ""))
                p = pairing(source.round_pgn(x["id"]))
                if not p:
                    continue
                games.append({"label": m.group(1) if m else "TB", "tb": not m, "starts": x["startsAt"], "white": p[0], "black": p[1], "result": p[2] if x.get("finished") or p[2] else None})
            if not games:
                continue
            decided = False
            pts = {}
            for g in games:
                if g["result"] and not g["tb"]:
                    x_, y_ = POINTS[g["result"]]
                    pts[short(g["white"])] = pts.get(short(g["white"]), 0) + x_
                    pts[short(g["black"])] = pts.get(short(g["black"]), 0) + y_
            decided = bool(pts) and max(pts.values()) >= WIN_POINTS
            if decided:
                games = [g for g in games if g["result"]]          # once decided, the games never played are dropped
            last_done = _utc(max(finished)) if finished else None
            if (decided or not to_come) and not (last_done and now - last_done <= timedelta(hours=36)):
                continue                                   # the match is over: the final table once, the morning after
            info = info_tour.get("info") or {}
            place = (info.get("location") or "").split(",")[0].strip()
            classical = [g for g in games if not g["tb"]]
            end_day = (_utc(max(g["starts"] for g in classical)).astimezone(ZoneInfo(info.get("timeZone") or "Europe/Zurich")) + timedelta(days=1)) if classical else None
            span = f"{_sgt(first).strftime('%-d %b')} \u2013 {end_day.strftime('%-d %b')}" if end_day else ""
            sub = " \u00b7 ".join(x for x in (place, span) if x)
            name = re.sub(r"\s*\|.*$", "", tour.get("name", "")).strip()
            title = re.sub(r"^FIDE\s+|\s+20\d\d$", "", name).replace("Chess Championship", "Championship") or name
            link = info_tour.get("url") or f"https://lichess.org/broadcast/{tour.get('slug', '')}"
            html_ = match_table(title, sub, games, now)
            if html_:
                out.append((html_, f"chess:{tour['id']}:table:{(now + timedelta(hours=8)).date().isoformat()}", link))
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
