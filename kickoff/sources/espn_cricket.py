"""Cricket scorecards from ESPN's public cricket pages (the Cricinfo scorecard, served on espn.com).

There is no official API for this, so we read the page's HTML. That is fragile by nature: when ESPN changes the page the
parser returns nothing and the digest falls back to the CricketData scorecard (or just the result line). Used gently, for
personal use: our own honest User-Agent, one scores page per run, one page per scorecard, a pause between pages, and
nothing is fetched twice because finished scorecards are cached by the caller.

The scorecard comes back in the same shape CricketData uses ({"scorecard": [innings...]}), plus an "espn" entry on each
innings with what only this source has: the real extras split, total and run rate, did-not-bat, fall of wickets.
"""
import html as htmllib
import re
import time

from kickoff import http
from kickoff.leaders import surname

BASE = "https://www.espn.com"
SCORES_URL = BASE + "/cricket/scores"
PAUSE = 1.0  # seconds between pages

LINK = re.compile(r'href="(/cricket/series/(\d+)/(scorecard|game|report)/(\d+)/([^"]+))"')


def _text(fragment):
    return htmllib.unescape(re.sub(r"<[^>]+>", "", fragment)).replace("\xa0", " ").strip()


def _int(s, default=0):
    m = re.search(r"-?\d+", s or "")
    return int(m.group()) if m else default


def _float(s):
    m = re.search(r"-?\d+(?:\.\d+)?", s or "")
    return float(m.group()) if m else None


def _clean(page):
    """The pages are server-rendered React: every tag carries a data-reactid and text is wrapped in comment markers."""
    return re.sub(r"<!--.*?-->", "", re.sub(r' data-reactid="\d+"', "", page), flags=re.S)


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


# ---- The day's page: which matches have a scorecard page ----------------------------------------

def parse_index(page):
    """{game id: {"slug", "scorecard": url or None}} from the scores page."""
    games = {}
    page = _clean(page)
    for path, _series, kind, game, rest in LINK.findall(page):  # noqa: B007
        g = games.setdefault(game, {"slug": rest, "series": _series, "scorecard": None})
        if kind == "scorecard":
            g["scorecard"] = BASE + path
    return games


def find_game(index, teams, match_name="", need_scorecard=True):
    """The game on the scores page between these two teams, or None when there is no single clear answer. Two games
    between the same sides on one page are told apart by their ordinal ('5th'), else we skip rather than guess."""
    if len(teams) != 2:
        return None
    a, b = slug(teams[0]), slug(teams[1])
    found = [g for g in index.values() if (g["scorecard"] or not need_scorecard) and (g["slug"].startswith(f"{a}-vs-{b}") or g["slug"].startswith(f"{b}-vs-{a}"))]
    if len(found) > 1:
        ordinal = re.search(r"\b(\d+(?:st|nd|rd|th))\b", match_name or "", re.I)
        if ordinal:
            found = [g for g in found if f"-{ordinal.group(1).lower()}-" in g["slug"]]
    return found[0] if len(found) == 1 else None


def find_scorecard_url(index, teams, match_name=""):
    g = find_game(index, teams, match_name)
    return g["scorecard"] if g else None


# ---- A scorecard page ------------------------------------------------------------------------------

def _batters(section):
    rows = []
    head = re.search(r'<div class="wrap header">(.*?)<div class="cell highlight', section, re.S)
    cols = [_text(c) for c in re.findall(r'<div class="cell runs">(.*?)</div>', head.group(1), re.S)] if head else []
    if not cols:
        return rows
    for block in re.findall(r'<div class="wrap batsmen">(.*?)<div class="cell highlight', section, re.S):
        name_cell = re.search(r'<div class="cell batsmen">(.*?)</div>', block, re.S)
        out_cell = re.search(r'<div class="cell commentary">(.*?)</div>', block, re.S)
        if not name_cell:
            continue
        shown = _text(name_cell.group(1))
        title = re.search(r'title="View the player profile of ([^"]+)"', name_cell.group(1))
        name = htmllib.unescape(title.group(1)).strip() if title else re.sub(r"\s*(\(c\)|†)", "", shown).strip()
        marks = (" (c)" if "(c)" in shown else "") + (" †" if "†" in shown else "")
        cells = [_text(c) for c in re.findall(r'<div class="cell runs">(.*?)</div>', block, re.S)]
        if len(cells) != len(cols):
            continue
        v = dict(zip(cols, cells))  # shorter formats have no minutes column, so read by header, not by position
        rows.append({"batsman": {"name": name}, "dismissal-text": _text(out_cell.group(1)) if out_cell else "", "mark": marks.strip(),
                     "r": _int(v.get("R")), "b": _int(v.get("B")), "m": _int(v.get("M"), None), "4s": _int(v.get("4s")), "6s": _int(v.get("6s")), "sr": _float(v.get("SR"))})
    return rows


def _bowlers(section):
    rows = []
    head = re.search(r"<thead>(.*?)</thead>", section, re.S)
    cols = [_text(c) for c in re.findall(r"<th[^>]*>(.*?)</th>", head.group(1), re.S)] if head else []
    body = re.search(r"<tbody>(.*?)</tbody>", section, re.S)
    for tr in re.findall(r"<tr>(.*?)</tr>", body.group(1) if body else "", re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if not cols or len(cells) != len(cols):
            continue
        v = dict(zip(cols, [_text(c) for c in cells]))  # by header, since the columns differ between formats
        title = re.search(r'title="View the player profile of ([^"]+)"', cells[0])
        name = htmllib.unescape(title.group(1)).strip() if title else _text(cells[0])
        rows.append({"bowler": {"name": name}, "o": _float(v.get("O")), "m": _int(v.get("M")), "r": _int(v.get("R")), "w": _int(v.get("W")), "eco": _float(v.get("Econ")),
                     "0s": _int(v.get("0s")), "wd": _int(v.get("WD")), "nb": _int(v.get("NB"))})
    return rows


def _extras(text):
    """'7 (b 1, lb 1, nb 1, w 4)' -> {"total": 7, "b": 1, "lb": 1, "nb": 1, "w": 4}"""
    out = {"total": _int(text)}
    for key, n in re.findall(r"\b(b|lb|nb|w|pen)\s+(\d+)", text):
        out[key] = int(n)
    return out


def _total(text):
    """'191/8 (20 Overs, RR: 9.55)' -> runs 191, wickets 8, overs 20, rr 9.55. No '/n' means all out."""
    m = re.match(r"\s*(\d+)(?:/(\d+))?", text)
    if not m:
        return None
    overs = re.search(r"([\d.]+)\s*Overs?", text)
    rr = re.search(r"RR:\s*([\d.]+)", text)
    return {"r": int(m.group(1)), "w": int(m.group(2)) if m.group(2) else 10, "o": float(overs.group(1)) if overs else None,
            "rr": float(rr.group(1)) if rr else None}


def _did_not_bat(fragment):
    """['MG Bracewell, ', 'MJ Santner (c), ', ...] -> ['Bracewell', 'Santner (c)', ...]"""
    out = []
    for raw in re.findall(r"<span>(.*?)</span>", fragment):
        name = _text(raw).strip(" ,")
        captain = name.endswith("(c)")
        name = surname(name.replace("(c)", "").replace("†", "").strip())
        out.append(name + (" (c)" if captain else ""))
    return out


def _fow(text):
    """'1-2 (Abhishek Sharma, 1.1 ov), 2-19 (...)' -> '1-2 (Sharma, 1.1), 2-19 (...)': surnames, no 'ov', to fit a phone."""
    return re.sub(r"(\d+-\d+) \((.*?), ([\d.]+) ov\)", lambda m: f"{m.group(1)} ({surname(m.group(2))}, {m.group(3)})", text.strip())


def parse_scorecard(page):
    """Every innings on a scorecard page, in CricketData's shape. [] when the page is not a scorecard we understand."""
    page = _clean(page)
    page = re.sub(r'<div id="commentary-[^"]*" class="commentary-content.*?</div></div>', "", page, flags=re.S)
    innings = []
    for seg in page.split('<li class="accordion-item">')[1:]:
        if 'scorecard-section batsmen' not in seg:
            continue
        head = re.search(r"<h2>(.*?)</h2>", seg, re.S)
        bat_part, _, bowl_part = seg.partition('<div class="scorecard-section bowling">')
        batting, bowling = _batters(bat_part), _bowlers(bowl_part)
        if not batting:
            continue
        extras = re.search(r'<div class="wrap extras"><div class="cell">Extras</div><div class="cell">(.*?)</div>', bat_part, re.S)
        total = re.search(r'<div class="wrap total"><div class="cell">TOTAL</div><div class="cell">(.*?)</div>', bat_part, re.S)
        dnb = re.search(r'Did not bat.*?</span>(.*?)</div></div></div>', bat_part, re.S)
        fow = re.search(r"Fall of wickets:\s*</span>(.*?)</div>", bat_part, re.S)
        innings.append({
            "inning": _text(head.group(1)) if head else "", "batting": batting, "bowling": bowling,
            "espn": {"extras": _extras(_text(extras.group(1))) if extras else None, "total": _total(_text(total.group(1))) if total else None,
                     "dnb": _did_not_bat(dnb.group(1)) if dnb else [],
                     "fow": _fow(_text(fow.group(1))) if fow else ""}})
    return innings


def parse_meta(page):
    """What sits above the scorecard: {"status": the result or state line, "potm": [{"name", "team"}]} (potm empty until awarded)."""
    page = _clean(page)
    status = re.search(r'cscore_notes_game">(.*?)</', page, re.S)
    block = re.search(r'player-match__title">Player of the Match</div>(.*?)(?:<div id="gamepackage-links-wrap"|$)', page, re.S)
    potm = []
    if block:
        for name, team in re.findall(r'player-match__player__detail__link">(.*?)<span>(.*?)</span></a>', block.group(1), re.S):
            potm.append({"name": _text(name), "team": _text(team)})
    return {"status": htmllib.unescape(_text(status.group(1))) if status else "", "potm": potm}


# ---- A points table -----------------------------------------------------------------------------------

def table_url(series):
    return f"{BASE}/cricket/table/series/{series}"


def parse_table(page):
    """The league's points table: [{"pos", "team" (abbreviation), "name", "p", "w", "l", "t", "nr", "pts", "nrr"}], or None when the
    page has no single table in the layout we know (tournaments with groups have several, and are left out)."""
    page = _clean(page)
    if page.count('<table') != 1:
        return None
    cols = [_text(c) for c in re.findall(r"<th[^>]*>(.*?)</th>", re.search(r"<thead[^>]*>(.*?)</thead>", page, re.S).group(1), re.S)] if "<thead" in page else []
    rows = []
    for tr in re.findall(r'<tr class="standings-row"[^>]*>(.*?)</tr>', page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(cells) != len(cols):
            return None
        name = re.search(r'class="team-names">(.*?)</span>', cells[0], re.S)
        abbr = re.search(r"<abbr[^>]*>(.*?)</abbr>", cells[0], re.S)
        pos = re.search(r'class="number">(.*?)</span>', cells[0], re.S)
        v = dict(zip(cols, [_text(c) for c in cells]))
        if not (name and pos):
            return None
        rows.append({"pos": _int(pos.group(1)), "name": _text(name.group(1)), "team": _text(abbr.group(1)) if abbr else _text(name.group(1)),
                     "p": _int(v.get("M")), "w": _int(v.get("W")), "l": _int(v.get("L")), "t": _int(v.get("T")), "nr": _int(v.get("N/R")),
                     "pts": _int(v.get("PT")), "nrr": _float(v.get("NRR"))})
    return rows or None


# ---- A series page: every match of a bilateral series, played and still to come ----------------------

SERIES_URL = BASE + "/cricket/scores/series/{series}"
SERIES_HEADER = re.compile(r"^(\d+(?:st|nd|rd|th)) (T20I|ODI|Test),\s+(?:\([^)]*\)\s+)?at (.+), ([A-Z][a-z]{2} \d{1,2}(?:-\d{1,2})? \d{4})$")


def parse_series(page):
    """The matches of a series page, in the order the page lists them: [{"n": '1st', "format": 'ODI', "venue", "date": 'Nov 4 2026',
    "teams": [{"name", "abbr", "score"}, {...}], "result": 'India won by 4 wkts' or None, "starts": 'Starts at 15:00 local time' or None}].
    The page prints every match's header line twice (before the teams and before the result), which is how a match is delimited; a match
    with no result yet carries a 'Starts at ...' line instead. Anything not in that pattern is skipped rather than guessed."""
    tokens = [t.strip() for t in re.sub(r"<[^>]+>", "|", _clean(page)).split("|") if t.strip()]
    out, i = [], 0
    while i < len(tokens):
        m = SERIES_HEADER.match(tokens[i])
        if not m or (i and tokens[i - 1] == tokens[i]):
            i += 1
            continue
        j, teams = i + 1, []
        while j < len(tokens) and tokens[j] != tokens[i]:
            t = tokens[j]
            if t.startswith("("):                         # an annotation: '(57.1 ov, target 288)', '(f/o)' (follow-on)
                j += 1
                continue
            if re.search(r"\d", t):
                if teams and not t.startswith("("):
                    teams[-1]["score"] = (teams[-1]["score"] + " " + t).strip()
            elif re.fullmatch(r"[A-Z]{2,5}", t) and teams and not teams[-1]["abbr"]:
                teams[-1]["abbr"] = t
            else:
                teams.append({"name": t, "abbr": "", "score": ""})
            j += 1
        if j >= len(tokens) or len(teams) != 2:
            i += 1
            continue
        after = htmllib.unescape(htmllib.unescape(tokens[j + 1])) if j + 1 < len(tokens) else ""   # the page escapes the ampersand twice
        out.append({"n": m.group(1), "format": m.group(2), "venue": m.group(3), "date": m.group(4), "teams": teams,
                    "result": None if after.startswith("Starts at") or not after else after, "starts": after if after.startswith("Starts at") else None})
        i = j + 1
    return out


# ---- Fetching ----------------------------------------------------------------------------------------

def _get(url):
    return http.get_bytes(url).decode("utf-8", "replace")


GAME_URL = BASE + "/cricket/series/{series}/scorecard/{game}"      # the plain address of a scorecard; ESPN redirects it to the full page


class Source:
    """Reads the day's scores page once, then a scorecard or points table per match. Nothing here raises: any problem gives
    None, and the caller falls back to the other source (or leaves the table out)."""

    def __init__(self, fetch=_get, pause=PAUSE):
        self.fetch, self.pause, self.index, self.fetched, self.tables = fetch, pause, None, 0, {}

    def _page(self, url):
        if self.fetched:
            time.sleep(self.pause)
        page = self.fetch(url)
        self.fetched += 1
        return page

    def _game(self, match, need_scorecard):
        if self.index is None:
            self.index = parse_index(self._page(SCORES_URL))
        return find_game(self.index, match.get("teams") or [], match.get("name", ""), need_scorecard)

    def card(self, match):
        """The scorecard of a match in CricketData's shape (+ "status", "potm"), or None. ESPN serves some scorecard pages from an old cache (on 4 November the
        scores page's own link gave India 54/1 after the match had finished 143/5, while the plain /scorecard/<id> address was right), so when the match has a score
        line to compare with, the first address whose card agrees with it is used (the link, the plain address, the plain address with a cache-busting query);
        when none does, there is no card rather than a wrong one."""
        try:
            from kickoff import cricket
            game = self._game(match, True)
            if not game:
                return None
            found = re.search(r"/series/(\d+)/scorecard/(\d+)", game["scorecard"])
            plain = GAME_URL.format(series=found.group(1), game=found.group(2)) if found else None
            urls = [game["scorecard"]] + ([plain, plain + f"?t={int(time.time())}", plain.replace("www.espn.com", "www.espn.in")] if plain else [])   # the link, the plain address, a cache-buster, ESPN's India host (its own cache)
            for url in urls:
                page = self._page(url)
                innings = parse_scorecard(page) if page else None
                if not innings:
                    continue
                card = {"scorecard": innings, **parse_meta(page)}
                if cricket.card_consistent(card, match):
                    return card
            return None
        except Exception:
            return None

    def series(self, match):
        """Every match of the series this match belongs to (see parse_series), or None."""
        try:
            game = self._game(match, False)
            if not game:
                return None
            if ("series", game["series"]) not in self.tables:
                self.tables[("series", game["series"])] = parse_series(self._page(SERIES_URL.format(series=game["series"])))
            return self.tables[("series", game["series"])] or None
        except Exception:
            return None

    def table(self, match):
        try:
            game = self._game(match, False)
            if not game:
                return None
            if game["series"] not in self.tables:
                self.tables[game["series"]] = parse_table(self._page(table_url(game["series"])))
            return self.tables[game["series"]]
        except Exception:
            return None


def card_getter(fetch=_get, pause=PAUSE):
    return Source(fetch, pause).card


# ---- ESPN's cricket JSON feed: the matches the free CricketData list may not have yet -----------------------

HEADER = "https://site.web.api.espn.com/apis/v2/scoreboard/header?sport=cricket&lang=en&region=us"
SERIES_FEED = "https://site.api.espn.com/apis/site/v2/sports/cricket/{series}/scoreboard"
TYPES = {"odi": "odi", "t20i": "t20", "t20": "t20", "test": "test", "first-class": "test"}


def _draft(league, ev):
    """A CricketData-shaped match from a header event (no scores yet): its name carries the format and the league so the usual scope rules can read it."""
    teams = [t.strip() for t in (ev.get("name") or "").split(" v ")]
    title = re.sub(r"\s*\((?:D/N|N|D)\)", "", ev.get("title") or "").strip()
    kind = TYPES.get(((ev.get("eventType") or (ev.get("class") or {}).get("eventType") or "")).lower(), "t20")
    return {"id": f"espn-{ev['id']}", "name": ", ".join(x for x in (" vs ".join(teams), title, league.get("name")) if x), "teams": teams, "matchType": kind,
            "dateTimeGMT": (ev.get("date") or "").replace("Z", "")[:19], "matchStarted": ev.get("status") in ("in", "post"), "matchEnded": ev.get("status") == "post",
            "status": ev.get("summary") or "", "series": league["id"], "event": ev["id"]}


def _scores(ev):
    """CricketData-style score entries ({"inning", "r", "w", "o"}), in batting order, from the competitors' line scores."""
    rows = []
    for c in ev["competitions"][0]["competitors"]:
        team = c["team"]["displayName"]
        for ls in c.get("linescores") or []:
            if ls.get("isBatting") or ls.get("runs"):
                rows.append((ls.get("period", 0), team, ls))
    out, count = [], {}
    for _, team, ls in sorted(rows, key=lambda x: x[0]):
        count[team] = count.get(team, 0) + 1
        out.append({"inning": f"{team} Inning {count[team]}", "r": ls.get("runs", 0), "w": ls.get("wickets", 0), "o": ls.get("overs")})
    return out


class Feed:
    """Reads the header scoreboard once (every current cricket series and its matches), then the scoreboard of a series for the matches wanted: the result line,
    the scores and the player of the match. Free JSON from the same ESPN host as the other sports, so it works from GitHub's servers (ESPN's cricket web
    pages do not)."""

    def __init__(self, get_json=None, pause=PAUSE):
        self.get_json, self.pause, self.calls = get_json or http.get_json, pause, 0

    def _call(self, url):
        if self.calls:
            time.sleep(self.pause)
        self.calls += 1
        return self.get_json(url)

    def matches(self, wanted=lambda draft: True, limit=6):
        """CricketData-shaped matches for the current events that `wanted(draft)` accepts, each with "status", "score" and "_card" ({"scorecard": [], "status",
        "potm"}); at most `limit` series are read. A series that fails is skipped."""
        header = self._call(HEADER)
        chosen = {}
        for league in header["sports"][0]["leagues"]:
            for ev in league.get("events", []):
                d = _draft(league, ev)
                if d["matchStarted"] and wanted(d):
                    chosen.setdefault(league["id"], {})[ev["id"]] = d
        out = []
        for sid, evs in list(chosen.items())[:limit]:
            try:
                board = self._call(SERIES_FEED.format(series=sid))
            except Exception:
                continue
            for e in board.get("events", []):
                d = evs.get(e["id"])
                if not d:
                    continue
                st = e.get("status") or {}
                names = {c["team"]["id"]: c["team"]["displayName"] for c in e["competitions"][0]["competitors"]}
                fa = (e["competitions"][0].get("status") or {}).get("featuredAthletes") or st.get("featuredAthletes") or []
                potm = [{"name": f["athlete"].get("displayName") or f["athlete"].get("name", ""), "team": names.get(str((f["athlete"].get("team") or {}).get("id")), "")}
                        for f in fa if f.get("abbreviation") == "POTM"]
                status = st.get("summary") or d["status"]
                out.append({**d, "status": status, "matchEnded": (st.get("type") or {}).get("state") == "post", "score": _scores(e),
                            "_card": {"scorecard": [], "status": status, "potm": potm}})
        return out
