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
FORMAT = re.compile(r"\b(T20I|ODI|Test|Tri-Series|World Cup|Asia Cup|Ashes|Champions Trophy)\b", re.I)
EXCLUDE = re.compile(r"\b(sixes|unofficial|under[- ]?19|u19|emerging|legends|masters|academy)\b", re.I)
HIGHLIGHT = {"india", "sunrisers hyderabad"}
DURATION = {"t20": timedelta(hours=4), "odi": timedelta(hours=9)}


def strip_women(team):
    return re.sub(r"\s+women$", "", team.strip(), flags=re.I)


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
    if m.get("matchType") in ("t20", "odi", "test") and FORMAT.search(name) and any(strip_women(t).lower() in TEST_NATIONS for t in teams):
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
    - live men's or women's Tests whose status line has changed since last time (each day's play is reported once)."""
    seen, last_status, out = set(seen or ()), last_status or {}, []
    for m in matches:
        c = classify(m)
        if c["kind"] is None:
            continue
        begin = started(m)
        if m.get("matchEnded"):
            ends = begin + DURATION.get(m["matchType"], timedelta(hours=10))
            if m["id"] in seen or not (window_start <= ends <= now):
                continue
        elif m.get("matchStarted") and m["matchType"] == "test" and c["kind"] == "international":
            if last_status.get(m["id"]) == m.get("status"):
                continue
        else:
            continue
        out.append({**m, "class": c})
    return sorted(out, key=lambda x: (-x["class"]["priority"], x["dateTimeGMT"]), reverse=False)


def title(m):
    """'New Zealand v India' and the rest of the name ('5th T20I, India tour of New Zealand 2026')."""
    parts = [p.strip() for p in m["name"].split(",")]
    teams = parts[0].replace(" vs ", " v ")
    return teams, ", ".join(parts[1:])


def result_html(m):
    teams, rest = title(m)
    names = r.esc(teams)
    for t in m.get("teams") or []:
        if strip_women(t).lower() in HIGHLIGHT:
            names = names.replace(r.esc(t), f"<strong>{r.esc(t)}</strong>")
    scores = " · ".join(r.esc(innings_line(s, m.get("teams") or [])) for s in m.get("score") or [])
    live = "" if m.get("matchEnded") else '<span class="tag">Live</span> '
    return (f'<li><span class="cm">{names}</span><span class="cs">{scores}</span>'
            f'<span class="cr">{live}{r.esc(m.get("status") or "")}</span><span class="ct">{r.esc(rest)}</span></li>')


def results_html(picked):
    """Matches grouped under International, Women's international, and each league, in priority order. '' if none."""
    groups, order = {}, []
    for m in picked:
        label = m["class"]["label"]
        if label not in groups:
            groups[label] = []
            order.append(label)
        groups[label].append(m)
    out = ""
    for label in order:
        out += f"<h3>{r.esc(label)}</h3><ul class=\"cricket\">{''.join(result_html(m) for m in groups[label])}</ul>"
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


def standout_html(o):
    series = ", ".join(o["match"].split(",")[1:]).strip()
    context = f" ({r.esc(series)}; {r.esc(o['result'])})" if o["result"] else f" ({r.esc(series)})"
    if o["kind"] in ("century", "fast fifty"):
        label = "century" if o["kind"] == "century" else f"fifty off {o['balls']} balls"
        figures = f"{o['runs']}{'*' if o['not_out'] else ''} off {o['balls']} balls, {o['fours']} fours and {o['sixes']} sixes"
        return (f"<li><strong>{r.esc(o['name'])}</strong> ({r.esc(o['team'])}) · {label}: {figures} against {r.esc(o['against'])}{context}</li>")
    label = "five-wicket haul" if o["kind"] == "five-for" else "four-wicket haul"
    overs = f"{o['overs']:g}" if isinstance(o["overs"], (int, float)) else str(o["overs"])
    return (f"<li><strong>{r.esc(o['name'])}</strong> ({r.esc(o['team'])}) · {label}: {o['wickets']} for {o['runs_conceded']} off {overs} overs "
            f"against {r.esc(o['against'])}{context}</li>")


def standouts_html(items):
    return '<h3>Standouts</h3><ol class="standouts">' + "".join(standout_html(o) for o in items) + "</ol>" if items else ""


# ---- The whole cricket block, within the daily call budget -------------------------------------

def run(now, window_start, st, get_matches, get_scorecard, affordable):
    """Build the cricket section. get_matches() -> (matches, calls used); get_scorecard(id) -> (card, calls used);
    affordable(used) -> how many scorecards fit. st: {"seen": [match ids], "status": {id: last status}}.
    Returns {"html", "state", "used", "stats"}; html is '' when there is no cricket to report."""
    matches, used = get_matches()
    seen = set(st.get("seen", []))
    picked = pick(matches, now, window_start, seen, st.get("status", {}))
    found, checked, skipped = [], 0, 0
    for m in picked:  # most important first
        if affordable(used) < 1:  # not even one more scorecard fits in what is left of today's calls
            skipped += 1
            continue
        try:
            card, used = get_scorecard(m["id"])
        except Exception:  # a failed scorecard costs us the standouts for that match, never the result
            skipped += 1
            continue
        checked += 1
        found += standouts(card, m)
    top = rank(found)
    html = results_html(picked) + standouts_html(top)
    if html and skipped:
        html += (f'<p class="muted">Standouts were checked in {checked} of {len(picked)} matches: the free cricket data allows only '
                 f"about eight scorecards a day.</p>")
    new = {"seen": sorted(seen | {m["id"] for m in picked if m.get("matchEnded")})[-400:],
           "status": {**st.get("status", {}), **{m["id"]: m.get("status") for m in picked if not m.get("matchEnded")}}}
    return {"html": html, "state": new, "used": used, "stats": {"picked": len(picked), "checked": checked, "skipped": skipped, "standouts": len(found)}}
