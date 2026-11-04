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
DURATION = {"t20": timedelta(hours=4), "odi": timedelta(hours=9), "test": timedelta(days=5)}   # estimates of the end: a Test can last five days (before this a finished Test was never reported: its estimated end, ten hours after the start, was long past)


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


def heading(m):
    """'New Zealand v India · 1st ODI': the teams and the match number and format; the tour or league name is left out (a league has its own heading, a series its
    own table), which keeps the line short."""
    teams, rest = title(m)
    first = rest.split(",")[0].strip() if rest else ""
    return teams, first


def short_result(status):
    """A result line that reads at a glance: 'India won by 5 wkts - 2nd inns reduced to 32 overs - DLS Target 143' becomes 'India won by 5 wickets (DLS)'; the bracket
    of balls remaining goes. A live Test's 'Day 3: Stumps - Australia lead by 42 runs' becomes 'Day 3: Stumps, Australia lead by 42 runs'."""
    text = (status or "").strip()
    if not text:
        return ""
    dls = bool(re.search(r"\bDLS\b", text))
    main = re.split(r"\s+-\s+", text)
    out = main[0].strip() if not re.match(r"^Day\s*\d", text) else ", ".join(x.strip() for x in main[:2])
    out = re.sub(r"\s*\(\d+b rem\)", "", out)
    out = re.sub(r"\bwkts\b", "wickets", out)
    out = re.sub(r"\bwkt\b", "wicket", out)
    out = re.sub(r"\s*\(DLS\)", "", out)
    return out + (" (DLS)" if dls else "")


def team_scores(m):
    """{team: 'score text'} from the match's innings: a one-innings match gives '185' or '143/5 (22.4)', a Test '329 & 387' (an innings still going shows its wickets,
    '187/4')."""
    teams, per = m.get("teams") or [], {}
    for sc in m.get("score") or []:
        team = team_of(sc.get("inning", ""), teams)
        w = "" if sc.get("w") in (None, 10) else f"/{sc.get('w')}"
        per.setdefault(team, []).append((f"{sc.get('r')}{w}", sc.get("o")))
    test = m.get("matchType") == "test"
    return {t: " & ".join(x[0] for x in v) if test or len(v) > 1 else v[0][0] + (f" ({v[0][1]:g})" if isinstance(v[0][1], (int, float)) else "") for t, v in per.items()}


def scores_line(m):
    """'New Zealand 185 (40.2) · India 143/5 (22.4)' or, for a Test, 'South Africa 329 & 387 · Australia 429 & 111'."""
    per = team_scores(m)
    order = [t for t in (m.get("teams") or []) if t in per] + [t for t in per if t not in (m.get("teams") or [])]
    return " · ".join(f"{t} {per[t]}" for t in order)


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


def series_day(date):
    """'Nov 4 2026' -> '4 Nov'; 'Oct 27-31 2026' (a Test) -> '27–31 Oct'."""
    m = re.match(r"([A-Z][a-z]{2}) (\d{1,2})(?:-(\d{1,2}))? \d{4}$", date or "")
    if not m:
        return date or ""
    return f"{m.group(2)}–{m.group(3)} {m.group(1)}" if m.group(3) else f"{m.group(2)} {m.group(1)}"


def patch_series(rows, current):
    """The series rows with the match being reported put right from our own checked data: ESPN's series page can be a stale copy (on 4 November it showed the 1st ODI
    as '185 v 103/1*, India require 40 runs' after the match had finished). The row for this match (same number and format) gets our result line and scores."""
    if not current:
        return rows
    label = FORMAT_LABEL.get(current.get("matchType"), "")
    ordinal = (re.search(r"\b(\d+(?:st|nd|rd|th))\b", current.get("name", ""), re.I) or [None, ""])[1].lower()
    per = team_scores(current)
    out = []
    for g in rows or []:
        if g["format"] == label and g["n"].lower() == ordinal and current.get("matchEnded"):
            teams = [dict(t, score=per.get(t["name"], t["score"]).split(" (")[0]) for t in g["teams"]]
            g = dict(g, teams=teams, result=short_result(current.get("status")) or g["result"], starts=None)
        out.append(g)
    return out


def series_html(rows, fmt, current=None):
    """A bilateral series as a series-style table (render.series_table) for one format: the two teams (the first listed match's order) with their wins either side
    of the word 'series', and a row for every match of the series made in advance: its number and date, both scores and the result under it once played (the
    winner in bold), 'Starts at ...' for a match still to come. rows: espn_cricket.parse_series; current: the match just reported, whose row is put right from
    our own data (patch_series)."""
    label = FORMAT_LABEL.get(fmt, fmt)
    games = [g for g in patch_series(rows, current) or [] if g["format"] == label]
    if not games:
        return ""
    left, right = (t["name"] for t in games[0]["teams"])
    wins = {left: 0, right: 0}
    body = []
    for g in games:
        day = series_day(g["date"])
        if g["result"]:
            sc = {t["name"]: t["score"] for t in g["teams"]}
            won = next((n for n in (left, right) if g["result"].startswith(n + " won")), None)
            if won:
                wins[won] += 1
            body.append({"mid": f"{g['n']} {label} · {day}", "a": sc.get(left, ""), "b": sc.get(right, ""), "win": "a" if won == left else "b" if won == right else None, "notes": [r.esc(g["result"])]})
        else:
            body.append({"mid": f"{g['n']} {label} · {day}" + (f" · {g['starts']}" if g["starts"] else ""), "pre": True})
    return r.series_table(f"{left} v {right} · {label} series", left, right, wins[left], wins[right], "series", body, "sm tst" if fmt == "test" else "sm")


def result_html(m, entry=None, series="", from_innings=0):
    """One match: the teams and its number ('New Zealand v India · 1st ODI'), the result as the big line, the scores under it, the player of the match, then the
    scorecard and the series table. A Test in progress carries its day and 'Day 3: Stumps, Australia lead by 42 runs' as the result line; from_innings: the
    innings of a Test already shown in full before (they come as one line each)."""
    teams, first = heading(m)
    names = r.esc(teams)
    for t in m.get("teams") or []:
        if strip_women(t).lower() in HIGHLIGHT:
            names = names.replace(r.esc(t), f"<strong>{r.esc(t)}</strong>")
    live = "" if m.get("matchEnded") or m.get("matchType") == "test" else '<span class="tag">In progress</span> '   # a Test in progress has its day flag instead'
    flag = ""
    if m.get("matchType") == "test" and not m.get("matchEnded"):
        day = day_of(m, entry)
        flag = f'<span class="dayflag">Test · {"Day " + str(day) if day else "in progress"}</span>'
    full = bool(entry) and scorecard_tier(m) < 3
    return (f'<li>{flag}<span class="cm">{names}{" · " + r.esc(first) if first else ""}</span>'
            f'<span class="cr">{live}{r.esc(short_result(m.get("status")))}</span><span class="cs">{r.esc(scores_line(m))}</span>{potm_html(entry)}'
            f'{full_scorecard_html(entry["innings"], from_innings) if full else ""}{standouts_html(entry["standouts"], inline=True) if full else ""}{series}</li>')


def table_html(label, rows):
    """A league's points table, shown after its results. '' when the rows do not add up (played = won + lost + tied + no result,
    positions 1..n in order): better no table than a wrong one. A Ties column appears only when some team has a tie."""
    if not rows or [x["pos"] for x in rows] != list(range(1, len(rows) + 1)) or any(x["p"] != x["w"] + x["l"] + x["t"] + x["nr"] for x in rows):
        return ""
    ties = any(x["t"] for x in rows)
    columns = [("#", True), ("Team", False), ("P", True), ("W", True), ("L", True)] + ([("T", True)] if ties else []) + [("NR", True), ("Pts", True), ("NRR", True)]
    body = [[x["pos"], x["team"], x["p"], x["w"], x["l"]] + ([x["t"]] if ties else []) + [x["nr"], x["pts"], f"{x['nrr']:+.3f}" if x["nrr"] is not None else ""] for x in rows]
    return f'<div class="pts">{r.table(f"{label} table", columns, body)}</div>'


def results_html(picked, cards=None, tables=None, series=None, from_innings=None):
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
        out += f"<h3>{r.esc(label)}</h3><ul class=\"cricket\">{''.join(result_html(m, (cards or {}).get(m['id']), (series or {}).get(m['id'], ''), (from_innings or {}).get(m['id'], 0)) for m in groups[label])}</ul>{(tables or {}).get(label, '')}"
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
    """False when a scorecard contradicts its own match's totals, so a wrong card is never shown. Cards can be stale: the free CricketData scorecard can be a
    snapshot from mid-innings (on 4 November it showed India's 143/5 with Gill and Kohli still 'batting' and 48 extras), and ESPN's page can be served from an old
    cache (the Mac once read India at 54/1 after the match had finished 143/5). Every innings is compared with the match's own score line: the card's total (a page
    total when ESPN gives one) must equal it in runs and wickets, the batters' runs must not exceed it, and the batters out must match the wickets (give or take one
    for a retired batter). With no score line to compare, only the batters are checked."""
    scores = match.get("score") or []
    for i, inn in enumerate(card.get("scorecard") or []):
        sc = scores[i] if i < len(scores) else None
        page_total = (inn.get("espn") or {}).get("total")
        if page_total and sc and sc.get("r") is not None and (page_total["r"] != sc["r"] or (sc.get("w") is not None and page_total["w"] != sc["w"])):
            return False
        if page_total and not sc:
            continue
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


def full_scorecard_html(innings, from_index=0):
    """A conventional scorecard for each innings: batting (with how each batter was out), then extras and a bold total with the run rate as the last two rows of the
    same table, then did-not-bat and fall of wickets (when the source has them), then the other side's bowling. Left out to fit a phone: minutes and dot balls.
    The innings before `from_index` (a Test's earlier innings, shown in full on an earlier day) come first as a single line each."""
    out = ""
    for inn in (innings or [])[:from_index]:
        wickets = "" if inn["wickets"] in (None, 10) else f"/{inn['wickets']}"
        runs = inn["runs"] if inn["runs"] is not None else ""
        overs = f" ({inn['overs']:g} ov)" if isinstance(inn["overs"], (int, float)) else ""
        label = " " + r.esc(inn["label"]) if inn.get("label") else ""
        out += f'<p class="muted fow"><strong>{r.esc(inn["team"])}</strong>{label} {runs}{wickets}{overs}</p>'
    for inn in (innings or [])[from_index:]:
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
            rows += (f'<tr class="sum total"><td class="name">Total<span class="dis">{inn["overs"]:g} ov, run rate {rr:.2f}</span></td>'
                     f'<td class="n">{total}</td><td colspan="4"></td></tr>')
        out += ('<div class="table-wrap"><table class="sc"><thead><tr><th>Batting</th><th class="n">R</th><th class="n">B</th><th class="n lc">4s</th>'
                f'<th class="n lc">6s</th><th class="n">SR</th></tr></thead><tbody>{rows}</tbody></table></div>')
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
        in_progress_test = m.get("matchType") == "test" and not m.get("matchEnded")        # no other matches of the series while a Test is on: only when it ends
        if espn_series and m.get("matchType") in SERIES_FORMATS and len(key[0]) == 2 and key not in done and not in_progress_test:
            done.add(key)
            table = series_html(espn_series(m), m.get("matchType"), current=m)
            if table:
                series[m["id"]] = table
    prev_done, test_done, from_innings = dict(st.get("test_done", {})), {}, {}
    for m in picked:                                    # a Test shows only the innings that moved since the last edition in full; the earlier ones are one line each
        entry = shown_cards.get(m["id"])
        if m.get("matchType") == "test" and entry:
            n = len(entry["innings"])
            from_innings[m["id"]] = min(prev_done.get(m["id"], 0), max(n - 1, 0))
            test_done[m["id"]] = n if m.get("matchEnded") else max(n - 1, 0)
    html = results_html(picked, shown_cards, tables, series, from_innings) + standouts_html(top)
    if html and skipped:
        html += (f'<p class="muted">Standouts were checked in {checked} of {len(picked)} matches: the free cricket data allows only '
                 f"about eight scorecards a day when ESPN's pages are not available.</p>")
    new = {"seen": sorted(seen | {m["id"] for m in picked if m.get("matchEnded")})[-400:],
           "status": {**st.get("status", {}), **{m["id"]: m.get("status") for m in picked if not m.get("matchEnded")}},
           "cards": dict(list(cards.items())[-60:]), "test_done": dict(list({**prev_done, **test_done}.items())[-20:])}
    return {"html": html, "state": new, "used": used, "stats": {"picked": len(picked), "checked": checked, "skipped": skipped, "standouts": total_standouts}}


def persist_cards(new_cards, directory=None):
    """Save bought scorecards into the real state file, so a match is never paid for twice across runs. Only the 'cards'
    entry is touched: what has been reported and each live Test's last status stay as they were."""
    from kickoff import state
    saved = state.load("cricket", directory=directory)
    merged = {**saved.get("cards", {}), **new_cards}
    state.save("cricket", {**saved, "cards": dict(list(merged.items())[-60:])}, directory)
