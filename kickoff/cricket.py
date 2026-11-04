"""Cricket: which matches belong in the digest, how they are ranked, and how a result reads.

Scope (from the spec): the 12 Test-playing nations, men's and women's, all formats; the IPL, BBL and The Hundred; and
the women's competitions WPL, WBBL and the women's Hundred. Everything else is left out."""
import re
from datetime import datetime, timedelta, timezone

from kickoff import render as r

TEST_NATIONS = {"australia", "england", "india", "new zealand", "pakistan", "south africa", "sri lanka", "west indies",
                "bangladesh", "zimbabwe", "afghanistan", "ireland"}
# Checked in this order, so "women's" is tested before the men's version of the same name.
LEAGUES = [("WPL", r"women'?s premier league", 50), ("WBBL", r"women'?s big bash", 50), ("Women's Hundred", r"the hundred women|women'?s hundred", 50),
           ("IPL", r"indian premier league", 60), ("BBL", r"big bash league", 60), ("The Hundred", r"the hundred", 60)]
RESULT = re.compile(r"\b(won by|match tied|tied|no result|match drawn|drawn|abandoned)\b", re.I)    # a status line that says the match is over
FORMAT = re.compile(r"\b(T20I|ODI|Test|Tri-Series|World Cup|Asia Cup|Ashes|Champions Trophy)\b", re.I)
EXCLUDE = re.compile(r"\b(sixes|unofficial|under[- ]?19|u19|emerging|legends|masters|academy)\b", re.I)
WORLD_CUP = re.compile(r"\bworld cup\b", re.I)
QUALIFIER = re.compile(r"\b(qualifier|qualifying|pathway|challenge|league\s*(2|two|1|one))\b", re.I)
HIGHLIGHT = {"india", "sunrisers hyderabad"}
DURATION = {"t20": timedelta(hours=4), "odi": timedelta(hours=9)}


def strip_women(team):
    return re.sub(r"\s+women$", "", team.strip(), flags=re.I)


def match_type(m):
    """'t20', 'odi' or 'test': the list's own matchType, else read from the match name. The free list sometimes leaves matchType out of a newly added match
    (the 4 November New Zealand v India ODI came with none and was dropped as out of scope)."""
    if m.get("matchType"):
        return m["matchType"]
    found = re.search(r"\b(T20I|T20|ODI|Test)\b", m.get("name", ""), re.I)
    return {"t20i": "t20", "t20": "t20", "odi": "odi", "test": "test"}.get(found.group(1).lower(), "") if found else ""


def normalise(matches):
    """The list with every match's matchType filled in (see match_type); the matches are copied, the originals untouched."""
    return [m if m.get("matchType") else {**m, "matchType": match_type(m)} for m in matches]


def classify(m):
    """{"kind": "international" | "league" | None, "women", "label", "priority"} for a match from the list."""
    name = m.get("name", "")
    teams = m.get("teams") or []
    women = any(re.search(r"\bwomen", t, re.I) for t in teams) or bool(re.search(r"\bwomen'?s\b", name, re.I))
    if EXCLUDE.search(name) or any(re.search(r"\sA$", t) for t in teams):
        return {"kind": None}
    for label, pattern, priority in LEAGUES:
        if re.search(pattern, name, re.I):
            return {"kind": "league", "women": women or label in ("WPL", "WBBL", "Women's Hundred"), "label": label, "priority": priority}
    world_cup = bool(WORLD_CUP.search(name)) and not QUALIFIER.search(name)  # the tournament proper, whoever plays
    if m.get("matchType") in ("t20", "odi", "test") and FORMAT.search(name) and (world_cup or any(strip_women(t).lower() in TEST_NATIONS for t in teams)):
        is_test = m.get("matchType") == "test"
        return {"kind": "international", "women": women, "label": "Women's international" if women else "International",
                "priority": (95 if women else 100) if is_test else (70 if women else 80)}
    return {"kind": None}


def team_of(inning, teams=()):
    """The batting team from an innings label. The data is messy ('ireland Inning 1', 'Namibia,Ireland Inning 1'), so the label
    is matched against the match's real team names: the first name before a comma, ignoring case."""
    label = re.sub(r"\s+Inning\s+\d+$", "", inning or "").strip()
    first = label.split(",")[0].strip()
    for t in teams:
        if t.lower() == first.lower():
            return t
    for t in teams:
        if first and (first.lower() in t.lower() or t.lower() in first.lower()):
            return t
    return first


def innings_line(score, teams=()):
    """'India 191/8 (20)' from a score entry like {'r': 191, 'w': 8, 'o': 20, 'inning': 'India Inning 1'}."""
    team = team_of(score.get("inning", ""), teams)
    wickets = "" if score.get("w") == 10 else f"/{score.get('w')}"
    overs = score.get("o")
    return f"{team} {score.get('r')}{wickets}" + (f" ({overs:g})" if isinstance(overs, (int, float)) else "")


def started(m):
    return datetime.strptime(m["dateTimeGMT"], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def pick(matches, now, window_start, seen=None, last_status=None):
    """The matches for this edition, most important first, each with its classification.
    - finished matches that ended since the last edition (estimated from the start time and format) and are not seen before;
    - every Test still in progress, every day (the day of the Test is shown on the block)."""
    seen, last_status, out = set(seen or ()), last_status or {}, []
    for m in matches:
        c = classify(m)
        if c["kind"] is None:
            continue
        begin = started(m)
        if m.get("matchEnded"):
            ends = begin + DURATION.get(m.get("matchType"), timedelta(hours=10))     # an estimate: a rain-shortened or DLS match ends earlier than this
            if m["id"] in seen or ends < window_start:
                continue
        elif m.get("matchStarted") and m.get("matchType") == "test" and c["kind"] == "international":
            pass
        else:
            continue
        out.append({**m, "class": c})
    return sorted(out, key=lambda x: (-x["class"]["priority"], x["dateTimeGMT"]), reverse=False)


MAX_EXTRA_SERIES = 6


def espn_extras(matches, feed):
    """Matches that ESPN's cricket feed has and the free CricketData list does not (it can run behind: on 4 November 2026 it lacked a finished New Zealand v India
    ODI that ESPN already had). Only matches in scope that are not already in `matches` (same two teams and the same ordinal, '1st ODI') are read from
    `feed` (espn_cricket.Feed); each comes back CricketData-shaped with its result line, scores and player of the match."""
    ordinal = lambda name: (re.search(r"\b(\d+(?:st|nd|rd|th))\b", name or "", re.I) or [None, ""])[1].lower()  # noqa: E731
    have = {}
    for m in matches:
        have.setdefault(frozenset(strip_women(t).lower() for t in m.get("teams") or []), set()).add(ordinal(m.get("name")))

    def wanted(draft):
        if classify(draft)["kind"] is None:
            return False
        pair = frozenset(strip_women(t).lower() for t in draft["teams"])
        return not (pair in have and (ordinal(draft["name"]) in have[pair] or not ordinal(draft["name"])))
    return feed.matches(wanted, MAX_EXTRA_SERIES)


def title(m):
    """'New Zealand v India' and the rest of the name ('5th T20I, India tour of New Zealand 2026')."""
    parts = [p.strip() for p in m["name"].split(",")]
    teams = parts[0].replace(" vs ", " v ")
    return teams, ", ".join(parts[1:])


def day_of(m, entry=None):
    """The day of a Test in progress: from the match's status line ('Day 2: Stumps - ...'), else from ESPN's."""
    for text in (m.get("status"), (entry or {}).get("status")):
        found = re.search(r"\bDay\s*(\d)\b", text or "", re.I)
        if found:
            return int(found.group(1))
    return None


def potm_html(entry):
    people = (entry or {}).get("potm") or []
    if not people:
        return ""
    return '<span class="potm">Player of the match: ' + ", ".join(f"<strong>{r.esc(p['name'])}</strong> ({r.esc(p['team'])})" for p in people) + "</span>"


SERIES_FORMATS = ("test", "odi")   # D: series tables for Test and ODI series (add "t20" to widen it to T20I series)
FORMAT_LABEL = {"test": "Test", "odi": "ODI", "t20": "T20I"}


def series_html(rows, fmt):
    """A bilateral series as a series-style table (render.series_table) for one format: the two teams (the first listed match's order) with
    their wins either side of the word 'series', and a row for every match of the series made in advance: its number and date, both scores
    and the result under it once played (the winner in bold), 'Starts at ...' for a match still to come. rows: espn_cricket.parse_series."""
    label = FORMAT_LABEL.get(fmt, fmt)
    games = [g for g in rows or [] if g["format"] == label]
    if not games:
        return ""
    left, right = (t["name"] for t in games[0]["teams"])
    wins = {left: 0, right: 0}
    body = []
    for g in games:
        when = datetime.strptime(g["date"], "%b %d %Y")
        day = f"{when.day} {when:%b}"
        if g["result"]:
            sc = {t["name"]: t["score"] for t in g["teams"]}
            won = next((n for n in (left, right) if g["result"].startswith(n + " won")), None)
            if won:
                wins[won] += 1
            body.append({"mid": f"{g['n']} {label} · {day}", "a": sc.get(left, ""), "b": sc.get(right, ""), "win": "a" if won == left else "b" if won == right else None, "notes": [r.esc(g["result"])]})
        else:
            body.append({"mid": f"{g['n']} {label} · {day}" + (f" · {g['starts']}" if g["starts"] else ""), "pre": True})
    return r.series_table(f"{left} v {right} · {label} series", left, right, wins[left], wins[right], "series", body, "sm")


def result_html(m, entry=None, series=""):
    teams, rest = title(m)
    names = r.esc(teams)
    for t in m.get("teams") or []:
        if strip_women(t).lower() in HIGHLIGHT:
            names = names.replace(r.esc(t), f"<strong>{r.esc(t)}</strong>")
    scores = " · ".join(r.esc(innings_line(s, m.get("teams") or [])) for s in m.get("score") or [])
    live = "" if m.get("matchEnded") else '<span class="tag">In progress</span> '
    flag = ""
    if m.get("matchType") == "test" and not m.get("matchEnded"):
        day = day_of(m, entry)
        flag = f'<span class="dayflag">Test · {"Day " + str(day) if day else "in progress"}</span>'
    full = bool(entry) and scorecard_tier(m) < 3
    return (f'<li>{flag}<span class="cm">{names}</span><span class="cs">{scores}</span>'
            f'<span class="cr">{live}{r.esc(m.get("status") or "")}</span><span class="ct">{r.esc(rest)}</span>{potm_html(entry)}'
            f'{full_scorecard_html(entry["innings"]) if full else ""}{standouts_html(entry["standouts"], inline=True) if full else ""}{series}</li>')


def table_html(label, rows):
    """A league's points table, shown after its results. '' when the rows do not add up (played = won + lost + tied + no result,
    positions 1..n in order): better no table than a wrong one. A Ties column appears only when some team has a tie."""
    if not rows or [x["pos"] for x in rows] != list(range(1, len(rows) + 1)) or any(x["p"] != x["w"] + x["l"] + x["t"] + x["nr"] for x in rows):
        return ""
    ties = any(x["t"] for x in rows)
    columns = [("#", True), ("Team", False), ("P", True), ("W", True), ("L", True)] + ([("T", True)] if ties else []) + [("NR", True), ("Pts", True), ("NRR", True)]
    body = [[x["pos"], x["team"], x["p"], x["w"], x["l"]] + ([x["t"]] if ties else []) + [x["nr"], x["pts"], f"{x['nrr']:+.3f}" if x["nrr"] is not None else ""] for x in rows]
    return f'<div class="pts">{r.table(f"{label} table", columns, body)}</div>'


def results_html(picked, cards=None, tables=None, series=None):
    """Matches grouped under International, Women's international, and each league, in priority order. '' if none.
    tables: {league label: points table html}, shown straight after that league's results."""
    groups, order = {}, []
    for m in picked:
        label = m["class"]["label"]
        if label not in groups:
            groups[label] = []
            order.append(label)
        groups[label].append(m)
    out = ""
    for label in order:
        out += f"<h3>{r.esc(label)}</h3><ul class=\"cricket\">{''.join(result_html(m, (cards or {}).get(m['id']), (series or {}).get(m['id'], '')) for m in groups[label])}</ul>{(tables or {}).get(label, '')}"
    return out


# ---- Which matches get a full scorecard ---------------------------------------------------------

FULL_SCORECARD_TEAMS = {"india", "australia", "england", "pakistan", "new zealand", "south africa"}


def scorecard_tier(m):
    """1: a men's international involving India, Australia, England, Pakistan, New Zealand or South Africa, any men's Test, or any
    men's World Cup match (full scorecard). 2: any men's IPL match (full scorecard). 3: everything else (the result line only)."""
    c = m.get("class") or classify(m)
    teams = m.get("teams") or []
    if c.get("kind") == "international" and not c.get("women") and (
            any(strip_women(t).lower() in FULL_SCORECARD_TEAMS for t in teams) or m.get("matchType") == "test" or WORLD_CUP.search(m.get("name", ""))):
        return 1
    if c.get("label") == "IPL" and not c.get("women"):
        return 2
    return 3


def overs_decimal(overs):
    """17.4 overs (17 and 4 balls) is 17.667 for run-rate sums."""
    whole = int(overs)
    return whole + round((overs - whole) * 10) / 6


def short_dismissal(text, names):
    """'c Michael Bracewell b Adam Milne' -> 'c Bracewell b Milne': the bowler's and catcher's full names become surnames."""
    from kickoff.leaders import surname
    for name in sorted({n for n in names if n}, key=len, reverse=True):
        text = text.replace(name, surname(name))
    return text


NOT_OUT = {"", "not out", "batting", "did not bat", "yet to bat", "retired hurt", "retired not out", "absent hurt"}


def card_consistent(card, match):
    """False when a scorecard contradicts its own match's totals, so a wrong card is never shown. The free CricketData scorecard can be a snapshot from
    mid-innings: on 4 November it showed India's 143/5 with Gill and Kohli still 'batting' and 48 extras. For every innings the batters' runs must not exceed the
    total and the number of batters out must match the wickets (give or take one for a retired batter). A page-total card from ESPN carries its own total and is trusted."""
    scores = match.get("score") or []
    for i, inn in enumerate(card.get("scorecard") or []):
        if (inn.get("espn") or {}).get("total"):
            continue
        sc = scores[i] if i < len(scores) else None
        if not sc or sc.get("r") is None:
            continue
        batters = inn.get("batting") or []
        outs = sum(1 for b in batters if (b.get("dismissal-text") or "").strip().lower() not in NOT_OUT)
        if sum(b.get("r") or 0 for b in batters) > sc["r"] or (sc.get("w") is not None and abs(outs - sc["w"]) > 1):
            return False
    return True


def slim_card(card, match):
    """The parts of a scorecard we show and keep, per innings. Totals come from the match's own score list. Extras are
    worked out: total minus the batters' runs, with wides and no-balls counted from the bowlers and the rest as byes
    and leg-byes together (the data does not split those two)."""
    teams = match.get("teams") or []
    score = match.get("score") or []
    out = []
    for i, inn in enumerate(card.get("scorecard") or []):
        team = team_of(inn.get("inning", ""), teams)
        sc = score[i] if i < len(score) else {}
        bowler_names = [b["bowler"]["name"] for b in inn.get("bowling") or []]
        bat = [{"name": b["batsman"]["name"], "mark": b.get("mark") or "",
                "out": short_dismissal(b.get("dismissal-text") or "", bowler_names + [(b.get("bowler") or {}).get("name"), (b.get("catcher") or {}).get("name")]),
                "r": b.get("r") or 0, "b": b.get("b") or 0,
                "fours": b.get("4s") or 0, "sixes": b.get("6s") or 0, "sr": b.get("sr")} for b in inn.get("batting") or []]
        bowl = [{"name": b["bowler"]["name"], "o": b.get("o"), "m": b.get("m") or 0, "r": b.get("r") or 0, "w": b.get("w") or 0,
                 "eco": b.get("eco"), "wd": b.get("wd") or 0, "nb": b.get("nb") or 0} for b in inn.get("bowling") or []]
        espn = inn.get("espn") or {}
        total = espn.get("total")
        if total:  # the page's own total beats the match's score list
            sc = {"r": total["r"], "w": total["w"], "o": total["o"]}
        runs = sc.get("r")
        extras = espn.get("extras")  # the real split, when the source has it; otherwise worked out below
        if extras is None and runs is not None:
            total_extras = runs - sum(b["r"] for b in bat)
            wides, noballs = sum(b["wd"] for b in bowl), sum(b["nb"] for b in bowl)
            if total_extras >= wides + noballs >= 0:
                extras = {"total": total_extras, "w": wides, "nb": noballs, "b_lb": total_extras - wides - noballs}
        number = re.search(r"\b(\d)(?:st|nd|rd|th)\s+innings\b", inn.get("inning", ""), re.I) or re.search(r"\binning\s*(\d)\b", inn.get("inning", ""), re.I)
        label = {"1": "1st", "2": "2nd", "3": "3rd", "4": "4th"}.get(number.group(1), "") + " innings" if number and match.get("matchType") == "test" else ""
        out.append({"team": team, "label": label.strip(), "bowling_team": next((t for t in teams if t != team), ""), "runs": runs, "wickets": sc.get("w"),
                    "overs": sc.get("o"), "extras": extras, "batting": bat, "bowling": bowl,
                    "dnb": espn.get("dnb") or [], "fow": espn.get("fow") or ""})
    return out


def _num(value, places=2):
    return f"{float(value):.{places}f}" if isinstance(value, (int, float)) else ""


def full_scorecard_html(innings):
    """A conventional scorecard for each innings: batting (with how each batter was out), extras and total with the run
    rate, then did-not-bat and fall of wickets (when the source has them), then the other side's bowling. Left out to fit a
    phone: minutes and dot balls."""
    out = ""
    for inn in innings or []:
        wickets = "" if inn["wickets"] in (None, 10) else f"/{inn['wickets']}"
        total = f"{inn['runs']}{wickets}" if inn["runs"] is not None else ""
        overs = f" ({inn['overs']:g} ov)" if isinstance(inn["overs"], (int, float)) else ""
        out += f'<p class="inn"><strong>{r.esc(inn["team"])}</strong>{" " + r.esc(inn["label"]) if inn.get("label") else ""} {total}{overs}</p>'
        rows = ""
        for b in inn["batting"]:
            rows += (f'<tr><td class="name">{r.esc(b["name"])}{r.esc(" " + b["mark"] if b.get("mark") else "")}<span class="dis">{r.esc(b["out"])}</span></td><td class="n"><strong>{b["r"]}</strong></td>'
                     f'<td class="n">{b["b"]}</td><td class="n">{b["fours"]}</td><td class="n">{b["sixes"]}</td><td class="n">{_num(b["sr"])}</td></tr>')
        ex = inn["extras"]
        if ex is not None:
            kinds = (("w", "w"), ("nb", "nb"), ("b", "b"), ("lb", "lb"), ("pen", "pen")) if "b_lb" not in ex else (("w", "w"), ("nb", "nb"), ("b_lb", "b/lb"))
            parts = [f"{label} {ex[key]}" for key, label in kinds if ex.get(key)]
            rows += f'<tr class="sum"><td class="name">Extras<span class="dis">{r.esc(", ".join(parts))}</span></td><td class="n">{ex["total"]}</td><td colspan="4"></td></tr>'
        if inn["runs"] is not None and isinstance(inn["overs"], (int, float)) and inn["overs"] > 0:
            rr = inn["runs"] / overs_decimal(inn["overs"])
            rows += (f'<tr class="sum"><td class="name">Total<span class="dis">{inn["overs"]:g} ov, run rate {rr:.2f}</span></td>'
                     f'<td class="n">{total}</td><td colspan="4"></td></tr>')
        out += ('<div class="table-wrap"><table class="sc"><thead><tr><th>Batting</th><th class="n">R</th><th class="n">B</th><th class="n">4s</th>'
                f'<th class="n">6s</th><th class="n">SR</th></tr></thead><tbody>{rows}</tbody></table></div>')
        if inn.get("dnb"):
            out += f'<p class="muted fow"><strong>Did not bat:</strong> {r.esc(", ".join(inn["dnb"]))}</p>'
        if inn.get("fow"):
            out += f'<p class="muted fow"><strong>Fall of wickets:</strong> {r.esc(inn["fow"])}</p>'
        econ = lambda b: _num(b["r"] / overs_decimal(b["o"]) if b["o"] else b["eco"])  # exact, not the API's one-decimal figure  # noqa: E731
        brows = "".join(f'<tr><td class="name">{r.esc(b["name"])}</td><td class="n">{b["o"]:g}</td><td class="n">{b["m"]}</td><td class="n">{b["r"]}</td>'
                        f'<td class="n"><strong>{b["w"]}</strong></td><td class="n">{econ(b)}</td><td class="n">{b["wd"]}</td><td class="n">{b["nb"]}</td></tr>'
                        for b in inn["bowling"] if isinstance(b["o"], (int, float)))
        if brows:
            out += (f'<div class="table-wrap"><table class="sc"><thead><tr><th>Bowling</th><th class="n">O</th><th class="n">M</th>'
                    f'<th class="n">R</th><th class="n">W</th><th class="n">Econ</th><th class="n">WD</th><th class="n">NB</th></tr></thead><tbody>{brows}</tbody></table></div>')
    return out


# ---- Standouts, from the scorecard ------------------------------------------------------------

CENTURY, FIVE_FOR, FAST_FIFTY_BALLS, T20_FOUR_FOR = 100, 5, 25, 4
TIER = {"century": 0, "five-for": 1, "fast fifty": 2, "four-for": 3}  # ranking order: rarer and bigger first
MAX_STANDOUTS = 5


def standouts(card, match):
    """Performances that meet the spec's thresholds, from a scorecard. From a final scorecard we can only say that a fifty
    came off 25 balls or fewer when the whole innings did (a 50 reached early in an 80 is invisible), so that rule is
    conservative. T20 hat-tricks and career milestones are not in a scorecard and are not claimed."""
    out = []
    t20 = match.get("matchType") == "t20"
    teams = match.get("teams") or []
    for inn in card.get("scorecard") or []:
        batting_team = team_of(inn.get("inning", ""), teams)
        bowling_team = next((t for t in teams if t != batting_team), "")
        for b in inn.get("batting") or []:
            runs, balls = b.get("r") or 0, b.get("b") or 0
            who = {"name": b["batsman"]["name"], "team": batting_team, "against": bowling_team, "runs": runs, "balls": balls,
                   "fours": b.get("4s") or 0, "sixes": b.get("6s") or 0, "not_out": (b.get("dismissal-text") or "").lower() == "not out"}
            if runs >= CENTURY:
                out.append({**who, "kind": "century"})
            elif runs >= 50 and 0 < balls <= FAST_FIFTY_BALLS:
                out.append({**who, "kind": "fast fifty"})
        for b in inn.get("bowling") or []:
            wickets = b.get("w") or 0
            who = {"name": b["bowler"]["name"], "team": bowling_team, "against": batting_team, "wickets": wickets, "runs_conceded": b.get("r") or 0,
                   "overs": b.get("o"), "maidens": b.get("m") or 0}
            if wickets >= FIVE_FOR:
                out.append({**who, "kind": "five-for"})
            elif t20 and wickets >= T20_FOUR_FOR:
                out.append({**who, "kind": "four-for"})
    return [{**o, "match": match["name"], "result": match.get("status") or ""} for o in out]


def rank(items, limit=MAX_STANDOUTS):
    """Best first: centuries (most runs), five-fors (most wickets, fewest runs), fast fifties (fewest balls), four-fors (fewest runs)."""
    def key(o):
        k = TIER[o["kind"]]
        if o["kind"] == "century":
            return (k, -o["runs"], o["balls"])
        if o["kind"] in ("five-for", "four-for"):
            return (k, -o["wickets"], o["runs_conceded"])
        return (k, o["balls"], -o["runs"])
    return sorted(items, key=key)[:limit]


def standout_html(o, context=True):
    series = ", ".join(o["match"].split(",")[1:]).strip()
    context = (f" ({r.esc(series)}; {r.esc(o['result'])})" if o["result"] else f" ({r.esc(series)})") if context else ""
    if o["kind"] in ("century", "fast fifty"):
        label = "century" if o["kind"] == "century" else f"fifty off {o['balls']} balls"
        figures = f"{o['runs']}{'*' if o['not_out'] else ''} off {o['balls']} balls, {o['fours']} fours and {o['sixes']} sixes"
        return (f"<li><strong>{r.esc(o['name'])}</strong> ({r.esc(o['team'])}) · {label}: {figures} against {r.esc(o['against'])}{context}</li>")
    label = "five-wicket haul" if o["kind"] == "five-for" else "four-wicket haul"
    overs = f"{o['overs']:g}" if isinstance(o["overs"], (int, float)) else str(o["overs"])
    return (f"<li><strong>{r.esc(o['name'])}</strong> ({r.esc(o['team'])}) · {label}: {o['wickets']} for {o['runs_conceded']} off {overs} overs "
            f"against {r.esc(o['against'])}{context}</li>")


def standouts_html(items, inline=False):
    """Under a match's own scorecard (inline: no series or result repeated), or as the closing list for matches without a scorecard."""
    if not items:
        return ""
    if inline:
        return '<p class="muted fow"><strong>Standouts</strong></p><ul class="standouts in">' + "".join(standout_html(o, context=False) for o in rank(items)) + "</ul>"
    return '<h3>Standouts</h3><ol class="standouts">' + "".join(standout_html(o) for o in items) + "</ol>"


# ---- The whole cricket block, within the daily call budget -------------------------------------

def run(now, window_start, st, get_matches, get_scorecard, affordable, espn_card=None, espn_table=None, espn_series=None, espn_extra=None):
    """Build the cricket section. get_matches() -> (matches, calls used); get_scorecard(id) -> (card, calls used);
    affordable(used) -> how many scorecards fit. espn_card(match) -> a free scorecard or None: tried first, costs no calls.
    espn_table(match) -> the league's points table rows or None.
    espn_series(match) -> every match of the match's bilateral series (espn_cricket.parse_series) or None: a Test or ODI series gets a series table under its first match.
    st: {"seen": [match ids], "status": {id: last status}}.
    Returns {"html", "state", "used", "stats"}; html is '' when there is no cricket to report."""
    matches, used = get_matches()
    matches = normalise(matches)
    if espn_extra:                                      # ESPN's scores page can have a match the free list has not caught up with yet
        try:
            matches = matches + (espn_extra(matches) or [])
        except Exception:
            pass
    seen = set(st.get("seen", []))
    picked = pick(matches, now, window_start, seen, st.get("status", {}))
    found, checked, skipped, shown_cards = [], 0, 0, {}
    cards = {k: v for k, v in st.get("cards", {}).items() if "innings" in v}  # scorecards already bought: paid for once, never twice
    # Buy in this order: full-scorecard matches first (tier 1, then the IPL), then the rest for their standouts.
    total_standouts = 0

    def take(m, entry):
        """Standouts of a match with a full scorecard sit under it; the others join the closing list."""
        nonlocal checked, total_standouts
        checked += 1
        total_standouts += len(entry["standouts"])
        if scorecard_tier(m) == 3:
            found.extend(entry["standouts"])
        shown_cards[m["id"]] = entry

    for m in sorted(picked, key=lambda x: (scorecard_tier(x), -x["class"]["priority"], x["dateTimeGMT"])):
        cached = cards.get(m["id"]) if m.get("matchEnded") else None  # a card saved mid-match would be out of date
        # A card saved before did-not-bat, fall of wickets and Player of the Match existed is only a fallback: ESPN's richer one is tried first.
        if cached and (not espn_card or ("potm" in cached and all("dnb" in i for i in cached["innings"]))):
            take(m, cached)
            continue
        card = (espn_card(m) if espn_card else None) or m.get("_card")  # free: no calls used; ESPN's page (or the Mac's cache of it) before the feed's bare result
        if card is None and cached:
            take(m, cached)
            continue
        if card is None:
            if affordable(used) < 1:  # not even one more scorecard fits in what is left of today's calls
                skipped += 1
                continue
            try:
                card, used = get_scorecard(m["id"])
            except Exception:  # a failed scorecard costs us the standouts for that match, never the result
                skipped += 1
                continue
        if not card_consistent(card, m):                 # a scorecard that contradicts the match's own totals is worse than none
            skipped += 1
            continue
        entry = {"innings": slim_card(card, m), "standouts": standouts(card, m), "potm": card.get("potm") or [], "status": card.get("status") or ""}
        if m.get("matchEnded"):
            cards[m["id"]] = entry
        else:
            cards.pop(m["id"], None)
        take(m, entry)
    top = rank(found)
    tables = {}
    for m in picked:  # a points table for each league that played, once per league
        label = m["class"]["label"]
        if espn_table and m["class"]["kind"] == "league" and label not in tables:
            tables[label] = table_html(label, espn_table(m))
    series, done = {}, set()
    for m in picked:  # one series table per Test or ODI series, under the first of its matches shown
        key = (frozenset(strip_women(t).lower() for t in m.get("teams") or []), m.get("matchType"))
        if espn_series and m.get("matchType") in SERIES_FORMATS and len(key[0]) == 2 and key not in done:
            done.add(key)
            table = series_html(espn_series(m), m.get("matchType"))
            if table:
                series[m["id"]] = table
    html = results_html(picked, shown_cards, tables, series) + standouts_html(top)
    if html and skipped:
        html += (f'<p class="muted">Standouts were checked in {checked} of {len(picked)} matches: the free cricket data allows only '
                 f"about eight scorecards a day when ESPN's pages are not available.</p>")
    new = {"seen": sorted(seen | {m["id"] for m in picked if m.get("matchEnded")})[-400:],
           "status": {**st.get("status", {}), **{m["id"]: m.get("status") for m in picked if not m.get("matchEnded")}},
           "cards": dict(list(cards.items())[-60:])}
    return {"html": html, "state": new, "used": used, "stats": {"picked": len(picked), "checked": checked, "skipped": skipped, "standouts": total_standouts}}


def persist_cards(new_cards, directory=None):
    """Save bought scorecards into the real state file, so a match is never paid for twice across runs. Only the 'cards'
    entry is touched: what has been reported and each live Test's last status stay as they were."""
    from kickoff import state
    saved = state.load("cricket", directory=directory)
    merged = {**saved.get("cards", {}), **new_cards}
    state.save("cricket", {**saved, "cards": dict(list(merged.items())[-60:])}, directory)
